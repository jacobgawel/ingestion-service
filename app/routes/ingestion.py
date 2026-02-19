import asyncio
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.clients import get_minio_handler, get_temporal_client
from app.core.logger import get_logger
from app.core.temporal import INGESTION_WORKFLOW, WORKER_QUEUE
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
    client = get_temporal_client()
    minio = get_minio_handler()

    file_payloads = []

    try:
        # Phase 1: Load all files into memory
        files_in_memory = []

        for file in files:
            file.file.seek(0)
            file_content = file.file.read()
            files_in_memory.append(
                {
                    "filename": file.filename,
                    "content": file_content,
                    "content_type": file.content_type,
                    "size": len(file_content),
                }
            )

        logger.info(f"Loaded {len(files_in_memory)} files into memory")

        # Phase 2: Upload all files
        for file_data in files_in_memory:
            # 1. GENERATE UNIQUE OBJECT NAME
            object_name = (
                f"{request_data.project_id}/{uuid.uuid4()}-{file_data['filename']}"
            )

            # 2. UPLOAD TO MINIO
            await asyncio.to_thread(
                minio.upload_file,
                file_data=file_data["content"],
                size=file_data["size"],
                object_name=object_name,
            )

            # 3. PREPARE PAYLOAD
            file_payloads.append(
                IngestionFilePayload(
                    filename=file_data["filename"],
                    object_name=object_name,
                    content_type=file_data["content_type"],
                )
            )

        handle = await client.start_workflow(
            INGESTION_WORKFLOW.INGESTION_WORFKLOW,
            args=[
                IngestionWorkflowDTO(
                    request=IngestionWorkflowRequest(**request_data.model_dump()),
                    files=file_payloads,
                )
            ],
            id=f"ingest-{uuid.uuid4()}",  # Unique ID prevents duplicate jobs
            task_queue=WORKER_QUEUE.INGESTION,  # Task Queue for the worker
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
