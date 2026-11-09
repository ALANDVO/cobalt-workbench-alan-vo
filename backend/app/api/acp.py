"""ACP (Agent Context Protocol) endpoints."""

from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator, Any
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.database import init_db, close_db, get_db
from app.models import Session as SessionModel
from app.services.acp_compress import (
    fold_conversation,
    unfold_conversation,
    FoldAnchor,
    CompressedConversation,
    search_context,
    SearchContextRequest,
    SearchContextResponse,
    SearchContextResult,
)
from app.services.session_storage import SessionStorage, get_session_storage

router = APIRouter()


@asynccontextmanager
async def lifespan(app: "FastAPI") -> AsyncGenerator[None, None]:
    """Application lifespan handler for database initialization."""
    await init_db()
    yield
    await close_db()


def set_lifespan(app: "FastAPI") -> None:
    """Attach lifespan to FastAPI app."""
    app.router.lifespan_context = lifespan


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

@router.get("/status", response_model=ACPStatusResponse, summary="ACP status")
async def acp_status(
    settings: Settings = Depends(get_settings),
    storage: SessionStorage = Depends(get_session_storage),
) -> ACPStatusResponse:
    """
    Return ACP compression status and statistics.
    Shows active sessions, fold history, and token savings.
    """
    if not settings.acp_enabled:
        raise HTTPException(status_code=503, detail="ACP is disabled")

    # Get all sessions from database
    result = await storage.db_session().execute(
        text("SELECT * FROM sessions ORDER BY updated_at DESC")
    )
    sessions_data = result.fetchall()

    session_summaries = []
    recent_folds = []
    total_folds = 0
    total_tokens_saved = 0

    for row in sessions_data:
        session = await storage.get_session(row.agent_namespace, row.conversation_id)
        if not session:
            continue

        folds = await storage.get_folds(session)
        all_messages = await storage.get_all_messages(session)

        total_original = sum(m.token_count for m in all_messages)
        total_folded = sum(f.token_count for f in folds)
        tokens_saved = total_original - total_folded
        total_tokens_saved += tokens_saved
        total_folds += len(folds)

        last_fold = folds[-1].created_at.isoformat() + "Z" if folds else None

        session_summaries.append(
            SessionSummary(
                session_id=f"sess_{session.id:03d}",
                agent_namespace=session.agent_namespace,
                conversation_id=session.conversation_id,
                total_messages=len(all_messages),
                total_original_tokens=total_original,
                total_folded_tokens=total_folded,
                overall_compression_ratio=total_folded / total_original if total_original > 0 else 0,
                fold_count=len(folds),
                last_fold_at=last_fold,
            )
        )

        for f in folds:
            fold_messages = await storage.get_messages_for_fold(session, f.fold_id)
            original_tokens = sum(m.token_count for m in fold_messages)
            recent_folds.append(
                FoldStats(
                    fold_id=f.fold_id,
                    original_tokens=original_tokens,
                    folded_tokens=f.token_count,
                    compression_ratio=f.token_count / original_tokens if original_tokens > 0 else 0,
                    anchor_count=len(json.loads(f.covered_ids)),
                    covered_message_count=len(json.loads(f.covered_ids)),
                    created_at=f.created_at.isoformat() + "Z",
                )
            )

    return ACPStatusResponse(
        enabled=settings.acp_enabled,
        default_window_tokens=settings.acp_default_window_tokens,
        compression_target_ratio=settings.acp_compression_target_ratio,
        fold_threshold_tokens=settings.acp_fold_threshold_tokens,
        active_sessions=len(session_summaries),
        total_folds=total_folds,
        total_tokens_saved=total_tokens_saved,
        sessions=session_summaries,
        recent_folds=recent_folds,
    )


class SessionRequest(BaseModel):
    """Request with session identification."""
    agent_namespace: str = Field(..., description="Agent namespace (e.g., 'dsh', 'trae')")
    conversation_id: str = Field(..., description="Conversation identifier")


class CompressRequest(SessionRequest):
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
    session_id: str


@router.post("/compress", summary="Compress history")
async def compress_history(
    request: CompressRequest,
    settings: Settings = Depends(get_settings),
    storage: SessionStorage = Depends(get_session_storage),
) -> CompressResponse:
    """
    Compress conversation history using fold-based compression.
    Returns folded messages with anchors for later decompression.
    Persists session, folds, and messages to database.
    """
    if not settings.acp_enabled:
        raise HTTPException(status_code=503, detail="ACP is disabled")

    session = await storage.get_or_create_session(
        request.agent_namespace, request.conversation_id
    )

    result = fold_conversation(
        messages=request.messages,
        preserve_recent=request.preserve_recent,
        target_ratio=settings.acp_compression_target_ratio,
    )

    # Save the fold and its messages
    if result.fold_anchors:
        # Get messages covered by the fold (all but recent)
        covered_messages = request.messages[:-request.preserve_recent] if request.preserve_recent < len(request.messages) else []
        # Convert FoldAnchor to dict format expected by storage
        fold_dict = result.fold_anchors[0].to_dict()
        await storage.save_fold(session, fold_dict, covered_messages)

    # Save recent messages
    recent_messages = request.messages[-request.preserve_recent:] if request.preserve_recent > 0 else []
    await storage.save_recent_messages(session, recent_messages)

    return CompressResponse(
        folded_messages=result.folded_messages,
        fold_anchors=[a.to_dict() for a in result.fold_anchors],
        original_tokens=result.original_tokens,
        folded_tokens=result.folded_tokens,
        compression_ratio=result.compression_ratio,
        fold_id=result.fold_id,
        session_id=f"sess_{session.id:03d}",
    )


class DecompressRequest(SessionRequest):
    """Request to decompress folded history from session."""
    fold_id: Optional[str] = Field(None, description="Specific fold to decompress (latest if omitted)")


class DecompressResponse(BaseModel):
    """Response from decompress operation."""
    messages: list[dict]
    restored_count: int
    session_id: str


@router.post("/decompress", response_model=None, summary="Decompress history")
async def decompress_history(
    request: DecompressRequest,
    storage: SessionStorage = Depends(get_session_storage),
) -> DecompressResponse:
    """
    Restore original messages from folded representation and anchors.
    Retrieves original messages from session storage.
    """
    session = await storage.get_session(request.agent_namespace, request.conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the compressed conversation from storage
    compressed = await storage.to_compressed_conversation(session)

    # If specific fold requested, filter to that fold
    if request.fold_id:
        fold = next((f for f in compressed.folds if f.fold_id == request.fold_id), None)
        if not fold:
            raise HTTPException(status_code=404, detail="Fold not found")
        folds = [fold]
    else:
        folds = compressed.folds

    messages, restored_count = unfold_conversation(
        folded_messages=compressed.recent_messages,
        fold_anchors=[{"fold_id": f.fold_id, "anchor_text": f.anchor_text, "covered_ids": f.covered_ids} for f in folds],
        original_messages=None,  # We'll get them from storage
    )

    # Also retrieve original messages for each fold
    all_restored = []
    for f in folds:
        fold_messages = await storage.get_messages_for_fold(session, f.fold_id)
        for m in fold_messages:
            all_restored.append(storage._message_to_dict(m))

    # Add recent messages
    all_restored.extend(storage._message_to_dict(m) for m in compressed.recent_messages)

    return DecompressResponse(
        messages=all_restored,
        restored_count=len(all_restored),
        session_id=f"sess_{session.id:03d}",
    )


class SearchContextRequest(BaseModel):
    """Request to search compressed conversation context."""
    query: str = Field(..., description="Search query")
    agent_namespace: Optional[str] = Field(None, description="Agent namespace (required if not providing fold_anchors)")
    conversation_id: Optional[str] = Field(None, description="Conversation identifier (required if not providing fold_anchors)")
    fold_anchors: Optional[list[dict[str, Any]]] = Field(None, description="Fold anchors from compressed history (alternative to session lookup)")
    max_results: int = Field(10, description="Maximum results to return")
    min_score: float = Field(0.1, description="Minimum relevance score (0-1)")


class SearchContextResponse(BaseModel):
    """Response from search_context operation."""
    query: str
    results: list[SearchContextResult]
    total_anchors_searched: int
    results_count: int
    session_id: str


@router.post("/search_context", response_model=SearchContextResponse, summary="Search compressed context")
async def search_context_endpoint(
    request: SearchContextRequest,
    storage: SessionStorage = Depends(get_session_storage),
) -> SearchContextResponse:
    """
    Search compressed conversation folds for relevant context.

    Returns matching fold summaries with anchor references ranked by relevance.
    Supports two modes:
    1. Session lookup: provide agent_namespace and conversation_id
    2. Direct anchors: provide fold_anchors directly
    """
    if request.fold_anchors is not None:
        # Direct anchors mode
        fold_anchors = request.fold_anchors
        session_id = "direct"
    else:
        # Session lookup mode
        if not request.agent_namespace or not request.conversation_id:
            raise HTTPException(
                status_code=422,
                detail="Either fold_anchors or both agent_namespace and conversation_id are required"
            )
        session = await storage.get_session(request.agent_namespace, request.conversation_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        folds = await storage.get_folds(session)

        # Convert to service format
        fold_anchors = [
            {
                "fold_id": f.fold_id,
                "anchor_text": f.anchor_text,
                "covered_ids": json.loads(f.covered_ids),
                "token_count": f.token_count,
                "created_at": f.created_at.isoformat() + "Z",
                "message_count": len(await storage.get_messages_for_fold(session, f.fold_id)),
            }
            for f in folds
        ]
        session_id = f"sess_{session.id:03d}"

    # Use service function (imported as search_context from acp_compress)
    from app.services.acp_compress import SearchContextRequest as ServiceSearchContextRequest
    service_request = ServiceSearchContextRequest(
        query=request.query,
        fold_anchors=fold_anchors,
        max_results=request.max_results,
        min_score=request.min_score,
    )

    response = search_context(service_request)

    return SearchContextResponse(
        query=response.query,
        results=response.results,
        total_anchors_searched=response.total_anchors_searched,
        results_count=response.results_count,
        session_id=session_id,
    )


class SessionResponse(BaseModel):
    """Response for session operations."""
    session_id: str
    agent_namespace: str
    conversation_id: str
    created_at: str
    updated_at: str
    message_count: int
    fold_count: int


@router.get("/sessions", response_model=list[SessionResponse], summary="List sessions")
async def list_sessions(
    storage: SessionStorage = Depends(get_session_storage),
) -> list[SessionResponse]:
    """List all persisted sessions."""
    result = await storage.get_db().execute(
        "SELECT * FROM sessions ORDER BY updated_at DESC"
    )
    sessions_data = result.fetchall()

    responses = []
    for row in sessions_data:
        session = await storage.get_session(row.agent_namespace, row.conversation_id)
        if not session:
            continue
        all_messages = await storage.get_all_messages(session)
        folds = await storage.get_folds(session)
        responses.append(
            SessionResponse(
                session_id=f"sess_{session.id:03d}",
                agent_namespace=session.agent_namespace,
                conversation_id=session.conversation_id,
                created_at=session.created_at.isoformat() + "Z",
                updated_at=session.updated_at.isoformat() + "Z",
                message_count=len(all_messages),
                fold_count=len(folds),
            )
        )
    return responses


@router.get("/sessions/{agent_namespace}/{conversation_id}", response_model=SessionResponse, summary="Get session")
async def get_session_endpoint(
    agent_namespace: str,
    conversation_id: str,
    storage: SessionStorage = Depends(get_session_storage),
) -> SessionResponse:
    """Get session details by namespace and conversation ID."""
    session = await storage.get_session(agent_namespace, conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_messages = await storage.get_all_messages(session)
    folds = await storage.get_folds(session)

    return SessionResponse(
        session_id=f"sess_{session.id:03d}",
        agent_namespace=session.agent_namespace,
        conversation_id=session.conversation_id,
        created_at=session.created_at.isoformat() + "Z",
        updated_at=session.updated_at.isoformat() + "Z",
        message_count=len(all_messages),
        fold_count=len(folds),
    )


@router.delete("/sessions/{agent_namespace}/{conversation_id}", summary="Delete session")
async def delete_session_endpoint(
    agent_namespace: str,
    conversation_id: str,
    storage: SessionStorage = Depends(get_session_storage),
) -> dict:
    """Delete a session and all its data."""
    session = await storage.get_session(agent_namespace, conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await storage.delete_session(session)
    return {"deleted": True, "session_id": f"sess_{session.id:03d}"}

