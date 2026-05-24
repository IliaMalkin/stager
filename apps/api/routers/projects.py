from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DbSession, require_project_member
from apps.api.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from packages.db.models import Project, ProjectMember
from packages.domain.quota import QuotaExceeded, check_quota, decrement_quota

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: DbSession, user: CurrentUser) -> list[Project]:
    rows = await db.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
    )
    return list(rows.scalars().all())


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db: DbSession, user: CurrentUser) -> Project:
    try:
        check_quota(user.project_quota)
    except QuotaExceeded as exc:
        from fastapi import HTTPException
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"project quota exceeded: {exc.quota}") from exc
    project = Project(
        owner_user_id=user.id,
        name=body.name,
        currency=body.currency,
        budget_minor=body.budget_minor,
        status="active",
    )
    db.add(project)
    await db.flush()
    db.add(ProjectMember(user_id=user.id, project_id=project.id, role="owner"))
    user.project_quota = decrement_quota(user.project_quota)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, db: DbSession, user: CurrentUser) -> Project:
    await require_project_member(project_id, db, user)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int, body: ProjectUpdate, db: DbSession, user: CurrentUser,
) -> Project:
    member = await require_project_member(project_id, db, user)
    if member.role not in ("owner", "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read-only role")
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if body.name is not None:
        project.name = body.name
    if body.status is not None:
        project.status = body.status
    if body.budget_minor is not None:
        project.budget_minor = body.budget_minor
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: DbSession, user: CurrentUser) -> None:
    member = await require_project_member(project_id, db, user)
    if member.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner only")
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await db.delete(project)
    await db.commit()
