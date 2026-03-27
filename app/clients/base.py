"""Base class for singleton client managers with a unified async lifecycle."""

from typing import Any, Generic, Self, TypeVar, cast

T = TypeVar("T")


class ClientManager(Generic[T]):
    """Base singleton with async initialize() / close() lifecycle.

    Subclasses must override ``_create_client`` and, if the underlying
    resource needs explicit teardown, ``_close_client``.
    """

    _instance: Any = None
    _client: T | None = None
    _initialized: bool = False

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cast(Self, cls._instance)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def client(self) -> T:
        if self._client is None:
            raise RuntimeError(
                f"{self.name} not initialized. Call 'await manager.initialize()' first."
            )
        return self._client

    async def initialize(self) -> None:
        if not self.__class__._initialized:
            self._client = await self._create_client()
            self.__class__._initialized = True

    async def _create_client(self) -> T:
        raise NotImplementedError

    async def close(self) -> None:
        if self._client:
            await self._close_client()
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None

    async def _close_client(self) -> None:
        """Override to perform cleanup. Default is a no-op."""
