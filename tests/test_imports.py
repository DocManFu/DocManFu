import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import imports
from app.core.auth import require_admin


class FakeTaskResult:
    id = "task-123"


class FakeImportTask:
    def __init__(self):
        self.calls = []

    def delay(self, enex_path: str, user_id: str, original_filename: str):
        self.calls.append((enex_path, user_id, original_filename))
        return FakeTaskResult()


def make_client():
    app = FastAPI()
    app.include_router(imports.router)
    admin_id = uuid.uuid4()
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(
        id=admin_id, username="admin", role="admin"
    )
    return TestClient(app), admin_id


def test_evernote_import_streams_raw_body_to_shared_import_file(tmp_path, monkeypatch):
    fake_task = FakeImportTask()
    monkeypatch.setattr(imports.settings, "UPLOAD_DIR", str(tmp_path))

    import app.tasks.import_evernote as import_task_module

    monkeypatch.setattr(import_task_module, "import_evernote_task", fake_task)

    client, admin_id = make_client()
    body = b"<?xml version='1.0'?><en-export></en-export>"

    response = client.post(
        "/api/admin/import/evernote",
        content=body,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Filename": "My%20Notes.0.enex",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "filename": "My Notes.0.enex",
        "status": "started",
    }

    assert len(fake_task.calls) == 1
    enex_path, user_id, original_filename = fake_task.calls[0]
    assert user_id == str(admin_id)
    assert original_filename == "My Notes.0.enex"
    assert enex_path.startswith(str(tmp_path / "_imports"))
    assert enex_path.endswith(".enex")
    assert (tmp_path / "_imports").is_dir()
    assert open(enex_path, "rb").read() == body


def test_evernote_import_rejects_non_enex_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(imports.settings, "UPLOAD_DIR", str(tmp_path))
    client, _ = make_client()

    response = client.post(
        "/api/admin/import/evernote",
        content=b"not an enex",
        headers={"X-Filename": "notes.txt"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File must be an .enex file"


def test_evernote_import_rejects_empty_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(imports.settings, "UPLOAD_DIR", str(tmp_path))
    client, _ = make_client()

    response = client.post(
        "/api/admin/import/evernote",
        content=b"",
        headers={"X-Filename": "empty.enex"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded ENEX file was empty"
    assert not any((tmp_path / "_imports").glob("*.enex"))
