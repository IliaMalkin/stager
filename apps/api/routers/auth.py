from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DbSession
from apps.api.rate_limit import limiter
from apps.api.schemas import LoginRequest, TokenResponse, UserOut
from apps.api.security import issue_token, verify_password
from packages.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    # slowapi требует request + response параметры в signature чтобы инжектить
    # X-RateLimit-* headers. response используется неявно через slowapi.
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token, exp = issue_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, expires_at=exp)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
