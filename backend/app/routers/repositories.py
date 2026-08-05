from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import CodeChunk, CodeFile, Repository, User
from app.dependencies import get_current_user
from app.schemas.user import RepositoryIndexResponse, RepositoryIndexStatus, RepositoryRead
from app.services.github_service import fetch_github_repositories
from app.services.repository_indexer import RepositoryIndexer

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("/sync", response_model=list[RepositoryRead])
async def sync_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Repository]:
    try:
        github_repositories = await fetch_github_repositories(current_user.access_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch repositories from GitHub.",
        ) from exc

    existing_repositories = {
        repo.github_repo_id: repo
        for repo in db.query(Repository).filter(Repository.owner_id == current_user.id).all()
    }

    for item in github_repositories:
        github_repo_id = int(item["id"])
        repository = existing_repositories.get(github_repo_id)
        values = {
            "github_repo_id": github_repo_id,
            "name": item.get("name") or "",
            "full_name": item.get("full_name") or "",
            "language": item.get("language"),
            "stars": int(item.get("stargazers_count") or 0),
            "forks": int(item.get("forks_count") or 0),
            "description": item.get("description"),
            "owner_id": current_user.id,
        }

        if repository is None:
            db.add(Repository(**values))
        else:
            for key, value in values.items():
                setattr(repository, key, value)

    db.commit()

    return (
        db.query(Repository)
        .filter(Repository.owner_id == current_user.id)
        .order_by(Repository.stars.desc(), Repository.name.asc())
        .all()
    )


@router.get("", response_model=list[RepositoryRead])
def list_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Repository]:
    return (
        db.query(Repository)
        .filter(Repository.owner_id == current_user.id)
        .order_by(Repository.stars.desc(), Repository.name.asc())
        .all()
    )


@router.post("/{repository_id}/index", response_model=RepositoryIndexResponse)
def index_repository(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryIndexResponse:
    repository = (
        db.query(Repository)
        .filter(Repository.id == repository_id, Repository.owner_id == current_user.id)
        .one_or_none()
    )
    if repository is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    try:
        indexer = RepositoryIndexer()
        result = indexer.index_repository(db, repository, current_user)
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Repository indexing failed.",
        ) from exc

    return RepositoryIndexResponse(files_processed=result.files_processed, status="success")


@router.get("/{repository_id}/index-status", response_model=RepositoryIndexStatus)
def get_repository_index_status(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryIndexStatus:
    repository = (
        db.query(Repository)
        .filter(Repository.id == repository_id, Repository.owner_id == current_user.id)
        .one_or_none()
    )
    if repository is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    files = db.query(CodeFile).filter(CodeFile.repository_id == repository_id).count()
    chunks = (
        db.query(CodeChunk)
        .join(CodeFile, CodeChunk.file_id == CodeFile.id)
        .filter(CodeFile.repository_id == repository_id)
        .count()
    )

    return RepositoryIndexStatus(
        repository_id=repository_id,
        files=files,
        chunks=chunks,
        indexed=files > 0 and chunks > 0,
    )
