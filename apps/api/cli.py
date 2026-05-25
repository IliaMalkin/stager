"""CLI: `python -m apps.api.cli create-admin <email> <password>` etc."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from apps.api.security import hash_password
from packages.db.base import get_sessionmaker
from packages.db.models import User


async def _create_admin(email: str, password: str, full_name: str | None = None) -> None:
    async with get_sessionmaker()() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            existing.password_hash = hash_password(password)
            existing.role = "admin"
            if full_name:
                existing.full_name = full_name
            await session.commit()
            print(f"updated existing user {email} → admin")
            return
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role="admin",
        )
        session.add(user)
        await session.commit()
        print(f"created admin {email}")


def main() -> None:
    if len(sys.argv) < 2:
        _usage()
    cmd = sys.argv[1]
    if cmd == "create-admin":
        if len(sys.argv) < 4:
            _usage()
        email = sys.argv[2]
        password = sys.argv[3]
        full_name = sys.argv[4] if len(sys.argv) > 4 else None
        asyncio.run(_create_admin(email, password, full_name))
    else:
        _usage()


def _usage() -> None:
    print("Usage:")
    print("  python -m apps.api.cli create-admin <email> <password> [full_name]")
    sys.exit(2)


if __name__ == "__main__":
    main()
