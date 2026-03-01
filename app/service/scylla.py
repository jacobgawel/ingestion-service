"""ScyllaDB service for executing CQL queries."""

import asyncio
from typing import Any

from cassandra.cluster import ResponseFuture, Session

from app.core.logger import get_logger

logger = get_logger("ScyllaService")


class ScyllaService:
    """Service layer for ScyllaDB query execution."""

    def __init__(self, session: Session) -> None:
        self.session: Session = session
        logger.info("ScyllaService initialized")

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
        """
        Execute a CQL query and return all rows.

        Args:
            query: CQL query string.
            params: Optional positional or named query parameters.

        Returns:
            List of rows, where each row is a dictionary mapping column names to values.
        """
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
        """
        Execute a CQL query and return the first row.

        Args:
            query: CQL query string.
            params: Optional positional or named query parameters.

        Returns:
            The first row as a dictionary, or None if no rows were returned.
        """
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
        """
        Execute a CQL write operation (INSERT, UPDATE, DELETE).

        Args:
            query: CQL mutation query string.
            params: Optional positional or named query parameters.
        """
        logger.info(f"Executing CQL write: {query}")

        response_future = self.session.execute_async(query, params)
        await self._await_future(response_future)

        logger.info("Write operation completed")
