"""OpenAI client singleton instance."""

from openai import AsyncOpenAI

from shared.clients.base import ClientManager
from shared.core.settings import config


class OpenAIManager(ClientManager[AsyncOpenAI]):
    """Singleton manager for the OpenAI client."""

    async def _create_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=config.OPENAI_KEY)

    async def _close_client(self) -> None:
        await self.client.close()


_openai_singleton = OpenAIManager()


def get_openai_client() -> AsyncOpenAI:
    return _openai_singleton.client
