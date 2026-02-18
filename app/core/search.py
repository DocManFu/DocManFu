"""Full-text search utilities for document search_vector maintenance."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def update_search_vector(db: Session, document_id) -> None:
    """Recompute the tsvector for a single document."""
    db.execute(
        text("""
            UPDATE documents SET search_vector = to_tsvector('english',
                coalesce(content_text, '') || ' ' ||
                coalesce(original_name, '') || ' ' ||
                coalesce(ai_generated_name, '') || ' ' ||
                coalesce(ai_metadata->>'summary', '') || ' ' ||
                coalesce(ai_metadata->>'company', '')
            )
            WHERE id = :doc_id
            """),
        {"doc_id": str(document_id)},
    )
    db.commit()
