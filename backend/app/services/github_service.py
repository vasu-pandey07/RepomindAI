from typing import Any

import httpx
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings


oauth = OAuth()
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email repo"},
)


async def fetch_github_user(access_token: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        user_response = await client.get("https://api.github.com/user", headers=headers)
        user_response.raise_for_status()
        user = user_response.json()

        if not user.get("email"):
            emails_response = await client.get("https://api.github.com/user/emails", headers=headers)
            emails_response.raise_for_status()
            emails = emails_response.json()
            primary_email = next(
                (item["email"] for item in emails if item.get("primary") and item.get("verified")),
                None,
            )
            user["email"] = primary_email

        return user


async def fetch_github_repositories(access_token: str) -> list[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repositories: list[dict[str, Any]] = []
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            response = await client.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={
                    "affiliation": "owner,collaborator,organization_member",
                    "sort": "updated",
                    "per_page": 100,
                    "page": page,
                },
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break

            repositories.extend(batch)
            if len(batch) < 100:
                break

            page += 1

    return repositories
