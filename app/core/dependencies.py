from fastapi import Depends
from mixedbread import AsyncMixedbread
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from app.clients import get_openai_client
from app.clients import get_qdrant_client
from app.clients import get_mixedbread_client
from app.service import IngestionService


def get_ingestion_service(
    qdrant_client: AsyncQdrantClient = Depends(get_qdrant_client),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
    mixedbread_client: AsyncMixedbread = Depends(get_mixedbread_client),
) -> IngestionService:
    return IngestionService(
        qdrant_client=qdrant_client,
        openai_client=openai_client,
        mixedbread_client=mixedbread_client,
    )
