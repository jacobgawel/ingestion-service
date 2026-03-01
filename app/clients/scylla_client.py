"""ScyllaDB client singleton instance."""

from typing import Any, Optional

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, Session
from cassandra.io.asyncioreactor import AsyncioConnection

from app.core.logger import get_logger
from app.core.settings import config

logger = get_logger("ScyllaManager")


class ScyllaManager:
    """Singleton class for ScyllaDB client to ensure single instance across the application."""

    _instance: Optional["ScyllaManager"] = None
    _cluster: Optional[Cluster] = None
    _session: Optional[Session] = None
    _initialized: bool = False

    def __new__(cls) -> "ScyllaManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _create_cluster(self) -> Cluster:
        """Create and configure the ScyllaDB cluster."""
        contact_points: list[str] = [
            host.strip() for host in config.SCYLLA_HOSTS.split(",")
        ]

        kwargs: dict[str, Any] = {
            "contact_points": contact_points,
            "port": config.SCYLLA_PORT,
            "connection_class": AsyncioConnection,
        }

        if config.SCYLLA_USERNAME and config.SCYLLA_PASSWORD:
            kwargs["auth_provider"] = PlainTextAuthProvider(
                username=config.SCYLLA_USERNAME,
                password=config.SCYLLA_PASSWORD,
            )

        return Cluster(**kwargs)

    async def initialize(self) -> None:
        """Initialize the ScyllaDB cluster and session. Must be called during app startup."""
        if not self.__class__._initialized:
            self._cluster = self._create_cluster()
            self._session = self._cluster.connect(
                keyspace=config.SCYLLA_KEYSPACE or None
            )
            logger.info("ScyllaDB client initialized successfully")
            self.__class__._initialized = True

    @property
    def session(self) -> Session:
        """Get the ScyllaDB session instance."""
        if self._session is None:
            raise RuntimeError(
                "ScyllaDB client not initialized. Call 'await scylla_manager.initialize()' first."
            )
        return self._session

    async def close(self) -> None:
        """Close the ScyllaDB cluster connection."""
        if self._cluster:
            self._cluster.shutdown()
            logger.info("ScyllaDB client shut down")
            self.__class__._initialized = False
            self.__class__._instance = None
            self._cluster = None
            self._session = None


# Create a singleton instance
_scylla_singleton = ScyllaManager()


async def initialize_scylla() -> None:
    """Initialize the ScyllaDB singleton client."""
    await _scylla_singleton.initialize()


async def close_scylla() -> None:
    """Close the ScyllaDB singleton client."""
    await _scylla_singleton.close()


def get_scylla_session() -> Session:
    """
    Get the singleton ScyllaDB session instance.

    Returns:
        Session: The singleton ScyllaDB session instance.
    """
    return _scylla_singleton.session
