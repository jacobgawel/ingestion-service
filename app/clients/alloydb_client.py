"""AlloyDB client singleton instance."""

from typing import Optional

import asyncpg

from app.core.logger import get_logger
from app.core.settings import config

logger = get_logger("AlloyDBManager")


class AlloyDBManager:
    """Singleton class for AlloyDB client to ensure single instance across the application."""

    _instance: Optional["AlloyDBManager"] = None
    _pool: Optional[asyncpg.Pool] = None
    _initialized: bool = False

    def __new__(cls) -> "AlloyDBManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """Initialize the AlloyDB connection pool. Must be called during app startup."""
        if not self.__class__._initialized:
            self._pool = await asyncpg.create_pool(
                host=config.ALLOYDB_HOST,
                port=config.ALLOYDB_PORT,
                database=config.ALLOYDB_DATABASE,
                user=config.ALLOYDB_USER,
                password=config.ALLOYDB_PASSWORD,
            )

            await self._create_schema()

            logger.info("AlloyDB client initialized successfully")
            self.__class__._initialized = True

    async def _create_schema(self) -> None:
        """Create extensions and tables if they don't exist."""
        if self._pool is None:
            raise RuntimeError("Cannot create schema: pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    file_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    job_id       TEXT NOT NULL,
                    source       TEXT,
                    project_id   TEXT,
                    filename     TEXT NOT NULL,
                    content_type TEXT,
                    markdown     TEXT,
                    page_count   INTEGER,
                    file_size    BIGINT,
                    created_at   TIMESTAMPTZ DEFAULT now(),
                    object_name  TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    file_id      UUID NOT NULL REFERENCES documents(file_id) ON DELETE CASCADE,
                    chunk_index  INTEGER NOT NULL,
                    content      TEXT NOT NULL,
                    heading      TEXT,
                    embedding    vector(1536),
                    token_count  INTEGER,
                    created_at   TIMESTAMPTZ DEFAULT now()
                )
            """)

        logger.info("AlloyDB schema created (documents + document_chunks)")

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the AlloyDB connection pool."""
        if self._pool is None:
            raise RuntimeError(
                "AlloyDB client not initialized. Call 'await alloydb_manager.initialize()' first."
            )
        return self._pool

    async def close(self) -> None:
        """Close the AlloyDB connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("AlloyDB client shut down")
            self.__class__._initialized = False
            self.__class__._instance = None
            self._pool = None


# Create a singleton instance
_alloydb_singleton = AlloyDBManager()


async def initialize_alloydb() -> None:
    """Initialize the AlloyDB singleton client."""
    await _alloydb_singleton.initialize()


async def close_alloydb() -> None:
    """Close the AlloyDB singleton client."""
    await _alloydb_singleton.close()


def get_alloydb_pool() -> asyncpg.Pool:
    """
    Get the singleton AlloyDB connection pool.

    Returns:
        asyncpg.Pool: The singleton AlloyDB connection pool.
    """
    return _alloydb_singleton.pool
