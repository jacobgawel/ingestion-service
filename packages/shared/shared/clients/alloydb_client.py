"""AlloyDB client singleton instance."""

import asyncpg

from shared.clients.base import ClientManager
from shared.core.logger import get_logger
from shared.core.settings import config

logger = get_logger("AlloyDBManager")


class AlloyDBManager(ClientManager[asyncpg.Pool]):
    """Singleton manager for the AlloyDB connection pool."""

    async def _create_client(self) -> asyncpg.Pool:
        pool = await asyncpg.create_pool(
            host=config.ALLOYDB_HOST,
            port=config.ALLOYDB_PORT,
            database=config.ALLOYDB_DATABASE,
            user=config.ALLOYDB_USER,
            password=config.ALLOYDB_PASSWORD,
        )
        await self._create_schema(pool)
        logger.info("AlloyDB client initialized successfully")
        return pool

    async def _create_schema(self, pool: asyncpg.Pool) -> None:
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # -- Job tracking --

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id          TEXT PRIMARY KEY,
                    source          TEXT NOT NULL,
                    project_id      TEXT,
                    status          TEXT NOT NULL,
                    total_files     INTEGER NOT NULL DEFAULT 0,
                    files_completed INTEGER NOT NULL DEFAULT 0,
                    files_failed    INTEGER NOT NULL DEFAULT 0,
                    created_at      TIMESTAMPTZ DEFAULT now(),
                    updated_at      TIMESTAMPTZ DEFAULT now(),
                    error_message   TEXT
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_source
                ON ingestion_jobs (source)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_project_id
                ON ingestion_jobs (project_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status
                ON ingestion_jobs (status)
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_files (
                    file_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    job_id        TEXT NOT NULL REFERENCES ingestion_jobs(job_id) ON DELETE CASCADE,
                    project_id    TEXT,
                    source        TEXT,
                    filename      TEXT,
                    object_name   TEXT NOT NULL,
                    content_type  TEXT,
                    status        TEXT NOT NULL,
                    created_at    TIMESTAMPTZ DEFAULT now(),
                    updated_at    TIMESTAMPTZ DEFAULT now(),
                    error_message TEXT
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_files_job_id
                ON ingestion_files (job_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_files_source
                ON ingestion_files (source)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_files_project_id
                ON ingestion_files (project_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_files_status
                ON ingestion_files (status)
            """)

            # -- Document storage --

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
                    object_name  TEXT NOT NULL,
                    hash         TEXT
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_hash
                ON documents (hash)
                WHERE hash IS NOT NULL
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

        logger.info("AlloyDB schema created")

    async def _close_client(self) -> None:
        await self.client.close()
        logger.info("AlloyDB client shut down")

    @property
    def pool(self) -> asyncpg.Pool:
        return self.client


_alloydb_singleton = AlloyDBManager()


def get_alloydb_pool() -> asyncpg.Pool:
    return _alloydb_singleton.pool
