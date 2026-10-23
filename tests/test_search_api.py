"""Search endpoint against a real PostgreSQL database.

Needs full-text search and JSON operators, so it only runs when
TEST_DATABASE_URL points at a disposable Postgres database (its tables are
dropped and recreated).
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import documents
from app.core.auth import get_current_user
from app.core.search import update_search_vector
from app.db.base import Base
from app.db.deps import get_db
from app.models import Document, Tag, User

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_DATABASE_URL not set (needs PostgreSQL)"
)

TODAY = date.today()


@pytest.fixture(scope="module")
def client():
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        owner = User(
            username="dustin",
            email="d@example.com",
            hashed_password="x",
            role="admin",
            token_version=0,
        )
        other = User(
            username="other",
            email="o@example.com",
            hashed_password="x",
            role="user",
            token_version=0,
        )
        db.add_all([owner, other])
        db.flush()
        bill = Tag(name="bill", color="#000000", user_id=owner.id)
        utility = Tag(name="Utility", color="#000000", user_id=owner.id)
        db.add_all([bill, utility])

        def doc(name, ai_name=None, **kw):
            d = Document(
                filename=f"{uuid.uuid4()}.pdf",
                original_name=name,
                ai_generated_name=ai_name,
                file_path="x",
                mime_type="application/pdf",
                file_size=1,
                user_id=kw.pop("user_id", owner.id),
                **kw,
            )
            db.add(d)
            return d

        doc(
            "scan1.pdf",
            "Utah Power Bill",
            content_text="Rocky Mountain Power electricity usage for Fountain Green",
            document_type="bill",
            ai_metadata={"company": "Rocky Mountain Power", "date": "2024-03-15"},
            bill_status="unpaid",
            bill_due_date=TODAY - timedelta(days=3),
            tags=[bill, utility],
        )
        doc(
            "scan2.pdf",
            "Ford Service Invoice",
            content_text="Ford dealership oil change and tire rotation 100% done",
            document_type="invoice",
            ai_metadata={"company": "Ford Motor", "date": "2023-07-01"},
            notes="warranty claim",
            tags=[bill],
        )
        doc(
            "city-newsletter.pdf",
            "Fountain Green City Newsletter",
            content_text="Utah county events and water restrictions",
            document_type="correspondence",
            ai_metadata={"date": "not-a-date", "summary": "Monthly city news"},
            upload_date=datetime(2022, 5, 1, tzinfo=timezone.utc),
        )
        doc("untitled.pdf", content_text=None)
        doc("scan4.pdf", ai_metadata={"date": "2024-99-99"})
        doc("private.pdf", "Utah Secret", user_id=other.id)
        doc("deleted.pdf", "Utah Deleted", deleted_at=datetime.now(timezone.utc))
        db.commit()
        for d in db.query(Document).all():
            update_search_vector(db, d.id)
        owner_id, other_id = owner.id, other.id

    app = FastAPI()
    app.include_router(documents.router)
    current = {"user": SimpleNamespace(id=owner_id, role="admin")}

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    test_client = TestClient(app)
    test_client.current = current
    test_client.other = SimpleNamespace(id=other_id, role="user")
    test_client.owner = current["user"]
    yield test_client
    Base.metadata.drop_all(engine)


def names(client, q, **params):
    res = client.get("/api/documents/search", params={"q": q, **params})
    assert res.status_code == 200, res.text
    return sorted(d["original_name"] for d in res.json()["documents"])


@pytest.mark.parametrize(
    "q, expected",
    [
        ("title:utah", ["private.pdf", "scan1.pdf"]),  # admin sees all users
        ("ocr:ford", ["scan2.pdf"]),
        ("ocr:100%", ["scan2.pdf"]),  # LIKE wildcards are literal
        ("tag:bill", ["scan1.pdf", "scan2.pdf"]),
        ("tag:utility", ["scan1.pdf"]),  # case-insensitive
        ("tag:bill -tag:utility", ["scan2.pdf"]),
        ("type:bill", ["scan1.pdf"]),
        ('type:"bank statement"', []),
        ("company:ford", ["scan2.pdf"]),
        ("from:rocky", ["scan1.pdf"]),
        ("notes:warranty", ["scan2.pdf"]),
        ("is:unpaid", ["scan1.pdf"]),
        ("is:overdue", ["scan1.pdf"]),
        ("is:bill", ["scan1.pdf"]),
        ("has:notes", ["scan2.pdf"]),
        ("-has:text title:untitled", ["untitled.pdf"]),
        ("is:untyped -title:utah", ["scan4.pdf", "untitled.pdf"]),
        ("date:2024", ["scan1.pdf"]),
        ("date:2024-03", ["scan1.pdf"]),
        ("after:2023 before:2024", ["scan2.pdf"]),
        ("date:2022-05", ["city-newsletter.pdf"]),  # bad AI date -> upload date
        ("utah", ["city-newsletter.pdf", "private.pdf", "scan1.pdf"]),
        ("utah -tag:bill", ["city-newsletter.pdf", "private.pdf"]),
        ('"fountain green" type:correspondence', ["city-newsletter.pdf"]),
        ("-title:utah title:ford", ["scan2.pdf"]),
    ],
)
def test_operators(client, q, expected):
    assert names(client, q) == expected


def test_negation_keeps_rows_with_null_fields(client):
    # untitled.pdf has no ai_generated_name / content / company
    assert "untitled.pdf" in names(client, "-title:utah -ocr:ford -company:ford")


def test_newer_and_older_than(client):
    recent = names(client, "newer_than:30d")
    assert "untitled.pdf" in recent and "scan2.pdf" not in recent
    assert "scan2.pdf" in names(client, "older_than:1y")


def test_non_admin_sees_only_own_documents(client):
    client.current["user"] = client.other
    try:
        assert names(client, "title:utah") == ["private.pdf"]
    finally:
        client.current["user"] = client.owner


def test_soft_deleted_excluded(client):
    assert "deleted.pdf" not in names(client, "title:deleted")


def test_response_terms_errors_and_facets(client):
    body = client.get(
        "/api/documents/search", params={"q": "tag:bill is:shiny", "limit": 1}
    ).json()
    assert body["total"] == 2
    assert len(body["documents"]) == 1
    assert body["terms"] == [
        {"key": "tag", "value": "bill", "negated": False, "start": 0, "end": 8}
    ]
    assert body["errors"] and "is:shiny" in body["errors"][0]
    facets = body["facets"]
    # facets cover the whole result set, not just the page
    assert {f["value"]: f["count"] for f in facets["tags"]} == {"bill": 2, "Utility": 1}
    assert {f["value"] for f in facets["types"]} == {"bill", "invoice"}
    assert [f["value"] for f in facets["years"]] == ["2024", "2023"]


def test_term_spans_are_utf16_offsets(client):
    q = "\U0001f600 tag:bill"  # emoji is 2 UTF-16 code units
    term = client.get("/api/documents/search", params={"q": q}).json()["terms"][0]
    assert (term["start"], term["end"]) == (3, 11)


def test_impossible_ai_date_falls_back_to_upload_date(client):
    assert "scan4.pdf" in names(client, f"date:{TODAY.year}")
    assert names(client, "date:2024-12") == []


def test_highlights_and_document_date(client):
    body = client.get("/api/documents/search", params={"q": "ocr:oil"}).json()
    doc = body["documents"][0]
    assert "<mark>" in doc["headline"]
    assert doc["document_date"] == "2023-07-01"

    # No text query: fall back to the AI summary
    body = client.get("/api/documents/search", params={"q": "type:correspondence"})
    assert body.json()["documents"][0]["headline"] == "Monthly city news"


def test_sorting(client):
    def order(sort):
        res = client.get(
            "/api/documents/search", params={"q": "tag:bill", "sort": sort}
        )
        return [d["original_name"] for d in res.json()["documents"]]

    assert order("newest") == ["scan1.pdf", "scan2.pdf"]
    assert order("oldest") == ["scan2.pdf", "scan1.pdf"]
    assert order("name") == ["scan2.pdf", "scan1.pdf"]  # Ford < Utah


def test_legacy_params_still_work(client):
    assert names(client, "utah", tag="bill") == ["scan1.pdf"]
