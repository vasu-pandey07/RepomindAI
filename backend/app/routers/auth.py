from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.schemas.user import UserRead
from app.services.github_service import fetch_github_user, oauth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/github/login")
async def github_login(request: Request) -> RedirectResponse:
    redirect_uri = f"{settings.backend_url}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth authorization failed.",
        ) from exc

    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub did not return an access token.",
        )

    github_user = await fetch_github_user(access_token)
    github_id = github_user.get("id")
    username = github_user.get("login")
    if github_id is None or username is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GitHub profile.")

    user = db.query(User).filter(User.github_id == github_id).one_or_none()
    if user is None:
        user = User(
            github_id=github_id,
            username=username,
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
            access_token=access_token,
        )
        db.add(user)
    else:
        user.username = username
        user.email = github_user.get("email")
        user.avatar_url = github_user.get("avatar_url")
        user.access_token = access_token

    db.commit()
    db.refresh(user)

    jwt_token = create_access_token(str(user.id))
    frontend_callback_url = f"{settings.frontend_url}/auth/callback?token={jwt_token}"
    return RedirectResponse(frontend_callback_url)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
