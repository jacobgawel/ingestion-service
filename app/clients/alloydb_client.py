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
            logger.info("AlloyDB client initialized successfully")
            self.__class__._initialized = True

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
