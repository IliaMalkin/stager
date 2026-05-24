from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status

from apps.api.deps import CurrentUser, DbSession, require_project_member
from apps.api.schemas import InviteCreate, InviteOut
from packages.db.models import Invite

router = APIRouter(prefix="/invites", tags=["invites"])


@router.post("", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: InviteCreate, db: DbSession, user: CurrentUser,
) -> InviteOut:
    if body.project_id is not None:
        member = await require_project_member(body.project_id, db, user)
        if member.role != "owner":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "owner only")
    elif user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only for global invites")

    token = secrets.token_urlsafe(24)[:48]
    expires = datetime.now(timezone.utc) + timedelta(hours=body.ttl_hours)
    invite = Invite(
        token=token,
        issued_by_user_id=user.id,
        project_id=body.project_id,
        role=body.role,
        max_projects=body.max_projects,
        expires_at=expires,
    )
    db.add(invite)
    await db.commit()

    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "stager_bot")
    url = f"https://t.me/{bot_username}?start={token}"
    return InviteOut(
        token=token, url=url, expires_at=expires,
        project_id=body.project_id, role=body.role,
        max_projects=body.max_projects,
    )
