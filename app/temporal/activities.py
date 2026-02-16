from typing import List

from llama_index.core import Document
from temporalio import activity

from app.core.minio import minio_handler
from app.models.workflows import (
    IngestionFilePayload,
    IngestionWorkflowRequest,
)
from app.service import IngestionService


class IngestionActivities:
    def __init__(self, ingestion_service: IngestionService) -> None:
        self._ingestion_service = ingestion_service

    @activity.defn(name="parse_files")
    async def parse_files(
        self, request: IngestionWorkflowRequest, files: List[IngestionFilePayload]
    ) -> list[Document]:
        """
        Activity 1: Returns the Markdown string.
        """
        results = []
        total_files = len(files)

        # We manually loop here instead of inside the service
        # so we can tell Temporal "I'm still alive!"
        for index, file in enumerate(files):
            # 1. Heartbeat to reset the "liveness" timer
            activity.heartbeat(
                f"Parsing file {index + 1}/{total_files}: {file.filename}"
            )

            file_stream = minio_handler.get_file_stream(object_name=file.object_name)

            # 2. Call the service logic for a SINGLE file
            batch_result = await self._ingestion_service.process_files(
                request=request, file=file_stream, file_name=file.filename or "default"
            )

            results.append(batch_result)

        return results

    @activity.defn(name="embed_markdown")
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
