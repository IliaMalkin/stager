"""initial schema — all MVP tables

Revision ID: 0001
Revises:
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, index=True),
        sa.Column("username", sa.String(128)),
        sa.Column("full_name", sa.String(256)),
        sa.Column("locale", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("email", sa.String(256), unique=True),
        sa.Column("password_hash", sa.String(256)),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("budget_minor", sa.BigInteger()),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "project_members",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="editor"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "active_context",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("current_project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expense_id", sa.Integer()),  # FK добавим позже из-за круговой ссылки
        sa.Column("minio_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(256)),
        sa.Column("ocr_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("ocr_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_provider", sa.String(64)),
        sa.Column("raw_ocr_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("description", sa.String(1024)),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("receipts.id")),
        sa.Column("raw_ocr_json", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expenses_project_paid", "expenses", ["project_id", "paid_at"])
    op.create_index("ix_expenses_project_category", "expenses", ["project_id", "category"])

    # back-reference: receipts.expense_id → expenses.id
    op.create_foreign_key(
        "fk_receipts_expense", "receipts", "expenses",
        ["expense_id"], ["id"], use_alter=True,
    )

    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("issued_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("role", sa.String(16), nullable=False, server_default="editor"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("invites")
    op.drop_constraint("fk_receipts_expense", "receipts", type_="foreignkey")
    op.drop_index("ix_expenses_project_category", table_name="expenses")
    op.drop_index("ix_expenses_project_paid", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("receipts")
    op.drop_table("active_context")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
