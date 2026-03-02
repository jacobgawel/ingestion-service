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
            self._session = self._cluster.connect()

            self._create_schema()

            self._session.set_keyspace(config.SCYLLA_KEYSPACE)
            logger.info("ScyllaDB client initialized successfully")
            self.__class__._initialized = True

    """
        -- 1. Simple partition key, no clustering
        PRIMARY KEY (job_id)
        -- job_id decides which node stores the row

        -- 2. Partition key + clustering key (what you have)
        PRIMARY KEY ((job_id), file_id)
        -- job_id decides the node, file_id sorts rows within that node

        -- 3. Composite partition key
        PRIMARY KEY ((source, project_id), file_id)
        -- source AND project_id TOGETHER decide the node
        -- meaning you must provide BOTH to query
    """

    def _create_schema(self) -> None:
        """Create keyspace and tables if they don't exist."""
        if self._session is None:
            raise RuntimeError("Cannot create schema: session not connected")

        # FYI: You can only execute one CQL statement at a time.
        # This is why all the statements are seperated.

        self._session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {config.SCYLLA_KEYSPACE}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
            """)

        self._session.set_keyspace(config.SCYLLA_KEYSPACE)

        self._session.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                job_id        TEXT,
                source        TEXT,
                project_id    TEXT,
                status        TEXT,
                total_files   INT,
                files_completed INT,
                files_failed  INT,
                created_at    TIMESTAMP,
                updated_at    TIMESTAMP,
                error_message TEXT,
                PRIMARY KEY ((job_id), source)
            )
            """)

        self._session.execute("""
            CREATE INDEX IF NOT EXISTS ingestion_jobs_project_id_idx
            ON nexus.ingestion_jobs (project_id);
            """)

        self._session.execute("""
            CREATE INDEX IF NOT EXISTS ingestion_jobs_status_idx
            ON nexus.ingestion_jobs (status);
            """)

        self._session.execute("""
            CREATE INDEX IF NOT EXISTS ingestion_jobs_source_idx
            ON nexus.ingestion_jobs (source);
            """)

        self._session.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS ingestion_jobs_by_source_project AS
                SELECT *
                FROM ingestion_jobs
                WHERE source IS NOT NULL
                  AND project_id IS NOT NULL
                  AND job_id IS NOT NULL
                PRIMARY KEY ((source, project_id), job_id)
            """)

        self._session.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_files (
                job_id        TEXT,
                project_id    TEXT,
                file_id       UUID,
                source        TEXT,
                filename      TEXT,
                object_name   TEXT,
                content_type  TEXT,
                status        TEXT,
                created_at    TIMESTAMP,
                updated_at    TIMESTAMP,
                error_message TEXT,
                PRIMARY KEY ((job_id), file_id)
            )
            """)

        self._session.execute("""
            CREATE INDEX IF NOT EXISTS ingestion_files_status_idx
            ON nexus.ingestion_files (status);
            """)

        self._session.execute("""
            CREATE INDEX IF NOT EXISTS ingestion_files_project_id_idx
            ON nexus.ingestion_files (project_id);
            """)

        self._session.execute("""
            CREATE INDEX IF NOT EXISTS ingestion_files_source_idx
            ON nexus.ingestion_files (source);
            """)

        logger.info("ScyllaDB schema created (keyspace + tables)")

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
