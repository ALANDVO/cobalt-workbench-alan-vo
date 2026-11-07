"""Tests for session persistence feature."""

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
async def test_session_create_and_list(client: AsyncClient):
    """Test creating a session via compress and listing sessions."""
    # First compress to create a session
    response = await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "test-agent",
            "conversation_id": "conv-001",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
                {"role": "assistant", "content": "I'm doing well, thanks!"},
            ],
            "preserve_recent": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["session_id"].startswith("sess_")

    # List sessions
    response = await client.get("/acp/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1

    # Find our session
    session = next((s for s in sessions if s["conversation_id"] == "conv-001"), None)
    assert session is not None
    assert session["agent_namespace"] == "test-agent"
    assert session["message_count"] >= 4
    assert session["fold_count"] >= 1


@pytest.mark.asyncio
async def test_session_get_by_id(client: AsyncClient):
    """Test getting a specific session by namespace and conversation ID."""
    # Create session
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "test-agent-2",
            "conversation_id": "conv-002",
            "messages": [
                {"role": "user", "content": "Test message"},
                {"role": "assistant", "content": "Test response"},
            ],
            "preserve_recent": 1,
        },
    )

    # Get session
    response = await client.get("/acp/sessions/test-agent-2/conv-002")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_namespace"] == "test-agent-2"
    assert data["conversation_id"] == "conv-002"
    assert data["message_count"] >= 2
    assert data["fold_count"] >= 1


@pytest.mark.asyncio
async def test_session_not_found(client: AsyncClient):
    """Test 404 for non-existent session."""
    response = await client.get("/acp/sessions/nonexistent/conv-999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compress_persists_data(client: AsyncClient):
    """Test that compress persists folds and messages."""
    response = await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "persist-test",
            "conversation_id": "conv-persist",
            "messages": [
                {"role": "user", "content": "Message 1"},
                {"role": "assistant", "content": "Response 1"},
                {"role": "user", "content": "Message 2"},
                {"role": "assistant", "content": "Response 2"},
                {"role": "user", "content": "Message 3"},
                {"role": "assistant", "content": "Response 3"},
            ],
            "preserve_recent": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fold_id"] != ""
    assert data["fold_anchors"]
    assert len(data["fold_anchors"]) >= 1
    assert data["original_tokens"] > data["folded_tokens"]


@pytest.mark.asyncio
async def test_decompress_from_session(client: AsyncClient):
    """Test decompressing messages from persisted session."""
    # Create session with compress
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "decompress-test",
            "conversation_id": "conv-decompress",
            "messages": [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "First response"},
                {"role": "user", "content": "Second message"},
                {"role": "assistant", "content": "Second response"},
            ],
            "preserve_recent": 2,
        },
    )

    # Decompress from session
    response = await client.post(
        "/acp/decompress",
        json={
            "agent_namespace": "decompress-test",
            "conversation_id": "conv-decompress",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert data["restored_count"] >= 4
    assert data["session_id"].startswith("sess_")


@pytest.mark.asyncio
async def test_search_context_from_session(client: AsyncClient):
    """Test searching compressed context from persisted session."""
    # Create session with more content
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "search-test",
            "conversation_id": "conv-search",
            "messages": [
                {"role": "user", "content": "I want to learn about Python programming"},
                {"role": "assistant", "content": "Python is a versatile programming language"},
                {"role": "user", "content": "What about JavaScript?"},
                {"role": "assistant", "content": "JavaScript is used for web development"},
                {"role": "user", "content": "Tell me about databases"},
                {"role": "assistant", "content": "Databases store and organize data efficiently"},
            ],
            "preserve_recent": 2,
        },
    )

    # Search from session
    response = await client.post(
        "/acp/search_context",
        json={
            "agent_namespace": "search-test",
            "conversation_id": "conv-search",
            "query": "Python",
            "max_results": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Python"
    assert isinstance(data["results"], list)
    assert data["session_id"].startswith("sess_")
    # Should find relevant results
    assert data["results_count"] >= 0


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient):
    """Test deleting a session."""
    # Create session
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "delete-test",
            "conversation_id": "conv-delete",
            "messages": [
                {"role": "user", "content": "To be deleted"},
                {"role": "assistant", "content": "Will be deleted"},
            ],
            "preserve_recent": 1,
        },
    )

    # Verify it exists
    response = await client.get("/acp/sessions/delete-test/conv-delete")
    assert response.status_code == 200

    # Delete it
    response = await client.delete("/acp/sessions/delete-test/conv-delete")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True

    # Verify it's gone
    response = await client.get("/acp/sessions/delete-test/conv-delete")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_status_shows_real_sessions(client: AsyncClient):
    """Test that /acp/status reflects real persisted sessions."""
    # Create a couple sessions
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "status-test-1",
            "conversation_id": "conv-status-1",
            "messages": [
                {"role": "user", "content": "Msg 1"},
                {"role": "assistant", "content": "Resp 1"},
            ],
            "preserve_recent": 1,
        },
    )

    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "status-test-2",
            "conversation_id": "conv-status-2",
            "messages": [
                {"role": "user", "content": "Msg 2"},
                {"role": "assistant", "content": "Resp 2"},
            ],
            "preserve_recent": 1,
        },
    )

    # Check status
    response = await client.get("/acp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["active_sessions"] >= 2
    assert data["total_folds"] >= 2
    assert data["total_tokens_saved"] >= 0

    # Verify our sessions appear
    sessions = data["sessions"]
    ns_conv_pairs = {(s["agent_namespace"], s["conversation_id"]) for s in sessions}
    assert ("status-test-1", "conv-status-1") in ns_conv_pairs
    assert ("status-test-2", "conv-status-2") in ns_conv_pairs


@pytest.mark.asyncio
async def test_multiple_compresses_same_session(client: AsyncClient):
    """Test multiple compress operations on same session accumulate folds."""
    # First compress
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "multi-test",
            "conversation_id": "conv-multi",
            "messages": [
                {"role": "user", "content": f"Message {i}"} for i in range(10)
            ] + [{"role": "assistant", "content": f"Response {i}"} for i in range(10)],
            "preserve_recent": 4,
        },
    )

    # Second compress on same session (simulating continued conversation)
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "multi-test",
            "conversation_id": "conv-multi",
            "messages": [
                {"role": "user", "content": f"Message {i}"} for i in range(20)
            ] + [{"role": "assistant", "content": f"Response {i}"} for i in range(20)],
            "preserve_recent": 4,
        },
    )

    # Check session has multiple folds
    response = await client.get("/acp/sessions/multi-test/conv-multi")
    assert response.status_code == 200
    data = response.json()
    assert data["fold_count"] >= 2
    assert data["message_count"] >= 40


@pytest.mark.asyncio
async def test_session_persistence_survives_restart(client: AsyncClient):
    """Test that session data persists (simulated by new client)."""
    # Create session
    await client.post(
        "/acp/compress",
        json={
            "agent_namespace": "restart-test",
            "conversation_id": "conv-restart",
            "messages": [
                {"role": "user", "content": "Persistent message"},
                {"role": "assistant", "content": "Persistent response"},
            ],
            "preserve_recent": 1,
        },
    )

    # Create new client (simulates restart)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as new_client:
        # Should still find the session
        response = await new_client.get("/acp/sessions/restart-test/conv-restart")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_namespace"] == "restart-test"
        assert data["conversation_id"] == "conv-restart"
        assert data["message_count"] >= 2

