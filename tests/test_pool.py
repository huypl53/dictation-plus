"""Tests for EnginePool."""
import asyncio

import pytest

from dictation.pool import EnginePool


class FakeEngine:
    """Simple engine stub for testing."""

    def __init__(self):
        self.reset_count = 0

    def reset(self):
        self.reset_count += 1


@pytest.mark.asyncio
async def test_pool_creates_on_first_acquire():
    call_count = 0

    def factory():
        nonlocal call_count
        call_count += 1
        return FakeEngine()

    pool = EnginePool(factory, max_size=2)
    assert call_count == 0
    engine = await pool.acquire()
    assert call_count == 1
    assert isinstance(engine, FakeEngine)
    pool.release(engine)


@pytest.mark.asyncio
async def test_pool_reuses_released_engine():
    pool = EnginePool(FakeEngine, max_size=2)
    engine1 = await pool.acquire()
    pool.release(engine1)
    engine2 = await pool.acquire()
    assert engine1 is engine2
    pool.release(engine2)


@pytest.mark.asyncio
async def test_pool_respects_max_size():
    pool = EnginePool(FakeEngine, max_size=2)
    e1 = await pool.acquire()
    e2 = await pool.acquire()

    # Third acquire should block — verify it times out
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(pool.acquire(), timeout=0.1)

    # Release one, now we can acquire again
    pool.release(e1)
    e3 = await pool.acquire()
    assert e3 is e1  # reused the released engine
    pool.release(e2)
    pool.release(e3)


@pytest.mark.asyncio
async def test_pool_checkout_context_manager():
    pool = EnginePool(FakeEngine, max_size=1)
    async with pool.checkout() as engine:
        assert isinstance(engine, FakeEngine)
    # After exiting, the engine should be back in the pool
    status = pool.status()
    assert status["idle"] == 1
    assert status["in_use"] == 0


@pytest.mark.asyncio
async def test_pool_on_release_callback():
    pool = EnginePool(FakeEngine, max_size=1, on_release=lambda e: e.reset())
    async with pool.checkout() as engine:
        assert engine.reset_count == 0
    # on_release should have called reset
    assert engine.reset_count == 1


@pytest.mark.asyncio
async def test_pool_checkout_releases_on_exception():
    pool = EnginePool(FakeEngine, max_size=1)
    with pytest.raises(ValueError, match="boom"):
        async with pool.checkout() as engine:
            raise ValueError("boom")
    # Engine should still be returned to pool
    status = pool.status()
    assert status["idle"] == 1
    assert status["in_use"] == 0


@pytest.mark.asyncio
async def test_pool_status():
    pool = EnginePool(FakeEngine, max_size=3)
    assert pool.status() == {"max_size": 3, "created": 0, "idle": 0, "in_use": 0}

    e1 = await pool.acquire()
    assert pool.status() == {"max_size": 3, "created": 1, "idle": 0, "in_use": 1}

    e2 = await pool.acquire()
    assert pool.status() == {"max_size": 3, "created": 2, "idle": 0, "in_use": 2}

    pool.release(e1)
    assert pool.status() == {"max_size": 3, "created": 2, "idle": 1, "in_use": 1}

    pool.release(e2)
    assert pool.status() == {"max_size": 3, "created": 2, "idle": 2, "in_use": 0}
