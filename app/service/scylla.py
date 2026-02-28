"""ScyllaDB service for executing CQL queries."""

from typing import Any

from scyllapy import Scylla

from app.core.logger import get_logger

logger = get_logger("ScyllaService")


class ScyllaService:
    """Service layer for ScyllaDB query execution."""

    def __init__(self, scylla_client: Scylla) -> None:
        self.client: Scylla = scylla_client
        logger.info("ScyllaService initialized")

    async def execute(
        self, query: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a CQL query and return all rows.

        Args:
            query: CQL query string.
            params: Optional list of positional query parameters.

        Returns:
            List of rows, where each row is a dictionary mapping column names to values.
        """
        logger.info(f"Executing CQL query: {query}")

        if params:
            result = await self.client.execute(query, params)
        else:
            result = await self.client.execute(query)

        rows: list[dict[str, Any]] = result.all()
        logger.info(f"Query returned {len(rows)} rows")
        return rows

    async def execute_one(
        self, query: str, params: list[Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Execute a CQL query and return the first row.

        Args:
            query: CQL query string.
            params: Optional list of positional query parameters.

        Returns:
            The first row as a dictionary, or None if no rows were returned.
        """
        logger.info(f"Executing CQL query (single row): {query}")

        if params:
            result = await self.client.execute(query, params)
        else:
            result = await self.client.execute(query)

        row: dict[str, Any] | None = result.first()
        logger.info(f"Query returned {'1 row' if row else 'no rows'}")
        return row

    async def execute_write(
        self, query: str, params: list[Any] | None = None
    ) -> None:
        """
        Execute a CQL write operation (INSERT, UPDATE, DELETE).

        Args:
            query: CQL mutation query string.
            params: Optional list of positional query parameters.
        """
        logger.info(f"Executing CQL write: {query}")

        if params:
            await self.client.execute(query, params)
        else:
            await self.client.execute(query)

        logger.info("Write operation completed")
