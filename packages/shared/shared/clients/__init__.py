import asyncio

from shared.core.logger import get_logger

from .alloydb_client import AlloyDBManager, get_alloydb_pool
from .base import ClientManager
from .minio_client import MinioManager, get_minio_handler
from .nats_client import NATSManager, get_nats_client
from .openai_client import OpenAIManager, get_openai_client
from .temporal_client import TemporalManager, get_temporal_client

logger = get_logger("Clients")

_managers: list[ClientManager] = [
    TemporalManager(),
    MinioManager(),
    AlloyDBManager(),
    NATSManager(),
    OpenAIManager(),
]


async def initialize_all() -> None:
    for manager in _managers:
        logger.info(f"Initializing {manager.name}...")
        await manager.initialize()


async def close_all(timeout: float = 5.0) -> None:
    for manager in _managers:
        try:
            await asyncio.wait_for(manager.close(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"{manager.name} close timed out after {timeout}s")
        except Exception as e:
            logger.warning(f"{manager.name} close failed: {e}")


__all__ = [
    "close_all",
    "get_alloydb_pool",
    "get_minio_handler",
    "get_nats_client",
    "get_openai_client",
    "get_temporal_client",
    "initialize_all",
]
