#!/usr/bin/env python3
"""Import Evernote ENEX files into DocManFu.

Usage:
    python scripts/import_evernote.py file1.enex [file2.enex ...]

Generates a markdown report of skipped/failed notes for review.
"""

import base64
import hashlib
import io
import mimetypes
import os
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

try:
    import fitz  # pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.tag import Tag, document_tags
from app.core.search import update_search_vector

# MIME types we can import as documents
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
    """Strip ENML/HTML tags to get plain text."""
    text = re.sub(r"<[^>]+>", " ", content_xml)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_evernote_date(date_str: str) -> datetime:
    """Parse Evernote date format: 20231215T143022Z"""
    try:
        return datetime.strptime(date_str.strip(), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def get_or_create_tag(db, tag_name: str, tag_cache: dict) -> Tag:
    """Find or create a tag by name (user_id=None for system-level tags)."""
    key = tag_name.lower()
    if key in tag_cache:
        return tag_cache[key]

    tag = db.query(Tag).filter(Tag.name == tag_name, Tag.user_id.is_(None)).first()
    if not tag:
        tag = Tag(id=uuid.uuid4(), name=tag_name, color="#6B7280", user_id=None)
        db.add(tag)
        db.flush()
    tag_cache[key] = tag
    return tag


def save_file(data: bytes, ext: str, upload_date: datetime, upload_dir: str) -> tuple[str, str]:
    """Save file to uploads/YYYY/MM/DD/{uuid}.ext, return (filename, relative_path)."""
    file_uuid = uuid.uuid4()
    filename = f"{file_uuid}{ext}"
    relative_dir = upload_date.strftime("%Y/%m/%d")
    relative_path = f"{relative_dir}/{filename}"

    abs_dir = Path(upload_dir) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    (abs_dir / filename).write_bytes(data)

    return filename, relative_path


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract embedded text from a PDF using pymupdf. Returns empty string on failure."""
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
    """Try to guess a file extension for an unknown MIME type."""
    ext = mimetypes.guess_extension(mime)
    if ext:
        return ext
    # Fallback: use the subtype
    parts = mime.split("/")
    if len(parts) == 2:
        return f".{parts[1].split('+')[0].split(';')[0]}"
    return None


def import_enex(filepath: str, upload_dir: str = "uploads") -> dict:
    """Import an ENEX file into DocManFu. Returns stats dict."""
    db = SessionLocal()
    tag_cache: dict[str, Tag] = {}
    stats = {
        "file": os.path.basename(filepath),
        "total": 0,
        "imported": 0,
        "errors": 0,
        "skipped": [],  # list of {title, reason, tags, created, content_preview, resources}
        "error_list": [],  # list of {title, error}
    }
    basename = stats["file"]

    print(f"Importing {basename}...")

    context = ET.iterparse(filepath, events=("end",))

    for event, elem in context:
        if elem.tag != "note":
            continue

        stats["total"] += 1
        title = "?"

        try:
            title = (elem.findtext("title") or "Untitled").strip()
            created = parse_evernote_date(elem.findtext("created") or "")
            updated = parse_evernote_date(elem.findtext("updated") or "")

            content_xml = elem.findtext("content") or ""
            content_text = strip_enml(content_xml)

            tag_names = [t.text.strip() for t in elem.findall("tag") if t.text]

            # Collect ALL resources (importable and not)
            importable_resources = []
            skipped_resources = []
            for res in elem.findall("resource"):
                data_elem = res.find("data")
                mime_elem = res.find("mime")
                fname_elem = res.find("resource-attributes/file-name") if res.find("resource-attributes") is not None else None
                if data_elem is not None and data_elem.text and mime_elem is not None and mime_elem.text:
                    mime = mime_elem.text.strip()
                    res_filename = fname_elem.text.strip() if fname_elem is not None and fname_elem.text else None
                    if mime in IMPORTABLE_MIMES:
                        try:
                            raw = base64.b64decode(data_elem.text)
                            importable_resources.append((raw, mime, res_filename))
                        except Exception:
                            skipped_resources.append({"mime": mime, "filename": res_filename, "reason": "base64 decode failed"})
                    else:
                        # Try to import with guessed extension
                        ext = guess_extension(mime)
                        if ext:
                            try:
                                raw = base64.b64decode(data_elem.text)
                                importable_resources.append((raw, mime, res_filename))
                                # Add to IMPORTABLE_MIMES for this run
                                IMPORTABLE_MIMES[mime] = ext
                            except Exception:
                                skipped_resources.append({"mime": mime, "filename": res_filename, "reason": "base64 decode failed"})
                        else:
                            skipped_resources.append({"mime": mime, "filename": res_filename, "reason": f"unknown MIME type"})

            tag_objects = [get_or_create_tag(db, tn, tag_cache) for tn in tag_names]

            docs_created = []

            if importable_resources:
                for raw_data, mime, res_filename in importable_resources:
                    ext = IMPORTABLE_MIMES.get(mime) or guess_extension(mime) or ".bin"
                    filename, relative_path = save_file(raw_data, ext, created, upload_dir)
                    # Use resource filename if available, otherwise title + ext
                    orig_name = res_filename or f"{title}{ext}"

                    # Extract text from PDFs
                    doc_content_text = content_text or None
                    if mime == "application/pdf":
                        pdf_text = extract_pdf_text(raw_data)
                        if pdf_text:
                            # Combine ENML note text with extracted PDF text
                            if doc_content_text:
                                doc_content_text = f"{doc_content_text}\n\n--- PDF Text ---\n\n{pdf_text}"
                            else:
                                doc_content_text = pdf_text

                    doc = Document(
                        id=uuid.uuid4(),
                        filename=filename,
                        original_name=orig_name,
                        file_path=relative_path,
                        mime_type=mime,
                        file_size=len(raw_data),
                        upload_date=created,
                        content_text=doc_content_text,
                    )
                    db.add(doc)
                    docs_created.append(doc)
            elif content_text:
                # Text-only note — import as .txt
                text_bytes = content_text.encode("utf-8")
                filename, relative_path = save_file(text_bytes, ".txt", created, upload_dir)
                doc = Document(
                    id=uuid.uuid4(),
                    filename=filename,
                    original_name=f"{title}.txt",
                    file_path=relative_path,
                    mime_type="text/plain",
                    file_size=len(text_bytes),
                    upload_date=created,
                    content_text=content_text,
                )
                db.add(doc)
                docs_created.append(doc)

            if docs_created:
                db.flush()
                for doc in docs_created:
                    for tag in tag_objects:
                        db.execute(document_tags.insert().values(document_id=doc.id, tag_id=tag.id))
                db.commit()
                for doc in docs_created:
                    update_search_vector(db, doc.id)
                stats["imported"] += 1

                # If some resources were skipped but others imported, note partial import
                if skipped_resources:
                    stats["skipped"].append({
                        "title": title,
                        "reason": "Partial import — some attachments skipped",
                        "tags": tag_names,
                        "created": created.isoformat(),
                        "content_preview": content_text[:200] if content_text else "",
                        "resources": skipped_resources,
                        "imported_count": len(docs_created),
                    })
            else:
                # Nothing imported
                reason = "Empty note — no content or attachments"
                if skipped_resources:
                    reason = f"All {len(skipped_resources)} attachment(s) have unsupported MIME types"
                stats["skipped"].append({
                    "title": title,
                    "reason": reason,
                    "tags": tag_names,
                    "created": created.isoformat(),
                    "content_preview": content_text[:200] if content_text else "",
                    "resources": skipped_resources,
                    "imported_count": 0,
                })

            if stats["total"] % 100 == 0:
                print(f"  Processed {stats['total']} notes from {basename} ({stats['imported']} imported)")

        except Exception as e:
            stats["errors"] += 1
            stats["error_list"].append({"title": title, "error": str(e)})
            db.rollback()
            print(f"  ERROR on note {stats['total']} ({title}): {e}", file=sys.stderr)

        elem.clear()

    db.close()
    print(f"Done with {basename}: {stats['total']} notes, {stats['imported']} imported, "
          f"{len(stats['skipped'])} skipped, {stats['errors']} errors")
    return stats


def generate_report(all_stats: list[dict], report_path: str):
    """Generate a markdown report of skipped and failed notes."""
    lines = [
        "# Evernote Import Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        "| File | Total | Imported | Skipped | Errors |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    grand_total = grand_imported = grand_skipped = grand_errors = 0
    all_skipped = []
    all_errors = []

    for stats in all_stats:
        skipped_count = len(stats["skipped"])
        lines.append(
            f"| {stats['file']} | {stats['total']} | {stats['imported']} "
            f"| {skipped_count} | {stats['errors']} |"
        )
        grand_total += stats["total"]
        grand_imported += stats["imported"]
        grand_skipped += skipped_count
        grand_errors += stats["errors"]
        all_skipped.extend(stats["skipped"])
        all_errors.extend(stats["error_list"])

    if len(all_stats) > 1:
        lines.append(
            f"| **Total** | **{grand_total}** | **{grand_imported}** "
            f"| **{grand_skipped}** | **{grand_errors}** |"
        )

    lines.append("")

    if not all_skipped and not all_errors:
        lines.append("✅ All notes imported successfully — nothing to review!")
    else:
        if all_skipped:
            lines.append(f"## Skipped Notes ({len(all_skipped)})")
            lines.append("")
            lines.append("These notes were not fully imported. Review and decide what to do with them.")
            lines.append("")

            for i, item in enumerate(all_skipped, 1):
                lines.append(f"### {i}. {item['title']}")
                lines.append("")
                lines.append(f"- **Reason:** {item['reason']}")
                lines.append(f"- **Created:** {item['created']}")
                if item["tags"]:
                    lines.append(f"- **Tags:** {', '.join(item['tags'])}")
                if item.get("imported_count", 0) > 0:
                    lines.append(f"- **Imported:** {item['imported_count']} attachment(s)")
                if item["resources"]:
                    lines.append(f"- **Skipped attachments:**")
                    for res in item["resources"]:
                        fname = f" (`{res['filename']}`)" if res.get("filename") else ""
                        lines.append(f"  - {res['mime']}{fname} — {res['reason']}")
                if item["content_preview"]:
                    preview = item["content_preview"]
                    if len(preview) >= 200:
                        preview += "…"
                    lines.append(f"- **Content preview:** {preview}")
                lines.append("")

        if all_errors:
            lines.append(f"## Errors ({len(all_errors)})")
            lines.append("")
            lines.append("These notes failed to import due to errors.")
            lines.append("")
            for i, item in enumerate(all_errors, 1):
                lines.append(f"{i}. **{item['title']}** — `{item['error']}`")
            lines.append("")

    report_text = "\n".join(lines)
    Path(report_path).write_text(report_text)
    print(f"\nReport saved to: {report_path}")
    return report_text


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} file1.enex [file2.enex ...]", file=sys.stderr)
        print(f"  Imports Evernote notes into DocManFu.", file=sys.stderr)
        print(f"  Generates a markdown report of any skipped/failed notes.", file=sys.stderr)
        sys.exit(1)

    # Determine upload dir from settings
    try:
        from app.core.config import settings
        upload_dir = settings.UPLOAD_DIR
    except Exception:
        upload_dir = "uploads"

    all_stats = []
    for filepath in sys.argv[1:]:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}", file=sys.stderr)
            continue
        stats = import_enex(filepath, upload_dir)
        all_stats.append(stats)

    # Generate report
    if all_stats:
        report_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            f"evernote-import-report.md",
        )
        generate_report(all_stats, report_path)


if __name__ == "__main__":
    main()
