"""Celery task for importing Evernote ENEX files."""

import base64
import logging
import mimetypes
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.search import update_search_vector
from app.models.document import Document
from app.models.tag import Tag, document_tags
from app.tasks.base import DocManFuTask

try:
    import fitz  # pymupdf

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

logger = logging.getLogger(__name__)

IMPORTABLE_MIMES = {
    # Documents
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "text/plain": ".txt",
    "text/html": ".html",
    "text/xml": ".xml",
    "application/xml": ".xml",
    "application/json": ".json",
    "application/rtf": ".rtf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    # Images
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    # Audio
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/amr": ".amr",
    "audio/aac": ".aac",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    # Video
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    # Archives
    "application/zip": ".zip",
    "application/gzip": ".gz",
}


def strip_enml(content_xml: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content_xml)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_evernote_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str.strip(), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    if not HAS_PYMUPDF:
        return ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n".join(pages)
    except Exception:
        return ""


def guess_extension(mime: str) -> str | None:
    ext = mimetypes.guess_extension(mime)
    if ext:
        return ext
    parts = mime.split("/")
    if len(parts) == 2:
        return f".{parts[1].split('+')[0].split(';')[0]}"
    return None


def save_file(data: bytes, ext: str, upload_date: datetime) -> tuple[str, str]:
    file_uuid = uuid.uuid4()
    filename = f"{file_uuid}{ext}"
    relative_dir = upload_date.strftime("%Y/%m/%d")
    relative_path = f"{relative_dir}/{filename}"

    upload_dir = settings.UPLOAD_DIR
    abs_dir = Path(upload_dir) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    (abs_dir / filename).write_bytes(data)

    return filename, relative_path


def get_or_create_tag(db, tag_name: str, user_id, tag_cache: dict) -> Tag:
    key = tag_name.lower()
    if key in tag_cache:
        return tag_cache[key]

    tag = db.query(Tag).filter(Tag.name == tag_name, Tag.user_id == user_id).first()
    if not tag:
        tag = Tag(id=uuid.uuid4(), name=tag_name, color="#6B7280", user_id=user_id)
        db.add(tag)
        db.flush()
    tag_cache[key] = tag
    return tag


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.import_evernote")
def import_evernote_task(
    self, enex_path: str, user_id: str, original_filename: str = "import.enex"
):
    """Import an ENEX file as a background task. Publishes SSE events for live progress."""
    from app.core.events import publish_event
    from app.db.session import SessionLocal

    task_id = self.request.id
    db = SessionLocal()
    tag_cache: dict[str, Tag] = {}

    stats = {
        "total": 0,
        "imported": 0,
        "documents_created": 0,
        "errors": 0,
        "skipped": [],
        "error_list": [],
    }

    try:
        # First pass: count total notes for progress
        total_notes = 0
        for event, elem in ET.iterparse(enex_path, events=("end",)):
            if elem.tag == "note":
                total_notes += 1
            elem.clear()

        publish_event(
            "import.progress",
            {
                "task_id": task_id,
                "user_id": user_id,
                "filename": original_filename,
                "current": 0,
                "total": total_notes,
                "imported": 0,
                "documents_created": 0,
                "status": f"Starting import of {total_notes} notes...",
            },
        )

        # Second pass: actual import
        context = ET.iterparse(enex_path, events=("end",))

        for event, elem in context:
            if elem.tag != "note":
                continue

            stats["total"] += 1
            title = "?"

            try:
                title = (elem.findtext("title") or "Untitled").strip()
                created = parse_evernote_date(elem.findtext("created") or "")

                content_xml = elem.findtext("content") or ""
                content_text = strip_enml(content_xml)

                tag_names = [t.text.strip() for t in elem.findall("tag") if t.text]

                # Collect resources
                importable_resources = []
                skipped_resources = []
                for res in elem.findall("resource"):
                    data_elem = res.find("data")
                    mime_elem = res.find("mime")
                    res_attrs = res.find("resource-attributes")
                    fname_elem = (
                        res_attrs.find("file-name") if res_attrs is not None else None
                    )

                    if (
                        data_elem is not None
                        and data_elem.text
                        and mime_elem is not None
                        and mime_elem.text
                    ):
                        mime = mime_elem.text.strip()
                        res_filename = (
                            fname_elem.text.strip()
                            if fname_elem is not None and fname_elem.text
                            else None
                        )

                        if mime in IMPORTABLE_MIMES:
                            try:
                                raw = base64.b64decode(data_elem.text)
                                importable_resources.append((raw, mime, res_filename))
                            except Exception:
                                skipped_resources.append(
                                    {
                                        "mime": mime,
                                        "filename": res_filename,
                                        "reason": "base64 decode failed",
                                    }
                                )
                        else:
                            ext = guess_extension(mime)
                            if ext:
                                try:
                                    raw = base64.b64decode(data_elem.text)
                                    importable_resources.append(
                                        (raw, mime, res_filename)
                                    )
                                    IMPORTABLE_MIMES[mime] = ext
                                except Exception:
                                    skipped_resources.append(
                                        {
                                            "mime": mime,
                                            "filename": res_filename,
                                            "reason": "base64 decode failed",
                                        }
                                    )
                            else:
                                skipped_resources.append(
                                    {
                                        "mime": mime,
                                        "filename": res_filename,
                                        "reason": "unknown MIME type",
                                    }
                                )

                tag_objects = [
                    get_or_create_tag(db, tn, user_id, tag_cache) for tn in tag_names
                ]
                docs_created = []

                if importable_resources:
                    for raw_data, mime, res_filename in importable_resources:
                        ext = (
                            IMPORTABLE_MIMES.get(mime)
                            or guess_extension(mime)
                            or ".bin"
                        )
                        filename, relative_path = save_file(raw_data, ext, created)
                        orig_name = res_filename or f"{title}{ext}"

                        doc_content_text = content_text or None
                        if mime == "application/pdf":
                            pdf_text = extract_pdf_text(raw_data)
                            if pdf_text:
                                doc_content_text = (
                                    f"{doc_content_text}\n\n{pdf_text}"
                                    if doc_content_text
                                    else pdf_text
                                )

                        doc = Document(
                            id=uuid.uuid4(),
                            filename=filename,
                            original_name=orig_name,
                            file_path=relative_path,
                            mime_type=mime,
                            file_size=len(raw_data),
                            upload_date=created,
                            content_text=doc_content_text,
                            user_id=user_id,
                        )
                        db.add(doc)
                        docs_created.append(doc)

                elif content_text:
                    text_bytes = content_text.encode("utf-8")
                    filename, relative_path = save_file(text_bytes, ".txt", created)
                    doc = Document(
                        id=uuid.uuid4(),
                        filename=filename,
                        original_name=f"{title}.txt",
                        file_path=relative_path,
                        mime_type="text/plain",
                        file_size=len(text_bytes),
                        upload_date=created,
                        content_text=content_text,
                        user_id=user_id,
                    )
                    db.add(doc)
                    docs_created.append(doc)

                if docs_created:
                    db.flush()
                    for doc in docs_created:
                        for tag in tag_objects:
                            db.execute(
                                document_tags.insert().values(
                                    document_id=doc.id, tag_id=tag.id
                                )
                            )
                    db.commit()

                    for doc in docs_created:
                        try:
                            update_search_vector(db, doc.id)
                        except Exception:
                            pass

                    stats["imported"] += 1
                    stats["documents_created"] += len(docs_created)

                    if skipped_resources:
                        stats["skipped"].append(
                            {
                                "title": title,
                                "reason": f"Partial — {len(skipped_resources)} attachment(s) skipped",
                                "created": created.isoformat(),
                                "tags": tag_names,
                                "resources": skipped_resources,
                            }
                        )
                else:
                    reason = (
                        "Empty note"
                        if not skipped_resources
                        else f"All {len(skipped_resources)} attachment(s) unsupported"
                    )
                    stats["skipped"].append(
                        {
                            "title": title,
                            "reason": reason,
                            "created": created.isoformat(),
                            "tags": tag_names,
                            "resources": skipped_resources,
                        }
                    )

            except Exception as e:
                stats["errors"] += 1
                stats["error_list"].append({"title": title, "error": str(e)})
                db.rollback()
                logger.exception("Error importing note '%s'", title)

            elem.clear()

            # Publish progress on every note
            publish_event(
                "import.progress",
                {
                    "task_id": task_id,
                    "user_id": user_id,
                    "filename": original_filename,
                    "current": stats["total"],
                    "total": total_notes,
                    "imported": stats["imported"],
                    "documents_created": stats["documents_created"],
                    "current_note": title,
                    "status": f"Importing: {title}",
                },
            )

    except Exception as e:
        logger.exception("Fatal error during ENEX import")
        stats["error_list"].append({"title": "(fatal)", "error": str(e)})
    finally:
        db.close()
        # Clean up the temp ENEX file
        try:
            Path(enex_path).unlink(missing_ok=True)
        except Exception:
            pass

    result = {
        "task_id": task_id,
        "user_id": user_id,
        "filename": original_filename,
        "total_notes": stats["total"],
        "imported_notes": stats["imported"],
        "documents_created": stats["documents_created"],
        "errors": stats["errors"],
        "skipped": stats["skipped"],
        "error_list": stats["error_list"],
    }

    if stats["error_list"] and stats["imported"] == 0:
        publish_event("import.failed", result)
    else:
        publish_event("import.completed", result)

    return result
