"""Uploads (e.g. from the docmanfu-watch CLI) must notify SSE clients immediately."""

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.events as events_module
from app.api import documents
from app.core.auth import require_write_access
from app.db.deps import get_db


class FakeSession:
    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_upload_publishes_document_updated(tmp_path, monkeypatch):
    published = []
    monkeypatch.setattr(
        events_module, "publish_event", lambda t, d: published.append((t, d))
    )
    monkeypatch.setattr(documents.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(documents, "update_search_vector", lambda db, doc_id: None)

    import app.tasks.ocr as ocr_module

    monkeypatch.setattr(
        ocr_module.process_ocr, "delay", lambda *a: SimpleNamespace(id="celery-1")
    )

    user_id = uuid.uuid4()
    app = FastAPI()
    app.include_router(documents.router)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    app.dependency_overrides[require_write_access] = lambda: SimpleNamespace(
        id=user_id, username="dustin", role="admin"
    )

    response = TestClient(app).post(
        "/api/documents/upload",
        files={"file": ("scan.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]
    assert (
        "document.updated",
        {"document_id": doc_id, "user_id": str(user_id), "changes": ["created"]},
    ) in published
