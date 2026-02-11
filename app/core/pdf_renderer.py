"""PDF page renderer for vision-based AI analysis.

Renders PDF pages to base64-encoded PNG images using pymupdf.
"""

import base64
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def render_pdf_pages(
    pdf_path: str,
    max_pages: int | None = None,
    dpi: int | None = None,
) -> list[str]:
    """Render PDF pages to base64-encoded PNG strings.

    Args:
        pdf_path: Path to the PDF file on disk.
        max_pages: Maximum number of pages to render (default: AI_MAX_PAGES).
        dpi: Render resolution (default: AI_VISION_DPI).

    Returns:
        List of base64-encoded PNG strings, one per page.

    Raises:
        FileNotFoundError: If the PDF file doesn't exist.
        RuntimeError: If rendering fails.
    """
    import fitz  # pymupdf

    if max_pages is None:
        max_pages = settings.AI_MAX_PAGES
    if dpi is None:
        dpi = settings.AI_VISION_DPI

    zoom = dpi / 72.0  # pymupdf default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF: {exc}") from exc

    images = []
    try:
        page_count = min(len(doc), max_pages)
        for i in range(page_count):
            page = doc[i]
            pix = page.get_pixmap(matrix=matrix)
            png_bytes = pix.tobytes("png")
            images.append(base64.b64encode(png_bytes).decode("ascii"))

        logger.info("Rendered %d pages from %s at %d DPI", page_count, pdf_path, dpi)
    finally:
        doc.close()

    return images
