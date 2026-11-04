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


@pytest.mark.asyncio
async def test_acp_search_context_endpoint_exists(client: AsyncClient):
    """Test /acp/search_context endpoint accepts requests."""
    request_data = {
        "query": "user assistant",
        "fold_anchors": [
            {
                "id": "fold_abc123",
                "summary": "2 user, 1 assistant: Hello world example...",
                "covered_message_ids": ["msg1", "msg2", "msg3"],
                "start_idx": 0,
                "end_idx": 2,
                "original_tokens": 150,
                "folded_tokens": 80,
            },
            {
                "id": "fold_def456",
                "summary": "1 system, 2 tool: Function call results...",
                "covered_message_ids": ["msg4", "msg5"],
                "start_idx": 3,
                "end_idx": 4,
                "original_tokens": 200,
                "folded_tokens": 80,
            },
        ],
        "max_results": 10,
        "min_score": 0.1,
    }
    response = await client.post("/acp/search_context", json=request_data)
    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert data["query"] == "user assistant"
    assert isinstance(data["results"], list)
    assert isinstance(data["total_anchors_searched"], int)
    assert data["total_anchors_searched"] == 2
    assert isinstance(data["results_count"], int)
    assert data["results_count"] >= 0

    # Results structure
    for result in data["results"]:
        assert "anchor_id" in result
        assert "summary" in result
        assert "covered_message_ids" in result
        assert "start_idx" in result
        assert "end_idx" in result
        assert "original_tokens" in result
        assert "folded_tokens" in result
        assert "score" in result
        assert isinstance(result["score"], (int, float))
        assert 0 <= result["score"] <= 1

    # Results should be sorted by score descending
    scores = [r["score"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_acp_search_context_empty_query(client: AsyncClient):
    """Test /acp/search_context with empty query returns empty results."""
    request_data = {
        "query": "",
        "fold_anchors": [
            {
                "id": "fold_abc123",
                "summary": "2 user, 1 assistant: Hello world example...",
                "covered_message_ids": ["msg1", "msg2", "msg3"],
                "start_idx": 0,
                "end_idx": 2,
                "original_tokens": 150,
                "folded_tokens": 80,
            },
        ],
        "max_results": 10,
        "min_score": 0.1,
    }
    response = await client.post("/acp/search_context", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["results_count"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_acp_search_context_no_anchors(client: AsyncClient):
    """Test /acp/search_context with no anchors returns empty results."""
    request_data = {
        "query": "user",
        "fold_anchors": [],
        "max_results": 10,
        "min_score": 0.1,
    }
    response = await client.post("/acp/search_context", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["results_count"] == 0
    assert data["total_anchors_searched"] == 0
    assert data["results"] == []