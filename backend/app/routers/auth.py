import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings, settings
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.schemas.user import UserRead
from app.services.github_service import fetch_github_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/github/login")
async def github_login(request: Request) -> RedirectResponse:
    current_settings = get_settings()
    redirect_uri = f"{current_settings.frontend_url}/auth/github/callback"
    github_auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={current_settings.github_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope=read:user%20user:email%20repo"
    )
    return RedirectResponse(github_auth_url)


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    current_settings = get_settings()
    if error or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub authorization rejected: {error or 'No code provided'}",
        )

    # Direct exchange with GitHub OAuth API (session-independent)
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": current_settings.github_client_id,
                "client_secret": current_settings.github_client_secret,
                "code": code,
                "redirect_uri": f"{current_settings.frontend_url}/auth/github/callback",
            },
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            err_msg = token_data.get("error_description") or token_data.get("error") or "Failed to exchange code for token"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

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
    frontend_callback_url = f"{current_settings.frontend_url}/auth/callback?token={jwt_token}"
    return RedirectResponse(frontend_callback_url)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
