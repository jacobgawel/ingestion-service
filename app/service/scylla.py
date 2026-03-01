"""ScyllaDB service for executing CQL queries."""

import asyncio
from typing import Any

from cassandra.cluster import ResponseFuture, Session
from cassandra.query import PreparedStatement

from app.core.logger import get_logger

logger = get_logger("ScyllaService")


class ScyllaService:
    """Service layer for ScyllaDB query execution."""

    def __init__(self, session: Session) -> None:
        self.session: Session = session
        self._prepared_cache: dict[str, PreparedStatement] = {}
        logger.info("ScyllaService initialized")

    def _prepare(self, query: str) -> PreparedStatement:
        """Get or create a prepared statement for the given query."""
        if query not in self._prepared_cache:
            self._prepared_cache[query] = self.session.prepare(query)
        return self._prepared_cache[query]

    async def _await_future(self, response_future: ResponseFuture) -> Any:
        """Bridge a cassandra ResponseFuture to an asyncio awaitable."""
        loop = asyncio.get_running_loop()
        asyncio_future: asyncio.Future[Any] = loop.create_future()

        def on_success(result: Any) -> None:
            loop.call_soon_threadsafe(asyncio_future.set_result, result)

        def on_error(exc: BaseException) -> None:
            loop.call_soon_threadsafe(asyncio_future.set_exception, exc)

        response_future.add_callbacks(on_success, on_error)
        return await asyncio_future

    async def execute(
        self,
        query: str,
        params: list[Any] | tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a CQL query and return all rows."""
        logger.info(f"Executing CQL query: {query}")

        response_future = self.session.execute_async(query, params)
        result_set = await self._await_future(response_future)

        rows: list[dict[str, Any]] = [row._asdict() for row in result_set]
        logger.info(f"Query returned {len(rows)} rows")
        return rows

    async def execute_one(
        self,
        query: str,
        params: list[Any] | tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute a CQL query and return the first row."""
        logger.info(f"Executing CQL query (single row): {query}")

        response_future = self.session.execute_async(query, params)
        result_set = await self._await_future(response_future)

        first = next(iter(result_set), None)
        if first is None:
            logger.info("Query returned no rows")
            return None

        result: dict[str, Any] = first._asdict()
        logger.info("Query returned 1 row")
        return result

    async def execute_write(
        self,
        query: str,
        params: list[Any] | tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> None:
        """Execute a CQL write operation (INSERT, UPDATE, DELETE)."""
        logger.info(f"Executing CQL write: {query}")

        response_future = self.session.execute_async(query, params)
        await self._await_future(response_future)

        logger.info("Write operation completed")

    # --- Prepared statement variants ---

    async def execute_prepared(
        self, query: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a prepared CQL query and return all rows."""
        stmt = self._prepare(query)
        response_future = self.session.execute_async(stmt, params)
        result_set = await self._await_future(response_future)
        return [row._asdict() for row in result_set]

    async def execute_prepared_one(
        self, query: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Execute a prepared CQL query and return the first row."""
        stmt = self._prepare(query)
        response_future = self.session.execute_async(stmt, params)
        result_set = await self._await_future(response_future)
        first = next(iter(result_set), None)
        return first._asdict() if first is not None else None

    async def execute_prepared_write(
        self, query: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> None:
        """Execute a prepared CQL write operation."""
        stmt = self._prepare(query)
        response_future = self.session.execute_async(stmt, params)
        await self._await_future(response_future)
