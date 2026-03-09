"""Generic async engine pool with bounded concurrency."""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Generic, TypeVar

T = TypeVar("T")


class EnginePool(Generic[T]):
    """Bounded pool of reusable engine instances.

    Engines are created lazily via a factory callable, up to ``max_size``.
    Acquire blocks (via semaphore) when all slots are in use.
    """

    def __init__(
        self,
        factory: Callable[[], T],
        max_size: int = 2,
        on_release: Callable[[T], None] | None = None,
    ) -> None:
        self._factory: Callable[[], T] = factory
        self._max_size: int = max_size
        self._on_release: Callable[[T], None] | None = on_release
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_size)
        self._idle: deque[T] = deque()
        self._created_count: int = 0

    async def acquire(self) -> T:
        """Acquire an engine, blocking if the pool is exhausted."""
        await self._semaphore.acquire()
        if self._idle:
            return self._idle.popleft()
        # Create a new instance in a thread (constructors may block)
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        engine: T = await loop.run_in_executor(None, self._factory)
        self._created_count += 1
        return engine

    def release(self, engine: T) -> None:
        """Return an engine to the pool."""
        if self._on_release is not None:
            self._on_release(engine)
        self._idle.append(engine)
        self._semaphore.release()

    @asynccontextmanager
    async def checkout(self) -> AsyncIterator[T]:
        """Context manager that acquires and auto-releases an engine."""
        engine: T = await self.acquire()
        try:
            yield engine
        finally:
            self.release(engine)

    def status(self) -> dict[str, int]:
        """Return pool statistics."""
        return {
            "max_size": self._max_size,
            "created": self._created_count,
            "idle": len(self._idle),
            "in_use": self._created_count - len(self._idle),
        }
