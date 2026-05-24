from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DbSession, require_project_member
from apps.api.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate
from packages.db.models import Expense, Project

router = APIRouter(tags=["expenses"])


@router.get("/projects/{project_id}/expenses", response_model=list[ExpenseOut])
async def list_expenses(
    project_id: int,
    db: DbSession,
    user: CurrentUser,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    category: str | None = None,
    source: str | None = None,
) -> list[Expense]:
    await require_project_member(project_id, db, user)
    stmt = select(Expense).where(Expense.project_id == project_id)
    if date_from is not None:
        stmt = stmt.where(Expense.paid_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.paid_at <= date_to)
    if category:
        stmt = stmt.where(Expense.category == category)
    if source:
        stmt = stmt.where(Expense.source == source)
    stmt = stmt.order_by(Expense.paid_at.desc(), Expense.id.desc())
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


@router.post(
    "/projects/{project_id}/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    project_id: int, body: ExpenseCreate, db: DbSession, user: CurrentUser,
) -> Expense:
    member = await require_project_member(project_id, db, user)
    if member.role not in ("owner", "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read-only role")
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    expense = Expense(
        project_id=project_id,
        amount_minor=body.amount_minor,
        currency=project.currency,
        category=body.category,
        description=body.description,
        paid_at=body.paid_at,
        created_by_user_id=user.id,
        source="admin_web",
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: int, body: ExpenseUpdate, db: DbSession, user: CurrentUser,
) -> Expense:
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    member = await require_project_member(expense.project_id, db, user)
    if member.role not in ("owner", "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read-only role")
    if body.amount_minor is not None:
        expense.amount_minor = body.amount_minor
    if body.category is not None:
        expense.category = body.category
    if body.description is not None:
        expense.description = body.description
    if body.paid_at is not None:
        expense.paid_at = body.paid_at
    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: int, db: DbSession, user: CurrentUser) -> None:
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    member = await require_project_member(expense.project_id, db, user)
    if member.role not in ("owner", "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read-only role")
    await db.delete(expense)
    await db.commit()
