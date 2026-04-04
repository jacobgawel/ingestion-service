"""Temporal client singleton instance."""

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from shared.clients.base import ClientManager
from shared.core.settings import config


class TemporalManager(ClientManager[Client]):
    """Singleton manager for the Temporal client."""

    async def _create_client(self) -> Client:
        return await Client.connect(
            config.TEMPORAL_HOST,
            data_converter=pydantic_data_converter,
        )


_temporal_singleton = TemporalManager()


def get_temporal_client() -> Client:
    return _temporal_singleton.client
