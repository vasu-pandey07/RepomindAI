from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ChatMessage, ChatSession, Repository, User
from app.dependencies import get_current_user
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionRead,
)
from app.services.rag_service import RepositoryRagService

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_owned_repository(db: Session, repository_id: int, user_id: int) -> Repository:
    repository = (
        db.query(Repository)
        .filter(Repository.id == repository_id, Repository.owner_id == user_id)
        .one_or_none()
    )
    if repository is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    return repository


def _build_session_title(question: str) -> str:
    title = question.strip().replace("\n", " ")
    if not title:
        return "Repository chat"

    return title[:80]


@router.post("", response_model=ChatResponse)
def chat_with_repository(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    _get_owned_repository(db, payload.repository_id, current_user.id)

    if payload.session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == payload.session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.repository_id == payload.repository_id,
            )
            .one_or_none()
        )
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    else:
        session = ChatSession(
            user_id=current_user.id,
            repository_id=payload.repository_id,
            title=_build_session_title(payload.question),
        )
        db.add(session)
        db.flush()

    try:
        rag_service = RepositoryRagService()
        rag_answer = rag_service.answer_question(db, payload.repository_id, payload.question)
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Repository chat failed.",
        ) from exc

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.question))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=rag_answer.answer))
    db.commit()
    db.refresh(session)

    return ChatResponse(answer=rag_answer.answer, sources=rag_answer.sources, session_id=session.id)


@router.post("/session", response_model=ChatSessionRead)
def create_chat_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSession:
    repository = _get_owned_repository(db, payload.repository_id, current_user.id)
    session = ChatSession(
        user_id=current_user.id,
        repository_id=repository.id,
        title=payload.title or f"Chat about {repository.name}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/session/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionDetail:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    return ChatSessionDetail(session=session, messages=messages)
