from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.dependencies import get_ingestion_service
from app.core.logger import get_logger
from app.models.api import IngestionRequest
from app.service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
logger = get_logger("IngestionRoute")


@router.post(
    "/ingest",
    summary="Ingest Data",
    description="Responsible for ingesting data",
)
async def ingest_data(
    service: IngestionService = Depends(get_ingestion_service),
    request_data: IngestionRequest = Depends(IngestionRequest.as_form),
    files: List[UploadFile] = File(...),
) -> bool:
    logger.info(
        f"Received ingestion request: user_id={request_data.user_id}, project_id={request_data.project_id}, files={len(files)}"
    )
    try:
        result = await service.process_pipeline(request=request_data, files=files)
        logger.info("Ingestion request completed successfully")
        return result
    except Exception as e:
        logger.error(f"Ingestion request failed: {e}")
        raise
