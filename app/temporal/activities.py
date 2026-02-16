import asyncio
from typing import List

from llama_index.core import Document
from temporalio import activity

from app.core.minio import minio_handler
from app.core.temporal import INGESTION_ACTIVITY
from app.models.workflows import (
    IngestionFilePayload,
    IngestionWorkflowRequest,
)
from app.service import IngestionService


class IngestionActivities:
    def __init__(self, ingestion_service: IngestionService) -> None:
        self._ingestion_service = ingestion_service

    def _download_and_parse_sync(
        self, request: IngestionWorkflowRequest, file_payload: IngestionFilePayload
    ) -> Document:
        """Synchronous function to download and parse file data"""

        file_stream = minio_handler.get_file_stream(
            object_name=file_payload.object_name
        )
        return self._ingestion_service.process_file(
            request=request,
            file=file_stream,
            file_name=file_payload.filename or "default",
        )

    @activity.defn(name=INGESTION_ACTIVITY.PARSE_FILES)
    async def parse_files(
        self, request: IngestionWorkflowRequest, files: List[IngestionFilePayload]
    ) -> list[Document]:
        """
        Activity 1: Returns the Markdown string.
        """

        total_files = len(files)

        # Determine concurrency limit (e.g., process 4 files at a time)
        semaphore = asyncio.Semaphore(4)

        async def _process_single_file(
            index: int, file_payload: IngestionFilePayload
        ) -> Document:
            async with semaphore:
                activity.heartbeat(
                    f"Parsing file {index + 1}/{total_files}: {file_payload.filename}"
                )

                # offload this to a thread
                return await asyncio.to_thread(
                    self._download_and_parse_sync, request, file_payload
                )

        # Create tasks for all files
        tasks = [_process_single_file(i, file) for i, file in enumerate(files)]

        # Run them concurrently
        results = await asyncio.gather(*tasks)

        return results

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
