"""Seed the database with sample documents, tags, and processing jobs."""

import uuid
from datetime import datetime, timezone, timedelta

from app.db.session import SessionLocal
from app.models import Document, Tag, ProcessingJob, JobType, JobStatus

now = datetime.now(timezone.utc)


def seed():
    db = SessionLocal()
    try:
        # Tags
        tags = [
            Tag(id=uuid.uuid4(), name="Invoice", color="#FF5733", created_at=now),
            Tag(id=uuid.uuid4(), name="Receipt", color="#33FF57", created_at=now),
            Tag(id=uuid.uuid4(), name="Contract", color="#3357FF", created_at=now),
            Tag(id=uuid.uuid4(), name="Report", color="#F033FF", created_at=now),
            Tag(id=uuid.uuid4(), name="Personal", color="#33FFF0", created_at=now),
        ]
        for tag in tags:
            db.add(tag)
        db.flush()

        # Documents
        docs = [
            Document(
                id=uuid.uuid4(),
                filename="electric_bill_jan_2026.pdf",
                original_name="scan_001.pdf",
                content_text="Electric bill for January 2026. Account #12345. Amount due: $142.50",
                ai_generated_name="Electric Bill - January 2026",
                file_path="/uploads/electric_bill_jan_2026.pdf",
                mime_type="application/pdf",
                file_size=245_000,
                upload_date=now - timedelta(days=5),
                processed_date=now - timedelta(days=5, hours=-1),
                created_at=now - timedelta(days=5),
                updated_at=now - timedelta(days=5),
            ),
            Document(
                id=uuid.uuid4(),
                filename="contractor_agreement_2026.pdf",
                original_name="IMG_20260201.pdf",
                content_text="Independent Contractor Agreement between Acme Corp and Jane Doe...",
                ai_generated_name="Contractor Agreement - Acme Corp 2026",
                file_path="/uploads/contractor_agreement_2026.pdf",
                mime_type="application/pdf",
                file_size=512_000,
                upload_date=now - timedelta(days=3),
                processed_date=now - timedelta(days=3, hours=-1),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=3),
            ),
            Document(
                id=uuid.uuid4(),
                filename="grocery_receipt.jpg",
                original_name="photo_receipt.jpg",
                content_text=None,
                ai_generated_name=None,
                file_path="/uploads/grocery_receipt.jpg",
                mime_type="image/jpeg",
                file_size=1_200_000,
                upload_date=now - timedelta(hours=2),
                processed_date=None,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
        ]
        for doc in docs:
            db.add(doc)
        db.flush()

        # Tag associations
        docs[0].tags.append(tags[0])  # Invoice
        docs[0].tags.append(tags[4])  # Personal
        docs[1].tags.append(tags[2])  # Contract
        docs[2].tags.append(tags[1])  # Receipt
        docs[2].tags.append(tags[4])  # Personal

        # Processing Jobs
        jobs = [
            ProcessingJob(
                id=uuid.uuid4(),
                document_id=docs[0].id,
                job_type=JobType.ocr,
                status=JobStatus.completed,
                progress=100,
                created_at=now - timedelta(days=5),
                started_at=now - timedelta(days=5, seconds=-10),
                completed_at=now - timedelta(days=5, seconds=-45),
            ),
            ProcessingJob(
                id=uuid.uuid4(),
                document_id=docs[0].id,
                job_type=JobType.ai_analysis,
                status=JobStatus.completed,
                progress=100,
                created_at=now - timedelta(days=5, seconds=-45),
                started_at=now - timedelta(days=5, seconds=-50),
                completed_at=now - timedelta(days=5, hours=-1),
            ),
            ProcessingJob(
                id=uuid.uuid4(),
                document_id=docs[1].id,
                job_type=JobType.ocr,
                status=JobStatus.completed,
                progress=100,
                created_at=now - timedelta(days=3),
                started_at=now - timedelta(days=3, seconds=-5),
                completed_at=now - timedelta(days=3, seconds=-30),
            ),
            ProcessingJob(
                id=uuid.uuid4(),
                document_id=docs[2].id,
                job_type=JobType.ocr,
                status=JobStatus.pending,
                progress=0,
                created_at=now - timedelta(hours=2),
            ),
        ]
        for job in jobs:
            db.add(job)

        db.commit()
        print(f"Seeded {len(tags)} tags, {len(docs)} documents, {len(jobs)} processing jobs.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
