"""ACP (Agent Context Protocol) endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.core.config import get_settings, Settings

router = APIRouter()


class FoldStats(BaseModel):
    """Statistics for a single fold operation."""
    fold_id: str
    original_tokens: int
    folded_tokens: int
    compression_ratio: float
    anchor_count: int
    covered_message_count: int
    created_at: str


class SessionSummary(BaseModel):
    """Summary of a compression session."""
    session_id: str
    agent_namespace: str
    conversation_id: str
    total_messages: int
    total_original_tokens: int
    total_folded_tokens: int
    overall_compression_ratio: float
    fold_count: int
    last_fold_at: Optional[str] = None


class ACPStatusResponse(BaseModel):
    """ACP status response with compression statistics."""
    enabled: bool
    default_window_tokens: int
    compression_target_ratio: float
    fold_threshold_tokens: int
    active_sessions: int
    total_folds: int
    total_tokens_saved: int
    sessions: list[SessionSummary] = Field(default_factory=list)
    recent_folds: list[FoldStats] = Field(default_factory=list)


# Mock data for skeleton — replace with real storage in session-persistence feature
MOCK_SESSIONS = [
    SessionSummary(
        session_id="sess_01abc",
        agent_namespace="dsh",
        conversation_id="conv_123",
        total_messages=1250,
        total_original_tokens=1_250_000,
        total_folded_tokens=250_000,
        overall_compression_ratio=0.2,
        fold_count=7,
        last_fold_at="2026-10-15T14:32:00Z",
    ),
    SessionSummary(
        session_id="sess_02def",
        agent_namespace="trae",
        conversation_id="conv_456",
        total_messages=340,
        total_original_tokens=340_000,
        total_folded_tokens=68_000,
        overall_compression_ratio=0.2,
        fold_count=2,
        last_fold_at="2026-10-15T10:15:00Z",
    ),
]

MOCK_FOLDS = [
    FoldStats(
        fold_id="fold_001",
        original_tokens=180_000,
        folded_tokens=36_000,
        compression_ratio=0.2,
        anchor_count=15,
        covered_message_count=180,
        created_at="2026-10-15T14:32:00Z",
    ),
    FoldStats(
        fold_id="fold_002",
        original_tokens=220_000,
        folded_tokens=44_000,
        compression_ratio=0.2,
        anchor_count=18,
        covered_message_count=220,
        created_at="2026-10-15T13:45:00Z",
    ),
]


@router.get("/status", response_model=ACPStatusResponse, summary="ACP status")
async def acp_status(settings: Settings = Depends(get_settings)) -> ACPStatusResponse:
    """
    Return ACP compression status and statistics.
    Shows active sessions, fold history, and token savings.
    """
    if not settings.acp_enabled:
        raise HTTPException(status_code=503, detail="ACP is disabled")

    total_tokens_saved = sum(
        s.total_original_tokens - s.total_folded_tokens for s in MOCK_SESSIONS
    )

    return ACPStatusResponse(
        enabled=settings.acp_enabled,
        default_window_tokens=settings.acp_default_window_tokens,
        compression_target_ratio=settings.acp_compression_target_ratio,
        fold_threshold_tokens=settings.acp_fold_threshold_tokens,
        active_sessions=len(MOCK_SESSIONS),
        total_folds=sum(s.fold_count for s in MOCK_SESSIONS),
        total_tokens_saved=total_tokens_saved,
        sessions=MOCK_SESSIONS,
        recent_folds=MOCK_FOLDS,
    )


class CompressRequest(BaseModel):
    """Request to compress conversation history."""
    messages: list[dict] = Field(..., description="Conversation messages")
    window_tokens: Optional[int] = Field(None, description="Target context window")
    preserve_recent: int = Field(10, description="Recent messages to keep uncompressed")


class CompressResponse(BaseModel):
    """Response from compress operation."""
    folded_messages: list[dict]
    fold_anchors: list[dict]
    original_tokens: int
    folded_tokens: int
    compression_ratio: float
    fold_id: str


@router.post("/compress", response_model=CompressResponse, summary="Compress history")
async def compress_history(
    request: CompressRequest,
    settings: Settings = Depends(get_settings),
) -> CompressResponse:
    """
    Compress conversation history using fold-based compression.
    Returns folded messages with anchors for later decompression.
    """
    if not settings.acp_enabled:
        raise HTTPException(status_code=503, detail="ACP is disabled")

    # TODO: Implement actual fold-based compression
    # For skeleton, return mock response
    original_tokens = sum(len(str(m).split()) for m in request.messages) * 4 // 3
    folded_tokens = int(original_tokens * settings.acp_compression_target_ratio)

    return CompressResponse(
        folded_messages=request.messages[-request.preserve_recent:],
        fold_anchors=[{"id": f"anchor_{i}", "summary": f"Folded segment {i}"} for i in range(3)],
        original_tokens=original_tokens,
        folded_tokens=folded_tokens,
        compression_ratio=folded_tokens / original_tokens if original_tokens > 0 else 0,
        fold_id="fold_mock_001",
    )


class DecompressRequest(BaseModel):
    """Request to decompress folded history."""
    folded_messages: list[dict]
    fold_anchors: list[dict]


class DecompressResponse(BaseModel):
    """Response from decompress operation."""
    messages: list[dict]
    restored_count: int


@router.post("/decompress", response_model=DecompressResponse, summary="Decompress history")
async def decompress_history(request: DecompressRequest) -> DecompressResponse:
    """
    Restore original messages from folded representation and anchors.
    """
    # TODO: Implement actual decompression using stored fold data
    return DecompressResponse(
        messages=request.folded_messages,
        restored_count=len(request.fold_anchors) * 50,  # mock
    )