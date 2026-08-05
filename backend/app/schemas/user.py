from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    id: int
    github_id: int
    username: str
    email: str | None
    avatar_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryRead(BaseModel):
    id: int
    github_repo_id: int
    name: str
    full_name: str
    language: str | None
    stars: int
    forks: int
    description: str | None
    owner_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RepositoryIndexResponse(BaseModel):
    files_processed: int
    status: str


class RepositoryIndexStatus(BaseModel):
    repository_id: int
    files: int
    chunks: int
    indexed: bool
