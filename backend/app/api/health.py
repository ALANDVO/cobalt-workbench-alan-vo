"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.config import get_settings, Settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Basic health check endpoint.
    Returns service status and version information.
    """
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health/ready", response_model=HealthResponse, summary="Readiness check")
async def readiness_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Readiness check for Kubernetes/Docker health probes.
    Extend to verify database, Keycloak, and other dependencies.
    """
    # TODO: Check database connectivity
    # TODO: Check Keycloak JWKS availability
    return HealthResponse(
        status="ready",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )