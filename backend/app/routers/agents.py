from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Repository, User, GeneratedDocument, GeneratedPRReview, GeneratedTestFile
from app.dependencies import get_current_user
from app.schemas.agents import (
    PRReviewRequest,
    PRReviewResponse,
    TestGenerationRequest,
    TestGenerationResponse,
    DocumentationResponse,
)
from app.graphs.documentation_graph import documentation_graph
from app.graphs.pr_review_graph import pr_review_graph
from app.graphs.test_generation_graph import test_generation_graph

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/documentation/{repository_id}", response_model=DocumentationResponse)
async def generate_documentation(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify repository ownership
    repo = (
        db.query(Repository)
        .filter(Repository.id == repository_id, Repository.owner_id == current_user.id)
        .first()
    )
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found or unauthorized.",
        )

    # Initialize and execute documentation graph
    initial_state = {
        "repository_id": repository_id,
        "file_path": None,
        "changed_files": None,
        "context": "",
        "analysis": "",
        "result": "",
        "issues_found": 0,
        "sources": [],
    }

    try:
        final_state = await documentation_graph.ainvoke(
            initial_state,
            config={"configurable": {"db": db}},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Documentation agent failed: {str(exc)}",
        ) from exc

    doc_content = final_state.get("result", "")

    # Save to database
    generated_doc = GeneratedDocument(
        repository_id=repository_id,
        title="Repository Architecture & Setup Guide",
        content=doc_content,
    )
    db.add(generated_doc)
    db.commit()

    return DocumentationResponse(documentation=doc_content)


@router.post("/pr-review", response_model=PRReviewResponse)
async def run_pr_review(
    req: PRReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify repository ownership
    repo = (
        db.query(Repository)
        .filter(Repository.id == req.repository_id, Repository.owner_id == current_user.id)
        .first()
    )
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found or unauthorized.",
        )

    # Initialize and execute PR Review graph
    initial_state = {
        "repository_id": req.repository_id,
        "file_path": None,
        "changed_files": req.changed_files,
        "context": "",
        "analysis": "",
        "result": "",
        "issues_found": 0,
        "sources": [],
    }

    try:
        final_state = await pr_review_graph.ainvoke(
            initial_state,
            config={"configurable": {"db": db}},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PR Review agent failed: {str(exc)}",
        ) from exc

    review_text = final_state.get("result", "")
    issues_found = final_state.get("issues_found", 0)

    # Save to database
    generated_review = GeneratedPRReview(
        repository_id=req.repository_id,
        review=review_text,
        issues_found=issues_found,
    )
    db.add(generated_review)
    db.commit()

    return PRReviewResponse(review=review_text, issues_found=issues_found)


@router.post("/tests", response_model=TestGenerationResponse)
async def generate_tests(
    req: TestGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify repository ownership
    repo = (
        db.query(Repository)
        .filter(Repository.id == req.repository_id, Repository.owner_id == current_user.id)
        .first()
    )
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found or unauthorized.",
        )

    # Initialize and execute Test Generation graph
    initial_state = {
        "repository_id": req.repository_id,
        "file_path": req.file_path,
        "changed_files": None,
        "context": "",
        "analysis": "",
        "result": "",
        "issues_found": 0,
        "sources": [],
    }

    try:
        final_state = await test_generation_graph.ainvoke(
            initial_state,
            config={"configurable": {"db": db}},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test generation agent failed: {str(exc)}",
        ) from exc

    test_content = final_state.get("result", "")

    # Save to database
    generated_test = GeneratedTestFile(
        repository_id=req.repository_id,
        file_path=req.file_path,
        tests=test_content,
    )
    db.add(generated_test)
    db.commit()

    return TestGenerationResponse(tests=test_content)
