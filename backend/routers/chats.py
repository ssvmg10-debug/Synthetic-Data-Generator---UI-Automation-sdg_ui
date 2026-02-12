"""
Chat / Session / State management
List, create, get, delete chat sessions and messages. Used by UI for ChatGPT-style history.
Synthetic Data Agent and UI Automation Agent each have separate chat lists (filtered by agent_type).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
from db import get_db
from models import ChatSession, ChatMessage
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== REQUEST/RESPONSE MODELS ==========

class ChatSessionCreate(BaseModel):
    agent_type: str  # 'synthetic' | 'ui-automation'
    title: Optional[str] = None


class ChatMessageCreate(BaseModel):
    sender: str  # 'user' | 'agent'
    text: str
    payload: Optional[Dict[str, Any]] = None


class ChatMessageOut(BaseModel):
    id: int
    sender: str
    text: str
    payload: Optional[Dict[str, Any]] = None
    created_at: str

    class Config:
        from_attributes = True


class ChatSessionOut(BaseModel):
    id: int
    agent_type: str
    title: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int = 0

    class Config:
        from_attributes = True


class ChatSessionWithMessagesOut(ChatSessionOut):
    messages: List[ChatMessageOut] = []


# ========== ENDPOINTS ==========


@router.get("", response_model=List[ChatSessionOut])
def list_chats(
    agent_type: Optional[str] = Query(None, description="Required: synthetic or ui-automation (keeps Data vs Automation chats separate)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List chat sessions (newest first). agent_type is required so Synthetic Data and UI Automation maintain separate lists."""
    if not agent_type or agent_type not in ("synthetic", "ui-automation"):
        raise HTTPException(
            status_code=400,
            detail="Query param agent_type is required and must be 'synthetic' or 'ui-automation'",
        )
    q = db.query(ChatSession).filter(ChatSession.agent_type == agent_type)
    sessions = q.order_by(desc(ChatSession.updated_at)).limit(limit).all()
    out = []
    for s in sessions:
        count = db.query(ChatMessage).filter(ChatMessage.chat_id == s.id).count()
        out.append(ChatSessionOut(
            id=s.id,
            agent_type=s.agent_type,
            title=s.title,
            created_at=s.created_at.isoformat() if s.created_at else "",
            updated_at=s.updated_at.isoformat() if s.updated_at else "",
            message_count=count,
        ))
    return out


@router.get("/{chat_id}", response_model=ChatSessionWithMessagesOut)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    """Get one chat session with all messages (for loading a previous chat in UI)."""
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at).all()
    return ChatSessionWithMessagesOut(
        id=session.id,
        agent_type=session.agent_type,
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
        message_count=len(messages),
        messages=[
            ChatMessageOut(
                id=m.id,
                sender=m.sender,
                text=m.text,
                payload=m.payload,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in messages
        ],
    )


@router.post("", response_model=ChatSessionOut)
def create_chat(body: ChatSessionCreate, db: Session = Depends(get_db)):
    """Create a new chat session (e.g. when user starts a new conversation)."""
    session = ChatSession(agent_type=body.agent_type, title=body.title or "New chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionOut(
        id=session.id,
        agent_type=session.agent_type,
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
        message_count=0,
    )


@router.post("/{chat_id}/messages", response_model=ChatMessageOut)
def add_message(chat_id: int, body: ChatMessageCreate, db: Session = Depends(get_db)):
    """Append a message to a chat (user or agent). Used by backend after workflow; UI can use for optimistic add."""
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found")
    msg = ChatMessage(chat_id=chat_id, sender=body.sender, text=body.text, payload=body.payload)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return ChatMessageOut(
        id=msg.id,
        sender=msg.sender,
        text=msg.text,
        payload=msg.payload,
        created_at=msg.created_at.isoformat() if msg.created_at else "",
    )


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """Delete a chat session and all its messages."""
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.delete(session)
    db.commit()
    return None


# ========== HELPERS FOR OTHER ROUTERS ==========

def get_or_create_chat_for_agent(db: Session, agent_type: str, first_user_text: str) -> int:
    """Create a new chat and return its id. Title from first 80 chars of user text."""
    title = (first_user_text[:80] + "…") if len(first_user_text) > 80 else first_user_text
    session = ChatSession(agent_type=agent_type, title=title or "New chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session.id


def _touch_session_updated_at(db: Session, chat_id: int) -> None:
    """Update chat session updated_at so list order (newest first) is correct."""
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if chat:
        chat.updated_at = datetime.utcnow()
        db.commit()


def ensure_chat_and_append_user_message(db: Session, chat_id: Optional[int], agent_type: str, user_text: str) -> int:
    """If chat_id given, append user message and return it. Else create new chat, append user message, return new id.
    agent_type must be 'synthetic' or 'ui-automation' so Synthetic Data and UI Automation keep separate chats."""
    if chat_id:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            chat_id = None
    if not chat_id:
        title = (user_text[:80] + "…") if len(user_text) > 80 else user_text
        chat = ChatSession(agent_type=agent_type, title=title or "New chat")
        db.add(chat)
        db.commit()
        db.refresh(chat)
        chat_id = chat.id
    msg = ChatMessage(chat_id=chat_id, sender="user", text=user_text, payload=None)
    db.add(msg)
    db.commit()
    _touch_session_updated_at(db, chat_id)
    return chat_id


def append_agent_message(db: Session, chat_id: int, text: str, payload: Optional[dict] = None) -> None:
    """Append an agent message to an existing chat. Updates session.updated_at for list order."""
    msg = ChatMessage(chat_id=chat_id, sender="agent", text=text, payload=payload)
    db.add(msg)
    db.commit()
    _touch_session_updated_at(db, chat_id)
