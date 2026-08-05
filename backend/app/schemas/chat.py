from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    repository_id: int
    question: str = Field(..., min_length=1)
    session_id: int | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    session_id: int


class ChatSessionCreate(BaseModel):
    repository_id: int
    title: str | None = None


class ChatSessionRead(BaseModel):
    id: int
    user_id: int
    repository_id: int
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetail(BaseModel):
    session: ChatSessionRead
    messages: list[ChatMessageRead]
