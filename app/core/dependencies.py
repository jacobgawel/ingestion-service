from cassandra.cluster import Session
from fastapi import Depends
from mixedbread import AsyncMixedbread
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.clients import (
    get_mixedbread_client,
    get_openai_client,
    get_qdrant_client,
    get_scylla_session,
)
from app.repositories import IngestionRepository
from app.service import IngestionService, ScyllaService


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


def get_scylla_service(
    session: Session = Depends(get_scylla_session),
) -> ScyllaService:
    return ScyllaService(session=session)


def get_ingestion_repository(
    scylla: ScyllaService = Depends(get_scylla_service),
) -> IngestionRepository:
    return IngestionRepository(scylla=scylla)
