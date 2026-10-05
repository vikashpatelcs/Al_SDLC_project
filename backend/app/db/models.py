"""
SQLAlchemy database models for persistence (Phase 2 minimal persistence).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_token_hash = Column(String(64), index=True, nullable=False)
    title = Column(String(255), nullable=False, default="New Financial Requirement")
    state = Column(String(64), nullable=False, default="INTAKE")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")
    files = relationship("UploadedFile", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # user, assistant, system
    sender_agent = Column(String(64), nullable=True)
    content_masked = Column(Text, nullable=False)
    action_cards_json = Column(Text, nullable=True)  # JSON-encoded array of ActionCard objects
    created_at = Column(DateTime, default=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="messages")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="files")
