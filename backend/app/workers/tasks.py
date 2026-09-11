import asyncio
import uuid

from backend.app.core.database import AsyncSessionLocal
from backend.app.services.pdf_compiler import compile_and_upload_prescription_pdf
from backend.app.workers.celery_app import celery_app


def _run_async(coro):
    """Run an async coroutine from a sync Celery worker process."""
    return asyncio.run(coro)


@celery_app.task(name="generate_prescription_pdf_task", bind=True, max_retries=3)
def generate_prescription_pdf_task(self, prescription_id: str) -> str:
    """Celery task: compile prescription PDF and upload to S3."""

    async def _work() -> str:
        async with AsyncSessionLocal() as session:
            return await compile_and_upload_prescription_pdf(
                uuid.UUID(prescription_id),
                session,
            )

    try:
        return _run_async(_work())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5) from exc
