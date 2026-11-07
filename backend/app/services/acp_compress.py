"""ACP fold-based compression service.

Implements content-hash anchored folding for conversation history compression.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel, Field


@dataclass
class FoldAnchor:
    """Anchor for a folded segment enabling decompression."""
    id: str
    summary: str
    covered_message_ids: list[str]
    start_idx: int
    end_idx: int
    original_tokens: int
    folded_tokens: int
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "fold_id": self.id,
            "anchor_text": self.summary,
            "covered_ids": self.covered_message_ids,
            "token_count": self.folded_tokens,
            "created_at": self.created_at,
            "message_count": len(self.covered_message_ids),
        }


@dataclass
class CompressedConversation:
    """Result of compression operation."""
    folded_messages: list[dict[str, Any]]
    fold_anchors: list[FoldAnchor]
    original_tokens: int
    folded_tokens: int
    compression_ratio: float
    fold_id: str


def message_id(message: dict[str, Any]) -> str:
    """Generate stable content-hash based ID for a message."""
    content = json.dumps(message, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return max(1, len(text) // 4)


def count_message_tokens(message: dict[str, Any]) -> int:
    """Count tokens in a message."""
    if "content" in message and isinstance(message["content"], str):
        return estimate_tokens(message["content"])
    return 0


def summarize_messages(messages: list[dict[str, Any]]) -> str:
    """Create a summary of folded messages."""
    if not messages:
        return "Empty fold"

    roles = [m.get("role", "unknown") for m in messages]
    role_counts: dict[str, int] = {}
    for r in roles:
        role_counts[r] = role_counts.get(r, 0) + 1

    parts = [f"{count} {role}" for role, count in role_counts.items()]

    # Include a brief preview of the first message content
    preview = ""
    if messages:
        first_content = messages[0].get("content", "")
        if isinstance(first_content, str) and first_content:
            preview = first_content[:80] + ("..." if len(first_content) > 80 else "")

    return f"{', '.join(parts)}: {preview}" if preview else f"{', '.join(parts)}"


def fold_conversation(
    messages: list[dict[str, Any]],
    preserve_recent: int = 10,
    target_ratio: float = 0.2,
) -> CompressedConversation:
    """Compress conversation using fold-based compression.

    Args:
        messages: Full conversation history (oldest first)
        preserve_recent: Number of recent messages to keep uncompressed
        target_ratio: Target compression ratio (folded/original)

    Returns:
        CompressedConversation with folded messages and anchors
    """
    if len(messages) <= preserve_recent:
        # Nothing to fold
        return CompressedConversation(
            folded_messages=messages,
            fold_anchors=[],
            original_tokens=sum(count_message_tokens(m) for m in messages),
            folded_tokens=sum(count_message_tokens(m) for m in messages),
            compression_ratio=1.0,
            fold_id="",
        )

    # Split into foldable and recent
    foldable = messages[:-preserve_recent]
    recent = messages[-preserve_recent:]

    # Calculate tokens
    original_tokens = sum(count_message_tokens(m) for m in foldable)
    target_folded = int(original_tokens * target_ratio)

    # Create fold anchors - group messages into chunks
    fold_anchors = []
    current_chunk = []
    current_tokens = 0
    chunk_start = 0

    for i, msg in enumerate(foldable):
        msg_tokens = count_message_tokens(msg)
        current_chunk.append(msg)
        current_tokens += msg_tokens

        # Create fold when we hit target or at end
        should_fold = (
            current_tokens >= target_folded and len(fold_anchors) == 0
        ) or (i == len(foldable) - 1)

        if should_fold and current_chunk:
            covered_ids = [message_id(m) for m in current_chunk]
            summary = summarize_messages(current_chunk)
            anchor = FoldAnchor(
                id=hashlib.sha256(
                    f"{chunk_start}-{i}-{summary}".encode()
                ).hexdigest()[:16],
                summary=summary,
                covered_message_ids=covered_ids,
                start_idx=chunk_start,
                end_idx=i,
                original_tokens=current_tokens,
                folded_tokens=max(1, int(current_tokens * target_ratio)),
            )
            fold_anchors.append(anchor)
            current_chunk = []
            current_tokens = 0
            chunk_start = i + 1

    # Build folded messages: fold summaries + recent messages
    folded_messages = []
    for anchor in fold_anchors:
        folded_messages.append({
            "role": "system",
            "content": f"[FOLD:{anchor.id}] {anchor.summary}",
            "meta": {
                "fold_id": anchor.id,
                "covered_count": len(anchor.covered_message_ids),
                "original_tokens": anchor.original_tokens,
            },
        })
    folded_messages.extend(recent)

    folded_tokens = sum(count_message_tokens(m) for m in folded_messages)
    total_original = sum(count_message_tokens(m) for m in messages)
    ratio = folded_tokens / total_original if total_original > 0 else 1.0

    fold_id = fold_anchors[-1].id if fold_anchors else ""

    return CompressedConversation(
        folded_messages=folded_messages,
        fold_anchors=fold_anchors,
        original_tokens=total_original,
        folded_tokens=folded_tokens,
        compression_ratio=ratio,
        fold_id=fold_id,
    )


def unfold_conversation(
    folded_messages: list[dict[str, Any]],
    fold_anchors: list[dict[str, Any]],
    original_messages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Restore original messages from folded representation.

    Args:
        folded_messages: Messages including fold summaries
        fold_anchors: Anchor metadata for each fold
        original_messages: Original messages for full restoration (if available)

    Returns:
        Tuple of (restored messages, count of restored from folds)
    """
    restored = []
    restored_count = 0

    # Build lookup for fold anchors by fold_id
    anchor_by_id = {a["fold_id"]: a for a in fold_anchors}

    for msg in folded_messages:
        content = msg.get("content", "")
        meta = msg.get("meta", {})

        if isinstance(content, str) and content.startswith("[FOLD:") and "fold_id" in meta:
            fold_id = meta["fold_id"]
            anchor = anchor_by_id.get(fold_id)

            if anchor and original_messages:
                # Restore from original messages using covered_ids
                covered_ids = anchor.get("covered_ids", [])
                for orig_msg in original_messages:
                    if message_id(orig_msg) in covered_ids:
                        restored.append(orig_msg)
                        restored_count += 1
            elif anchor:
                # No original messages available, create placeholder
                restored.append({
                    "role": "system",
                    "content": f"[RESTORED FOLD:{fold_id}] {anchor.get('anchor_text', 'Folded content')}",
                    "meta": {"restored_from_fold": fold_id, "covered_ids": anchor.get("covered_ids", [])},
                })
                restored_count += len(anchor.get("covered_ids", []))
        else:
            restored.append(msg)

    return restored, restored_count


def search_folds(
    query: str,
    fold_anchors: list[dict[str, Any]],
    max_results: int = 10,
    min_score: float = 0.1,
) -> list[dict[str, Any]]:
    """Search fold anchors for relevance to a query.

    Args:
        query: Search query string
        fold_anchors: List of fold anchor dictionaries
        max_results: Maximum results to return
        min_score: Minimum relevance score (0-1)

    Returns:
        List of matching fold results with scores
    """
    query_lower = query.lower()
    query_terms = set(query_lower.split())

    results = []

    for anchor in fold_anchors:
        summary_lower = anchor.get("anchor_text", "").lower()
        anchor_terms = set(summary_lower.split())

        # Jaccard similarity
        intersection = query_terms & anchor_terms
        union = query_terms | anchor_terms
        jaccard = len(intersection) / len(union) if union else 0

        # Term frequency score
        tf_score = sum(summary_lower.count(term) for term in query_terms)
        tf_normalized = min(tf_score / 10, 1.0)

        # Combined score
        total_score = 0.7 * jaccard + 0.3 * tf_normalized

        if total_score >= min_score:
            results.append({
                "anchor_id": anchor.get("fold_id", ""),
                "summary": anchor.get("anchor_text", ""),
                "covered_message_ids": anchor.get("covered_ids", []),
                "start_idx": anchor.get("start_idx", 0),
                "end_idx": anchor.get("end_idx", 0),
                "original_tokens": anchor.get("original_tokens", 0),
                "folded_tokens": anchor.get("folded_tokens", 0),
                "score": round(total_score, 3),
            })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:max_results]


class SearchContextRequest(BaseModel):
    """Request to search compressed conversation context."""
    query: str = Field(..., description="Search query")
    fold_anchors: list[dict[str, Any]] = Field(..., description="Fold anchors from compressed history")
    max_results: int = Field(10, description="Maximum results to return")
    min_score: float = Field(0.1, description="Minimum relevance score (0-1)")


class SearchContextResult(BaseModel):
    """Single search result from a fold anchor."""
    anchor_id: str
    summary: str
    covered_message_ids: list[str]
    start_idx: int
    end_idx: int
    original_tokens: int
    folded_tokens: int
    score: float


class SearchContextResponse(BaseModel):
    """Response from search_context operation."""
    query: str
    results: list[SearchContextResult]
    total_anchors_searched: int
    results_count: int


def search_context(request: SearchContextRequest) -> SearchContextResponse:
    """Search compressed conversation folds for relevant context."""
    results = search_folds(
        query=request.query,
        fold_anchors=request.fold_anchors,
        max_results=request.max_results,
        min_score=request.min_score,
    )

    return SearchContextResponse(
        query=request.query,
        results=results,
        total_anchors_searched=len(request.fold_anchors),
        results_count=len(results),
    )

