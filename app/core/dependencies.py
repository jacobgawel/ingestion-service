import asyncpg
from fastapi import Depends
from openai import AsyncOpenAI

from app.clients import (
    get_alloydb_pool,
    get_openai_client,
)
from app.database import AlloyDBEngine
from app.repositories import IngestionRepository
from app.service import IngestionService


def get_ingestion_service(
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> IngestionService:
    return IngestionService(
        openai_client=openai_client,
    )


def get_alloydb_engine(pool: asyncpg.Pool = Depends(get_alloydb_pool)):
    return AlloyDBEngine(pool=pool)


def get_ingestion_repository(
    alloydb: AlloyDBEngine = Depends(get_alloydb_engine),
) -> IngestionRepository:
    return IngestionRepository(alloydb=alloydb)
