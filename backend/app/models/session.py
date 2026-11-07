"""Database models for session persistence."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Index,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Session(Base):
    """Session keyed by (agent_namespace, conversation_id)."""

    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("agent_namespace", "conversation_id", name="uq_session_ns_conv"),
        Index("ix_session_agent_namespace", "agent_namespace"),
        Index("ix_session_updated_at", "updated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_namespace = Column(String(255), nullable=False)
    conversation_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    meta = Column(Text, default="{}")  # JSON metadata

    folds = relationship("FoldAnchor", back_populates="session", cascade="all, delete-orphan")


class FoldAnchor(Base):
    """Fold anchor tracking covered message IDs and summary."""

    __tablename__ = "fold_anchors"
    __table_args__ = (
        Index("ix_fold_anchor_session_id", "session_id"),
        Index("ix_fold_anchor_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    fold_id = Column(String(64), nullable=False)  # Content-hash based
    anchor_text = Column(Text, nullable=False)  # Summary/anchor for search
    covered_ids = Column(Text, nullable=False)  # JSON array of message IDs
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="folds")


class Message(Base):
    """Individual message storage for decompression."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_message_session_id", "session_id"),
        Index("ix_message_fold_id", "fold_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    fold_id = Column(String(64), nullable=True)  # Which fold this message belongs to (None = recent)
    message_id = Column(String(64), nullable=False)  # Content-hash based
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    meta = Column(Text, default="{}")  # JSON metadata
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sequence = Column(Integer, nullable=False)  # Order within session

