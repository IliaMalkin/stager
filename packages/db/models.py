"""All MVP models in one file. Split per-domain when it gets >500 LOC."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, Index, Integer,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str | None] = mapped_column(String(256))
    locale: Mapped[str] = mapped_column(String(8), default="ru")
    email: Mapped[str | None] = mapped_column(String(256), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="user")  # admin | user
    # NULL = unlimited (whitelisted owners). Целое число — сколько ЕЩЁ проектов
    # юзер может создать (декрементится при /newproject).
    project_quota: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    budget_minor: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | completed | archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectMember(Base):
    __tablename__ = "project_members"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="editor")  # owner | editor | viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActiveContext(Base):
    __tablename__ = "active_context"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    current_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))
    minio_key: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str | None] = mapped_column(String(256))
    ocr_status: Mapped[str] = mapped_column(String(16), default="pending")
    ocr_attempts: Mapped[int] = mapped_column(Integer, default=0)
    ocr_provider: Mapped[str | None] = mapped_column(String(64))
    raw_ocr_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(1024))
    paid_at: Mapped[date] = mapped_column(Date)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(16))  # bot_photo | bot_text | admin_web
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"))
    raw_ocr_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_expenses_project_paid", "project_id", "paid_at"),
        Index("ix_expenses_project_category", "project_id", "category"),
    )


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    role: Mapped[str] = mapped_column(String(16), default="editor")
    # Сколько проектов сможет создать redeemer (NULL = unlimited).
    # Применяется только при первом redeem (если User новый).
    max_projects: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
