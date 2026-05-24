from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from apps.api.deps import CurrentUser, DbSession, require_project_member
from apps.api.schemas import CategoryRowOut, DayRowOut, ProjectSummaryOut
from apps.worker.tasks.reports import build_csv_bytes, build_xlsx_bytes
from packages.db.models import Expense, Project
from packages.domain.reports import summarize_expenses

router = APIRouter(prefix="/projects/{project_id}/report", tags=["reports"])


@router.get("/summary", response_model=ProjectSummaryOut)
async def report_summary(
    project_id: int, db: DbSession, user: CurrentUser,
) -> ProjectSummaryOut:
    await require_project_member(project_id, db, user)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    rows = await db.execute(select(Expense).where(Expense.project_id == project_id))
    summary = summarize_expenses(rows.scalars().all())
    return ProjectSummaryOut(
        project_id=project_id,
        total_minor=summary.total_minor,
        count=summary.count,
        currency=project.currency,
        by_category=[
            CategoryRowOut(category=r.category, total_minor=r.total_minor, count=r.count)
            for r in summary.by_category
        ],
        by_day=[
            DayRowOut(day=r.day, total_minor=r.total_minor, count=r.count)
            for r in summary.by_day
        ],
    )


@router.get("/export.csv")
async def export_csv(
    project_id: int, db: DbSession, user: CurrentUser,
) -> Response:
    await require_project_member(project_id, db, user)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    rows = await db.execute(
        select(Expense).where(Expense.project_id == project_id).order_by(Expense.paid_at)
    )
    payload = build_csv_bytes(project, rows.scalars().all())
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project.name)
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe}_report.csv"'},
    )


@router.get("/export.xlsx")
async def export_xlsx(
    project_id: int, db: DbSession, user: CurrentUser,
) -> Response:
    await require_project_member(project_id, db, user)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    rows = await db.execute(
        select(Expense).where(Expense.project_id == project_id).order_by(Expense.paid_at)
    )
    payload = build_xlsx_bytes(project, rows.scalars().all())
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project.name)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}_report.xlsx"'},
    )
