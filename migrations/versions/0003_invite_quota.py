"""invite max_projects + user project_quota

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # invites: сколько проектов может создать redeemer
    op.add_column(
        "invites",
        sa.Column("max_projects", sa.Integer(), nullable=True),
    )
    # users: оставшаяся квота на создание новых проектов; NULL = unlimited
    op.add_column(
        "users",
        sa.Column("project_quota", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "project_quota")
    op.drop_column("invites", "max_projects")
