"""ACP fold-based compression service.

Implements content-hash anchored folding for conversation history compression.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


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
        return {
            "id": self.id,
            "summary": self.summary,
            "covered_message_ids": self.covered_message_ids,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "original_tokens": self.original_tokens,
            "folded_tokens": self.folded_tokens,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FoldAnchor":
        return cls(
            id=data["id"],
            summary=data["summary"],
            covered_message_ids=data["covered_message_ids"],
            start_idx=data["start_idx"],
            end_idx=data["end_idx"],
            original_tokens=data["original_tokens"],
            folded_tokens=data["folded_tokens"],
            created_at=data.get("created_at", time.time()),
        )


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
    content = message.get("content", "")
    if isinstance(content, str):
        return estimate_tokens(content)
    elif isinstance(content, list):
        # Handle multimodal content
        return sum(estimate_tokens(str(c)) for c in content)
    return 0


def summarize_messages(messages: list[dict[str, Any]]) -> str:
    """Create a summary of folded messages."""
    if not messages:
        return "Empty segment"

    roles = [m.get("role", "unknown") for m in messages]
    role_counts: dict[str, int] = {}
    for r in roles:
        role_counts[r] = role_counts.get(r, 0) + 1

    parts = [f"{count} {role}" for role, count in role_counts.items()]
    first_user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    preview = first_user[:100] + ("..." if len(first_user) > 100 else "")

    return f"{', '.join(parts)}: {preview}" if preview else f"{', '.join(parts)}"


def fold_conversation(
    messages: list[dict[str, Any]],
    preserve_recent: int = 10,
    target_ratio: float = 0.2,
) -> CompressedConversation:
    """Compress conversation using fold-based compression.

    Args:
        messages: Full conversation history
        preserve_recent: Number of recent messages to keep uncompressed
        target_ratio: Target compression ratio (folded/original)

    Returns:
        CompressedConversation with folded messages and anchors
    """
    if len(messages) <= preserve_recent:
        # Nothing to fold
        total_tokens = sum(count_message_tokens(m) for m in messages)
        return CompressedConversation(
            folded_messages=messages,
            fold_anchors=[],
            original_tokens=total_tokens,
            folded_tokens=total_tokens,
            compression_ratio=1.0,
            fold_id="",
        )

    # Split into foldable prefix and preserved suffix
    foldable = messages[:-preserve_recent]
    preserved = messages[-preserve_recent:]

    # Generate message IDs for all messages
    msg_ids = [message_id(m) for m in messages]

    # Group foldable messages into chunks for folding
    # Aim for chunks that compress to target_ratio
    fold_anchors: list[FoldAnchor] = []
    folded_prefix: list[dict[str, Any]] = []
    current_chunk: list[dict[str, Any]] = []
    current_chunk_ids: list[str] = []
    current_chunk_start = 0
    current_original_tokens = 0

    for i, msg in enumerate(foldable):
        msg_tokens = count_message_tokens(msg)
        current_chunk.append(msg)
        current_chunk_ids.append(msg_ids[i])
        current_original_tokens += msg_tokens

        # Check if chunk is large enough to fold
        # Target: folded tokens ≈ original * target_ratio
        # Summary tokens ≈ 50-100
        estimated_folded = 80  # summary token estimate
        if current_original_tokens * target_ratio >= estimated_folded and len(current_chunk) >= 3:
            # Create fold anchor
            anchor_id = hashlib.sha256(
                "".join(current_chunk_ids).encode()
            ).hexdigest()[:12]

            anchor = FoldAnchor(
                id=f"fold_{anchor_id}",
                summary=summarize_messages(current_chunk),
                covered_message_ids=current_chunk_ids,
                start_idx=current_chunk_start,
                end_idx=current_chunk_start + len(current_chunk) - 1,
                original_tokens=current_original_tokens,
                folded_tokens=estimated_folded,
            )
            fold_anchors.append(anchor)

            # Add summary message to folded prefix
            folded_prefix.append({
                "role": "system",
                "content": f"[Folded: {anchor.summary}]",
                "fold_anchor_id": anchor.id,
            })

            # Reset chunk
            current_chunk = []
            current_chunk_ids = []
            current_chunk_start = i + 1
            current_original_tokens = 0

    # Handle remaining messages in chunk
    if current_chunk:
        anchor_id = hashlib.sha256(
            "".join(current_chunk_ids).encode()
        ).hexdigest()[:12]
        anchor = FoldAnchor(
            id=f"fold_{anchor_id}",
            summary=summarize_messages(current_chunk),
            covered_message_ids=current_chunk_ids,
            start_idx=current_chunk_start,
            end_idx=current_chunk_start + len(current_chunk) - 1,
            original_tokens=current_original_tokens,
            folded_tokens=80,
        )
        fold_anchors.append(anchor)
        folded_prefix.append({
            "role": "system",
            "content": f"[Folded: {anchor.summary}]",
            "fold_anchor_id": anchor.id,
        })

    # Combine folded prefix with preserved messages
    folded_messages = folded_prefix + preserved

    # Calculate totals
    original_tokens = sum(count_message_tokens(m) for m in messages)
    folded_tokens = sum(count_message_tokens(m) for m in folded_messages)
    compression_ratio = folded_tokens / original_tokens if original_tokens > 0 else 0

    # Generate fold_id from all anchors
    fold_id = hashlib.sha256(
        "".join(a.id for a in fold_anchors).encode()
    ).hexdigest()[:16]

    return CompressedConversation(
        folded_messages=folded_messages,
        fold_anchors=fold_anchors,
        original_tokens=original_tokens,
        folded_tokens=folded_tokens,
        compression_ratio=compression_ratio,
        fold_id=f"fold_{fold_id}",
    )


def unfold_conversation(
    folded_messages: list[dict[str, Any]],
    fold_anchors: list[dict[str, Any]],
    original_messages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Restore original messages from folded representation.

    Note: Full decompression requires the original messages or a stored ledger.
    This implementation returns the folded messages with anchors expanded
    as placeholders when original_messages is not provided.

    Args:
        folded_messages: Messages with fold summary placeholders
        fold_anchors: Anchor metadata from compression
        original_messages: Original messages if available (from storage)

    Returns:
        Tuple of (restored_messages, restored_count)
    """
    if original_messages is not None:
        # Full restoration from stored originals
        return original_messages, len(original_messages)

    # Without originals, we can only expand anchor placeholders
    # into structured summaries (not full original content)
    restored: list[dict[str, Any]] = []
    restored_count = 0

    anchor_map = {a["id"]: a for a in fold_anchors}

    for msg in folded_messages:
        if msg.get("role") == "system" and "fold_anchor_id" in msg:
            anchor_id = msg["fold_anchor_id"]
            anchor = anchor_map.get(anchor_id)
            if anchor:
                # Expand to structured representation
                restored.append({
                    "role": "system",
                    "content": f"[Folded Segment: {anchor.get('summary', 'Unknown')}]",
                    "fold_anchor": anchor,
                    "covered_message_ids": anchor.get("covered_message_ids", []),
                    "original_tokens": anchor.get("original_tokens", 0),
                })
                restored_count += anchor.get("covered_message_count", len(anchor.get("covered_message_ids", [])))
            else:
                restored.append(msg)
        else:
            restored.append(msg)

    return restored, restored_count


