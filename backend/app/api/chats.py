"""
Chat session and messaging API router with SSE mock streaming and file upload.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.session import get_current_owner_hash
from backend.app.db.models import Chat, Message, UploadedFile
from backend.app.db.session import get_db
from backend.app.core.security.masking import pii_masker
from backend.app.core.parsers.factory import parse_and_mask_document
from backend.app.agents.requirement_engineer import requirement_engineer_agent

router = APIRouter(prefix="/chats", tags=["chats"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Request & Response Models
class CreateChatRequest(BaseModel):
    title: Optional[str] = Field(default="New Financial Requirement")


class UpdateChatRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    acting_role: Optional[str] = Field(default="Product Owner")


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    state: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    role: str
    sender_agent: Optional[str] = None
    content_masked: str
    action_cards: List[dict] = []
    created_at: datetime


class UploadedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    filename: str
    file_size: int
    mime_type: str
    created_at: datetime


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: Optional[CreateChatRequest] = None,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """Create a new chat session bound to the current anonymous owner token."""
    title = payload.title if payload and payload.title else "New Financial Requirement"
    chat = Chat(
        id=str(uuid.uuid4()),
        owner_token_hash=owner_hash,
        title=title,
        state="INTAKE",
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("", response_model=List[ChatResponse])
def list_chats(
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """List all active non-deleted chats owned by the caller."""
    chats = (
        db.query(Chat)
        .filter(Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .order_by(Chat.updated_at.desc())
        .all()
    )
    return chats


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(
    chat_id: str,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """Get chat details with tenant isolation."""
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.patch("/{chat_id}", response_model=ChatResponse)
def update_chat(
    chat_id: str,
    payload: UpdateChatRequest,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """Rename chat session."""
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    chat.title = payload.title.strip()
    chat.updated_at = utcnow()
    db.commit()
    db.refresh(chat)
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: str,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """Soft delete chat session."""
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    chat.deleted_at = utcnow()
    db.commit()
    return None


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
def list_messages(
    chat_id: str,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """Retrieve message history for an isolated chat."""
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    result = []
    for m in messages:
        cards = []
        if m.action_cards_json:
            try:
                cards = json.loads(m.action_cards_json)
            except Exception:
                cards = []
        result.append(
            MessageResponse(
                id=m.id,
                chat_id=m.chat_id,
                role=m.role,
                sender_agent=m.sender_agent,
                content_masked=m.content_masked,
                action_cards=cards,
                created_at=m.created_at,
            )
        )
    return result


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """
    Save user message and stream assistant response via Server-Sent Events (SSE).
    Phase 6: Uses RequirementEngineerAgent for grouped questions, requirement extraction, and assumptions.
    """
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. PII masking on incoming content
    masked_content, _ = pii_masker.mask(payload.content)

    # 2. Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        chat_id=chat_id,
        role="user",
        sender_agent="stakeholder",
        content_masked=masked_content,
        created_at=utcnow(),
    )
    db.add(user_msg)
    chat.updated_at = utcnow()
    db.commit()

    # 3. Check for uploaded files in this chat
    uploaded_records = db.query(UploadedFile).filter(UploadedFile.chat_id == chat_id).all()
    parsed_chunks = []
    for rec in uploaded_records:
        if os.path.exists(rec.file_path):
            try:
                chunks = parse_and_mask_document(rec.file_path, rec.mime_type)
                parsed_chunks.extend(chunks)
            except Exception:
                pass

    # 4. Invoke Requirement Engineer Agent
    result = requirement_engineer_agent.process_chat_message(
        db=db,
        chat=chat,
        user_message=user_msg,
        uploaded_chunks=parsed_chunks if parsed_chunks else None
    )
    resp_text = result["text"]
    action_cards = result["action_cards"]

    asst_msg_id = str(uuid.uuid4())

    async def event_generator():
        # Yield start event
        yield f"event: start\ndata: {json.dumps({'message_id': asst_msg_id})}\n\n"

        # Stream tokens in words/chunks
        words = resp_text.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.01)
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        # Yield action cards
        yield f"event: action_cards\ndata: {json.dumps({'action_cards': action_cards})}\n\n"

        # Save assistant message to DB
        asst_msg = Message(
            id=asst_msg_id,
            chat_id=chat_id,
            role="assistant",
            sender_agent="requirement_engineer",
            content_masked=resp_text,
            action_cards_json=json.dumps(action_cards),
            created_at=utcnow(),
        )
        db.add(asst_msg)
        db.commit()

        # Yield completion
        yield f"event: done\ndata: {json.dumps({'message_id': asst_msg_id, 'status': 'completed'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{chat_id}/upload", response_model=UploadedFileResponse)
async def upload_file(
    chat_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """
    Handle paperclip file upload (stores file only in storage/uploads/, records metadata).
    """
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(settings.STORAGE_UPLOADS_DIR, safe_filename)

    contents = await file.read()
    file_size = len(contents)

    with open(file_path, "wb") as f:
        f.write(contents)

    record = UploadedFile(
        id=file_id,
        chat_id=chat_id,
        filename=file.filename or "unknown_file",
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        created_at=utcnow(),
    )
    db.add(record)
    chat.updated_at = utcnow()
    db.commit()
    db.refresh(record)

    return record
