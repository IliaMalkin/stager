"""Password hashing + JWT issuing/verifying."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

_JWT_ALG = "HS256"


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _ttl_hours() -> int:
    return int(os.getenv("JWT_EXP_HOURS", "168"))


def issue_token(*, user_id: int, role: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=_ttl_hours())
    payload = {"sub": str(user_id), "role": role, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    token = jwt.encode(payload, _secret(), algorithm=_JWT_ALG)
    return token, exp


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _secret(), algorithms=[_JWT_ALG])
    except JWTError:
        return None
