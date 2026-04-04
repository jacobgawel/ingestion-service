import asyncpg
from fastapi import Depends

from shared.clients import get_alloydb_pool
from shared.database import AlloyDBEngine
from shared.repositories import IngestionRepository


def get_alloydb_engine(pool: asyncpg.Pool = Depends(get_alloydb_pool)):
    return AlloyDBEngine(pool=pool)


def get_ingestion_repository(
    alloydb: AlloyDBEngine = Depends(get_alloydb_engine),
) -> IngestionRepository:
    return IngestionRepository(alloydb=alloydb)
