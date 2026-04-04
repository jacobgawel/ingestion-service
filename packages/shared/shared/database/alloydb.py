"""AlloyDB engine for executing SQL queries."""

from typing import Any

import asyncpg

from shared.core.logger import get_logger

logger = get_logger("AlloyEngine")


class AlloyDBEngine:
    """Query execution layer for AlloyDB (PostgreSQL) via asyncpg."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool: asyncpg.Pool = pool
        logger.info("AlloyDBEngine initialized")

    async def execute(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SQL query and return all rows."""
        logger.info(f"Executing SQL query: {query}")
        async with self._pool.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, *(params or []))
        logger.info(f"Query returned {len(rows)} rows")
        return [dict(row) for row in rows]

    async def execute_one(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute a SQL query and return the first row."""
        logger.info(f"Executing SQL query (single row): {query}")
        async with self._pool.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(query, *(params or []))
        if row is None:
            logger.info("Query returned no rows")
            return None
        logger.info("Query returned 1 row")
        return dict(row)

    async def execute_write(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> str:
        """Execute a SQL write operation (INSERT, UPDATE, DELETE). Returns status string."""
        logger.info(f"Executing SQL write: {query}")
        async with self._pool.acquire() as conn:
            status: str = await conn.execute(query, *(params or []))
        logger.info(f"Write operation completed: {status}")
        return status

    async def execute_many(
        self,
        query: str,
        params: list[list[Any]],
    ) -> None:
        """Execute a SQL write operation for many rows."""
        logger.info(f"Executing SQL batch write: {query} ({len(params)} rows)")
        async with self._pool.acquire() as conn:
            await conn.executemany(query, params)
        logger.info("Batch write completed")

    async def execute_in_transaction(
        self,
        queries: list[tuple[str, list[Any] | None]],
    ) -> None:
        """Execute multiple queries within a single transaction."""
        logger.info(f"Executing transaction with {len(queries)} queries")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for query, params in queries:
                    await conn.execute(query, *(params or []))
        logger.info("Transaction completed")
