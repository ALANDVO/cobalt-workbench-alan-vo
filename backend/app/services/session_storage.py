"""Session storage service for persisting conversations and folds."""

import json
from datetime import datetime
from typing import Optional

from fastapi import Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Session, FoldAnchor, Message
from app.services.acp_compress import FoldAnchor as CompressFoldAnchor, CompressedConversation

class SessionStorage:
    """Handles persistence of sessions, folds, and messages."""

    def __init__(self, db):
        self._db = db

    def db_session(self):
        return self._db

    async def get_or_create_session(
        self, agent_namespace: str, conversation_id: str
    ) -> Session:
        """Get existing session or create new one."""
        result = await self._db.execute(
            select(Session).where(
                Session.agent_namespace == agent_namespace,
                Session.conversation_id == conversation_id,
            )
        )
        session = result.scalar_one_or_none()

        if session is None:
            session = Session(
                agent_namespace=agent_namespace,
                conversation_id=conversation_id,
            )
            self._db.add(session)
            await self._db.flush()

        return session

    async def get_session(self, agent_namespace: str, conversation_id: str) -> Optional[Session]:
        """Get session by namespace and conversation ID."""
        result = await self._db.execute(
            select(Session).where(
                Session.agent_namespace == agent_namespace,
                Session.conversation_id == conversation_id,
            )
        )
        return result.scalar_one_or_none()

    async def save_fold(
        self,
        session: Session,
        fold: CompressFoldAnchor | dict,
        messages: list[dict],
    ) -> FoldAnchor:
        """Save a fold anchor and its covered messages."""
        # Support both object with attributes and dict
        def get_attr(obj, key):
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        # Create fold anchor
        created_at_val = get_attr(fold, "created_at")
        if isinstance(created_at_val, (int, float)):
            created_at = datetime.fromtimestamp(created_at_val)
        elif isinstance(created_at_val, str):
            created_at = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
        else:
            created_at = datetime.utcnow()

        fold_anchor = FoldAnchor(
            session_id=session.id,
            fold_id=get_attr(fold, "fold_id"),
            anchor_text=get_attr(fold, "anchor_text"),
            covered_ids=json.dumps(get_attr(fold, "covered_ids")),
            token_count=get_attr(fold, "token_count"),
            created_at=created_at,
        )
        self._db.add(fold_anchor)
        await self._db.flush()

        # Save messages belonging to this fold
        for idx, msg in enumerate(messages):
            message_id = msg.get("id") or self._message_id(msg)
            message = Message(
                session_id=session.id,
                fold_id=get_attr(fold, "fold_id"),
                message_id=message_id,
                role=msg.get("role", "unknown"),
                content=msg.get("content", ""),
                meta=json.dumps(msg.get("meta", {})),
                token_count=msg.get("token_count", 0),
                created_at=datetime.utcnow(),
                sequence=idx,
            )
            self._db.add(message)

        session.updated_at = datetime.utcnow()
        return fold_anchor

    async def save_recent_messages(
        self, session: Session, messages: list[dict], start_sequence: int = 0
    ) -> list[Message]:
        """Save recent (unfolded) messages."""
        saved = []
        for idx, msg in enumerate(messages):
            message_id = msg.get("id") or self._message_id(msg)
            message = Message(
                session_id=session.id,
                fold_id=None,  # Recent messages have no fold
                message_id=message_id,
                role=msg.get("role", "unknown"),
                content=msg.get("content", ""),
                meta=json.dumps(msg.get("meta", {})),
                token_count=msg.get("token_count", 0),
                created_at=datetime.utcnow(),
                sequence=start_sequence + idx,
            )
            self._db.add(message)
            saved.append(message)
        session.updated_at = datetime.utcnow()
        return saved

    async def get_folds(self, session: Session) -> list[FoldAnchor]:
        """Get all fold anchors for a session."""
        result = await self._db.execute(
            select(FoldAnchor)
            .where(FoldAnchor.session_id == session.id)
            .order_by(FoldAnchor.created_at)
        )
        return list(result.scalars().all())

    async def get_fold_by_id(self, session: Session, fold_id: str) -> Optional[FoldAnchor]:
        """Get specific fold anchor by fold_id."""
        result = await self._db.execute(
            select(FoldAnchor).where(
                FoldAnchor.session_id == session.id,
                FoldAnchor.fold_id == fold_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_messages_for_fold(self, session: Session, fold_id: str) -> list[Message]:
        """Get all messages belonging to a specific fold."""
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session.id, Message.fold_id == fold_id)
            .order_by(Message.sequence)
        )
        return list(result.scalars().all())

    async def get_recent_messages(self, session: Session, limit: int) -> list[Message]:
        """Get most recent messages (those without fold_id)."""
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session.id, Message.fold_id.is_(None))
            .order_by(Message.sequence.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        return list(reversed(messages))  # Return in chronological order

    async def get_all_messages(self, session: Session) -> list[Message]:
        """Get all messages for a session in order."""
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.sequence)
        )
        return list(result.scalars().all())

    async def delete_session(self, session: Session) -> None:
        """Delete a session and all its data (cascades)."""
        await self._db.delete(session)

    @staticmethod
    def _message_id(message: dict) -> str:
        """Generate stable content-hash based ID for a message."""
        import hashlib
        content = json.dumps(message, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def to_compressed_conversation(self, session: Session, preserve_recent: int = 10) -> CompressedConversation:
        """Reconstruct CompressedConversation from stored session."""
        folds = await self.get_folds(session)
        recent_messages = await self.get_recent_messages(session, preserve_recent)

        fold_anchors = []
        for f in folds:
            messages = await self.get_messages_for_fold(session, f.fold_id)
            fold_anchors.append(
                CompressFoldAnchor(
                    fold_id=f.fold_id,
                    anchor_text=f.anchor_text,
                    covered_ids=json.loads(f.covered_ids),
                    token_count=f.token_count,
                    created_at=f.created_at.isoformat() + "Z",
                    message_count=len(messages),
                )
            )

        return CompressedConversation(
            folds=fold_anchors,
            recent_messages=[self._message_to_dict(m) for m in recent_messages],
            original_token_count=sum(f.token_count for f in fold_anchors)
            + sum(m.token_count for m in recent_messages),
            compressed_token_count=sum(f.token_count for f in fold_anchors)
            + sum(m.token_count for m in recent_messages),
            fold_id=fold_anchors[-1].fold_id if fold_anchors else "",
        )

    def _message_to_dict(self, message: Message) -> dict:
        """Convert Message model to dict."""
        return {
            "id": message.message_id,
            "role": message.role,
            "content": message.content,
            "meta": json.loads(message.meta) if message.meta else {},
            "token_count": message.token_count,
        }

async def get_session_storage():
    """Dependency injection for SessionStorage."""
    from app.core.database import async_session_maker
    async with async_session_maker() as session:
        yield SessionStorage(session)
