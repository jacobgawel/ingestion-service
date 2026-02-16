import asyncio
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from app.core.logger import get_logger
from app.core.minio import minio_handler
from app.models.api import IngestionRequest
from app.models.workflows import (
    IngestionFilePayload,
    IngestionWorkflowDTO,
    IngestionWorkflowRequest,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
logger = get_logger("IngestionRoute")


@router.post(
    "/ingest",
    summary="Ingest Data",
    description="Responsible for ingesting data",
)
async def ingest_data(
    request_data: IngestionRequest = Depends(IngestionRequest.as_form),
    files: List[UploadFile] = File(...),
) -> dict[str, str | None]:
    logger.info(
        f"Received ingestion request: user_id={request_data.user_id}, project_id={request_data.project_id}, files={len(files)}"
    )
    client = await Client.connect(
        "localhost:7233", data_converter=pydantic_data_converter
    )
    file_payloads = []

    try:
        for file in files:
            # 1. GENERATE UNIQUE OBJECT NAME
            object_name = f"{request_data.project_id}/{uuid.uuid4()}-{file.filename}"

            # 2. GET FILE SIZE (Required for MinIO put_object)
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            # 3. UPLOAD TO MINIO
            await asyncio.to_thread(
                minio_handler.upload_file,
                file_data=file.file,
                size=file_size,
                object_name=object_name,
            )

            # 4. PREPARE PAYLOAD
            file_payloads.append(
                IngestionFilePayload(
                    filename=file.filename,
                    object_name=object_name,
                    content_type=file.content_type,
                )
            )

        handle = await client.start_workflow(
            "IngestionWorkflow",
            args=[
                IngestionWorkflowDTO(
                    request=IngestionWorkflowRequest(**request_data.model_dump()),
                    files=file_payloads,
                )
            ],
            id=f"ingest-{uuid.uuid4()}",  # Unique ID prevents duplicate jobs
            task_queue="ingestion-queue",  # Task Queue for the worker
        )
        return {
            "status": "started",
            "workflow_id": handle.id,
            "run_id": handle.run_id,
            "message": "File uploaded and ingestion workflow triggered.",
        }
    except Exception as e:
        logger.error(f"Ingestion request failed: {e}")
        raise
