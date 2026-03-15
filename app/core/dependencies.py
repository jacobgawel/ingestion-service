import asyncpg
from cassandra.cluster import Session
from fastapi import Depends
from mixedbread import AsyncMixedbread
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.clients import (
    get_alloydb_pool,
    get_mixedbread_client,
    get_openai_client,
    get_qdrant_client,
    get_scylla_session,
)
from app.database import AlloyDBEngine, ScyllaEngine
from app.repositories import IngestionRepository
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


def get_scylla_engine(
    session: Session = Depends(get_scylla_session),
) -> ScyllaEngine:
    return ScyllaEngine(session=session)


def get_alloydb_engine(pool: asyncpg.Pool = Depends(get_alloydb_pool)):
    return AlloyDBEngine(pool=pool)


def get_ingestion_repository(
    scylla: ScyllaEngine = Depends(get_scylla_engine),
    alloydb: AlloyDBEngine = Depends(get_alloydb_engine),
) -> IngestionRepository:
    return IngestionRepository(scylla=scylla, alloydb=alloydb)
