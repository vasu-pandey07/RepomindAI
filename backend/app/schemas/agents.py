from pydantic import BaseModel, Field
from typing import List


class PRReviewRequest(BaseModel):
    repository_id: int
    changed_files: List[str] = Field(..., description="List of file paths that changed in the PR")


class PRReviewResponse(BaseModel):
    review: str
    issues_found: int


class TestGenerationRequest(BaseModel):
    repository_id: int
    file_path: str = Field(..., description="Target file path to generate unit tests for")


class TestGenerationResponse(BaseModel):
    tests: str


class DocumentationResponse(BaseModel):
    documentation: str
