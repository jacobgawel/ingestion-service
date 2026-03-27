import asyncio
import hashlib
import io
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.clients import get_minio_handler, get_temporal_client
from app.core.dependencies import get_ingestion_repository
from app.core.logger import get_logger
from app.core.temporal import INGESTION_WORKFLOW, WORKER_QUEUE
from app.models.api import (
    FileStatusResponse,
    IngestionRequest,
    IngestionResponse,
    JobStatusResponse,
)
from app.models.workflows import (
    IngestionFilePayload,
    IngestionWorkflowDTO,
    IngestionWorkflowRequest,
)
from app.repositories import IngestionRepository

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
logger = get_logger("IngestionRoute")


@router.post(
    "/ingest",
    summary="Ingest Data",
    description="Responsible for ingesting data",
    response_model=IngestionResponse,
)
async def ingest_data(
    request_data: IngestionRequest = Depends(IngestionRequest.as_form),
    files: List[UploadFile] = File(...),
    repo: IngestionRepository = Depends(get_ingestion_repository),
) -> IngestionResponse:
    logger.info(
        f"Received ingestion request: source={request_data.source}, project_id={request_data.project_id}, files={len(files)}"
    )
    client = get_temporal_client()
    minio = get_minio_handler()

    job_id = f"ingest-{uuid.uuid4()}"
    file_payloads: list[IngestionFilePayload] = []

    if request_data.project_id is None:
        request_data.project_id = str(uuid.uuid4())

    try:
        # Phase 1: Upload all files to MinIO
        for file_data in files:
            file_bytes = await file_data.read()
            size = len(file_bytes)
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            # 1. GENERATE UNIQUE OBJECT NAME
            unique_prefix = uuid.uuid4()
            file_name = file_data.filename

            object_path = (
                f"{request_data.project_id}/{unique_prefix}-{Path(file_name).stem}"  # type: ignore
            )
            object_url = f"/{object_path}/{file_name}"

            # 2. UPLOAD TO MINIO
            await asyncio.to_thread(
                minio.upload_file,
                file_data=io.BytesIO(file_bytes),
                object_name=object_url,
            )

            # 3. PREPARE PAYLOAD
            file_payloads.append(
                IngestionFilePayload(
                    filename=str(file_name),
                    object_url=object_url,
                    content_type=file_data.content_type,
                    file_size=size,
                    object_path=object_path,
                    file_hash=file_hash,
                )
            )

        logger.info(f"Finished uploading: {len(files)} files")

        # Phase 3: Build workflow DTO
        workflow_dto = IngestionWorkflowDTO(
            job_id=job_id,
            request=IngestionWorkflowRequest(**request_data.model_dump()),
            files=file_payloads,
        )

        # Phase 4: Create DB records
        await repo.create_job(
            job_id=job_id,
            source=workflow_dto.source,
            project_id=request_data.project_id,
            total_files=len(file_payloads),
        )

        for payload in file_payloads:
            unique_prefix = await repo.create_file(
                job_id=job_id,
                project_id=request_data.project_id,
                source=workflow_dto.source,
                filename=payload.filename,
                object_name=payload.object_url,
                content_type=payload.content_type,
            )

            await repo.create_document(
                file_id=unique_prefix,
                job_id=job_id,
                project_id=request_data.project_id,
                source=workflow_dto.source,
                filename=payload.filename,
                content_type=payload.content_type,
                file_size=payload.file_size,
                object_name=payload.object_url,
                file_hash=payload.file_hash,
            )

            payload.file_id = unique_prefix

        # Phase 5: Start Temporal workflow
        handle = await client.start_workflow(
            INGESTION_WORKFLOW.WORKFLOW,
            args=[workflow_dto],
            id=job_id,
            task_queue=WORKER_QUEUE.INGESTION,
        )

        return IngestionResponse(
            status="started",
            job_id=job_id,
            run_id=handle.run_id,
            message="File uploaded and ingestion workflow triggered.",
        )
    except Exception as e:
        logger.error(f"Ingestion request failed: {e}")
        raise


@router.get(
    "/ingest/{job_id}",
    summary="Get Job Status",
    description="Get the status of an ingestion job and its files",
    response_model=JobStatusResponse,
)
async def get_job_status(
    job_id: str,
    repo: IngestionRepository = Depends(get_ingestion_repository),
) -> JobStatusResponse:
    job = await repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    files = await repo.get_job_files(job_id)

    return JobStatusResponse(
        **job,
        files=[FileStatusResponse(**f) for f in files],
    )
