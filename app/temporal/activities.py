import asyncio
from typing import List

from llama_index.core import Document
from temporalio import activity

from app.clients import get_minio_handler
from app.clients.minio_client import MinioManager
from app.core.enums import INGESTION_STATUS
from app.core.logger import get_logger
from app.core.temporal import INGESTION_ACTIVITY
from app.models.workflows import (
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
    ) -> None:
        self._ingestion_service = ingestion_service
        self.minio_handler = minio_handler
        self._repo = ingestion_repository

    def _download_and_parse_sync(
        self, request: IngestionWorkflowRequest, file_payload: IngestionFilePayload
    ) -> Document:
        """Synchronous function to download and parse file data"""

        file_stream = get_minio_handler().get_file_stream(
            object_name=file_payload.object_name
        )
        return self._ingestion_service.process_file(
            request=request,
            file=file_stream,
            file_name=file_payload.filename or "default",
        )

    @activity.defn(name=INGESTION_ACTIVITY.PARSE_FILES)
    async def parse_files(
        self,
        job_id: str,
        request: IngestionWorkflowRequest,
        files: List[IngestionFilePayload],
    ) -> list[Document]:
        """
        Activity 1: Returns the Markdown string.
        """

        total_files = len(files)

        # Determine concurrency limit (e.g., process 4 files at a time)
        semaphore = asyncio.Semaphore(4)

        async def _process_single_file(
            index: int, file_payload: IngestionFilePayload
        ) -> Document | None:
            async with semaphore:
                activity.heartbeat(
                    f"Parsing file {index + 1}/{total_files}: {file_payload.filename}"
                )

                try:
                    doc = await asyncio.to_thread(
                        self._download_and_parse_sync, request, file_payload
                    )

                    if file_payload.file_id:
                        await self._repo.update_file_status(
                            job_id=job_id,
                            file_id=file_payload.file_id,
                            status=INGESTION_STATUS.COMPLETED,
                        )

                    return doc
                except Exception as e:
                    logger.error(f"Failed to parse file {file_payload.filename}: {e}")

                    if file_payload.file_id:
                        await self._repo.update_file_status(
                            job_id=job_id,
                            file_id=file_payload.file_id,
                            status=INGESTION_STATUS.FAILED,
                            error_message=str(e),
                        )

                    return None

        # Create tasks for all files
        tasks = [_process_single_file(i, file) for i, file in enumerate(files)]

        # Run them concurrently
        results = await asyncio.gather(*tasks)

        # Filter out failed files (None values)
        return [doc for doc in results if doc is not None]

    @activity.defn(name=INGESTION_ACTIVITY.EMBED_MARKDOWN)
    async def embed_markdown(
        self,
        request: IngestionWorkflowRequest,
        processed_files: list[Document],
    ) -> str:
        """
        Activity 2: Takes Markdown, returns Status.
        """
        await self._ingestion_service.embed_markdown(
            request=request,
            processed_files=processed_files,
        )
        return "Success"

    @activity.defn(name=INGESTION_ACTIVITY.FINALIZE_JOB)
    async def finalize_job(
        self,
        job_id: str,
        status: str,
        error_message: str | None,
    ) -> None:
        """
        Activity 3: Finalize the job status in ScyllaDB.
        """
        await self._repo.finalize_job(
            job_id=job_id,
            status=status,
            error_message=error_message,
        )
