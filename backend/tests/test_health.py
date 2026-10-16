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
async def test_health_check(client: AsyncClient):
    """Test /health endpoint returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "cobalt-workbench"
    assert "version" in data
    assert data["environment"] in ("development", "production")


@pytest.mark.asyncio
async def test_readiness_check(client: AsyncClient):
    """Test /health/ready endpoint returns ready status."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "cobalt-workbench"