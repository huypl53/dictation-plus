"""Tests for FastAPI service."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from dictation.api import create_app


@pytest.fixture
def mock_stt():
    return MagicMock()


@pytest.fixture
def mock_tts():
    engine = MagicMock()
    engine.synthesize.return_value = b"RIFF" + b"\x00" * 100
    return engine


@pytest.fixture
def app(mock_stt, mock_tts):
    return create_app(stt_engine=mock_stt, tts_engine=mock_tts)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_post_tts(client, mock_tts):
    resp = await client.post("/tts", json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    mock_tts.synthesize.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_post_tts_missing_text(client):
    resp = await client.post("/tts", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_stt_start(client):
    resp = await client.post("/stt/start")
    assert resp.status_code == 200
    data = resp.json()
    assert "ws_url" in data


@pytest.mark.asyncio
async def test_post_stt_stop(client, mock_stt):
    mock_stt.finalize.return_value = MagicMock(text="hello", is_final=True)
    resp = await client.post("/stt/stop")
    assert resp.status_code == 200
