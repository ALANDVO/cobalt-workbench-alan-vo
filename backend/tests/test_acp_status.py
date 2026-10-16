import pytest_asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Create test client."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_acp_status_enabled(client: AsyncClient):
    """Test /acp/status returns expected structure when enabled."""
    response = await client.get("/acp/status")
    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert data["enabled"] is True
    assert isinstance(data["default_window_tokens"], int)
    assert data["default_window_tokens"] > 0
    assert isinstance(data["compression_target_ratio"], float)
    assert 0 < data["compression_target_ratio"] < 1
    assert isinstance(data["fold_threshold_tokens"], int)
    assert data["fold_threshold_tokens"] > 0

    # Session stats
    assert isinstance(data["active_sessions"], int)
    assert data["active_sessions"] >= 0
    assert isinstance(data["total_folds"], int)
    assert data["total_folds"] >= 0
    assert isinstance(data["total_tokens_saved"], int)
    assert data["total_tokens_saved"] >= 0

    # Sessions array
    assert isinstance(data["sessions"], list)
    for session in data["sessions"]:
        assert "session_id" in session
        assert "agent_namespace" in session
        assert "conversation_id" in session
        assert isinstance(session["total_messages"], int)
        assert isinstance(session["total_original_tokens"], int)
        assert isinstance(session["total_folded_tokens"], int)
        assert isinstance(session["overall_compression_ratio"], float)
        assert isinstance(session["fold_count"], int)
        assert session["last_fold_at"] is None or isinstance(session["last_fold_at"], str)

    # Recent folds array
    assert isinstance(data["recent_folds"], list)
    for fold in data["recent_folds"]:
        assert "fold_id" in fold
        assert isinstance(fold["original_tokens"], int)
        assert isinstance(fold["folded_tokens"], int)
        assert isinstance(fold["compression_ratio"], float)
        assert isinstance(fold["anchor_count"], int)
        assert isinstance(fold["covered_message_count"], int)
        assert isinstance(fold["created_at"], str)


@pytest.mark.asyncio
async def test_acp_compress_endpoint_exists(client: AsyncClient):
    """Test /acp/compress endpoint accepts requests."""
    response = await client.post(
        "/acp/compress",
        json={
            "messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}],
            "preserve_recent": 2,
        },
    )
    # Should not be 404
    assert response.status_code != 404
    if response.status_code == 200:
        data = response.json()
        assert "folded_messages" in data
        assert "fold_anchors" in data
        assert "original_tokens" in data
        assert "folded_tokens" in data
        assert "compression_ratio" in data
        assert "fold_id" in data


@pytest.mark.asyncio
async def test_acp_decompress_endpoint_exists(client: AsyncClient):
    """Test /acp/decompress endpoint accepts requests."""
    response = await client.post(
        "/acp/decompress",
        json={
            "folded_messages": [{"role": "user", "content": "Hello"}],
            "fold_anchors": [{"id": "anchor_1", "summary": "Previous context"}],
        },
    )
    # Should not be 404
    assert response.status_code != 404
    if response.status_code == 200:
        data = response.json()
        assert "messages" in data
        assert "restored_count" in data