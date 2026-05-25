"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import decode_token
from packages.db.base import get_sessionmaker
from packages.db.models import ProjectMember, User


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_project_member(
    project_id: int,
    db: DbSession,
    user: CurrentUser,
) -> ProjectMember:
    from sqlalchemy import select
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.user_id == user.id,
            ProjectMember.project_id == project_id,
        )
    )
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a project member")
    return member
