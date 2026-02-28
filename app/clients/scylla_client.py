"""ScyllaDB client singleton instance."""

from typing import Optional

from scyllapy import Scylla

from app.core.logger import get_logger
from app.core.settings import config

logger = get_logger("ScyllaManager")


class ScyllaManager:
    """Singleton class for ScyllaDB client to ensure single instance across the application."""

    _instance: Optional["ScyllaManager"] = None
    _client: Optional[Scylla] = None
    _initialized: bool = False

    def __new__(cls) -> "ScyllaManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _create_client(self) -> Scylla:
        """Create and configure the ScyllaDB client."""
        contact_points: list[str] = [
            host.strip() for host in config.SCYLLA_HOSTS.split(",")
        ]

        kwargs: dict = {"contact_points": contact_points}

        if config.SCYLLA_KEYSPACE:
            kwargs["default_keyspace"] = config.SCYLLA_KEYSPACE

        if config.SCYLLA_USERNAME and config.SCYLLA_PASSWORD:
            kwargs["username"] = config.SCYLLA_USERNAME
            kwargs["password"] = config.SCYLLA_PASSWORD

        return Scylla(**kwargs)

    async def initialize(self) -> None:
        """Initialize the ScyllaDB client. Must be called during app startup."""
        if not self.__class__._initialized:
            self._client = self._create_client()
            await self._client.startup()
            logger.info("ScyllaDB client initialized successfully")
            self.__class__._initialized = True

    @property
    def client(self) -> Scylla:
        """Get the ScyllaDB client instance."""
        if self._client is None:
            raise RuntimeError(
                "ScyllaDB client not initialized. Call 'await scylla_manager.initialize()' first."
            )
        return self._client

    async def close(self) -> None:
        """Close the ScyllaDB client connection."""
        if self._client:
            await self._client.shutdown()
            logger.info("ScyllaDB client shut down")
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


# Create a singleton instance
_scylla_singleton = ScyllaManager()


async def initialize_scylla() -> None:
    """Initialize the ScyllaDB singleton client."""
    await _scylla_singleton.initialize()


async def close_scylla() -> None:
    """Close the ScyllaDB singleton client."""
    await _scylla_singleton.close()


def get_scylla_client() -> Scylla:
    """
    Get the singleton ScyllaDB client instance.

    Returns:
        Scylla: The singleton ScyllaDB client instance.
    """
    return _scylla_singleton.client
