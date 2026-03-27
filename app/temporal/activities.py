import asyncio
import gc
import json
import os
import tempfile
from typing import List

from nats.aio.client import Client as NATSClient
from temporalio import activity

from app.clients.minio_client import MinioManager
from app.core.enums import INGESTION_STATUS
from app.core.logger import get_logger
from app.core.settings import config
from app.core.temporal import INGESTION_ACTIVITY
from app.models.workflows import (
    FileProcessingContext,
    IngestionFilePayload,
    IngestionWorkflowRequest,
)
from app.repositories import IngestionRepository
from app.service import IngestionService

logger = get_logger("IngestionActivities")


class IngestionActivities:
    def __init__(
        self,
        ingestion_service: IngestionService,
        minio_handler: MinioManager,
        ingestion_repository: IngestionRepository,
        nats_client: NATSClient,
    ) -> None:
        self._ingestion_service = ingestion_service
        self.minio_handler = minio_handler
        self._repo = ingestion_repository
        self._nats = nats_client

    async def _publish(self, subject: str, payload: dict) -> None:
        """Publish a message to NATS, swallowing errors to avoid breaking workflows."""
        try:
            await self._nats.publish(subject, json.dumps(payload).encode())
        except Exception as e:
            logger.warning(f"Failed to publish NATS message to {subject}: {e}")

    async def _download_and_parse_sync(
        self, request: IngestionWorkflowRequest, file_payload: IngestionFilePayload
    ):
        """Download file to temp disk, parse to Document, then discard the file."""
        ext = os.path.splitext(file_payload.filename or "")[1]
        with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
            self.minio_handler.download_file(file_payload.object_url, tmp.name)

            ctx = FileProcessingContext.from_request(
                file_name=file_payload.filename or "default",
                request=request,
                file_path=tmp.name,
                object_path=file_payload.object_path,
                object_url=file_payload.object_url,
            )

            doc = await self._ingestion_service.process_file(ctx)

            if file_payload.file_id is not None:
                await self._repo.update_markdown_by_fileid(
                    markdown=doc.text, file_id=file_payload.file_id
                )

            return doc

    @activity.defn(name=INGESTION_ACTIVITY.PARSE_AND_EMBED)
    async def parse_and_embed(
        self,
        job_id: str,
        request: IngestionWorkflowRequest,
        files: List[IngestionFilePayload],
    ) -> str:
        """
        Activity: Download, parse, and embed each file one at a time.
        Returns a status string (no large payloads in Temporal history).
        """
        total_files = len(files)
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_FILES)

        async def _process_single_file(
            index: int, file_payload: IngestionFilePayload
        ) -> bool:
            async with semaphore:
                activity.heartbeat(
                    f"Processing file {index + 1}/{total_files}: {file_payload.filename}"
                )

                try:
                    # --- Deduplication: check for cached processing results ---
                    cached_hit = False
                    if file_payload.file_hash and file_payload.file_id:
                        cached = await self._repo.find_cached_document(
                            file_payload.file_hash
                        )
                        if cached:
                            source_file_id = cached["file_id"]
                            cached_markdown = cached["markdown"]
                            cached_chunks = await self._repo.get_chunks_by_file_id(
                                source_file_id
                            )

                            if cached_chunks:
                                logger.info(
                                    f"Cache hit for {file_payload.filename} "
                                    f"(hash={file_payload.file_hash[:12]}…, "
                                    f"source_doc={source_file_id})"
                                )

                                # Copy markdown to the new document
                                await self._repo.update_markdown_by_fileid(
                                    markdown=cached_markdown,
                                    file_id=file_payload.file_id,
                                )

                                # Insert cached chunks into AlloyDB for the new doc
                                await self._repo.insert_chunks(
                                    file_id=file_payload.file_id,
                                    chunks=cached_chunks,
                                )

                                await self._ingestion_service.reindex_cached_chunks(
                                    request, cached_chunks
                                )

                                del cached_chunks
                                gc.collect()
                                cached_hit = True

                    # --- Normal processing path (cache miss) ---
                    if not cached_hit:
                        doc = await self._download_and_parse_sync(
                            request=request, file_payload=file_payload
                        )

                        chunks = await self._ingestion_service.embed_single_document(
                            request, doc, is_image=file_payload.is_image
                        )

                        if file_payload.file_id and chunks:
                            await self._repo.insert_chunks(
                                file_id=file_payload.file_id, chunks=chunks
                            )

                        del doc, chunks
                        gc.collect()

                    if file_payload.file_id:
                        await self._repo.update_file_status(
                            job_id=job_id,
                            file_id=file_payload.file_id,
                            status=INGESTION_STATUS.COMPLETED,
                        )
                        await self._publish(
                            f"jobs.{job_id}",
                            {
                                "type": "file_update",
                                "job_id": job_id,
                                "file_id": str(file_payload.file_id),
                                "filename": file_payload.filename,
                                "status": INGESTION_STATUS.COMPLETED,
                            },
                        )

                    return True
                except Exception as e:
                    logger.error(f"Failed to process file {file_payload.filename}: {e}")

                    if file_payload.file_id:
                        await self._repo.update_file_status(
                            job_id=job_id,
                            file_id=file_payload.file_id,
                            status=INGESTION_STATUS.FAILED,
                            error_message=str(e),
                        )
                        await self._publish(
                            f"jobs.{job_id}",
                            {
                                "type": "file_update",
                                "job_id": job_id,
                                "file_id": str(file_payload.file_id),
                                "filename": file_payload.filename,
                                "status": INGESTION_STATUS.FAILED,
                            },
                        )

                    return False

        tasks = [_process_single_file(i, file) for i, file in enumerate(files)]
        results = await asyncio.gather(*tasks)

        succeeded = sum(1 for r in results if r)
        failed = total_files - succeeded
        return f"Processed {succeeded}/{total_files} files ({failed} failed)"

    @activity.defn(name=INGESTION_ACTIVITY.FINALIZE_JOB)
    async def finalize_job(
        self,
        job_id: str,
        source: str,
        status: str,
        error_message: str | None,
    ) -> None:
        """
        Activity: Finalize the job status.
        """
        await self._repo.finalize_job(
            job_id=job_id,
            source=source,
            status=status,
            error_message=error_message,
        )

        job = await self._repo.get_job(job_id)
        if job:
            await self._publish(
                f"jobs.{job_id}",
                {
                    "type": "job_update",
                    "job_id": job_id,
                    "status": status,
                    "total_files": job.get("total_files", 0),
                    "files_completed": job.get("files_completed", 0),
                    "files_failed": job.get("files_failed", 0),
                },
            )
