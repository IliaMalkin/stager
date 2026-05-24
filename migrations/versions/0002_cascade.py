"""cascade deletes on project + user FKs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


_CASCADES = [
    # (table, fk_name_old, column, parent_table, parent_column, ondelete)
    ("project_members", "project_members_project_id_fkey", "project_id", "projects", "id", "CASCADE"),
    ("project_members", "project_members_user_id_fkey",    "user_id",    "users",    "id", "CASCADE"),
    ("active_context",  "active_context_user_id_fkey",     "user_id",    "users",    "id", "CASCADE"),
    ("active_context",  "active_context_current_project_id_fkey", "current_project_id", "projects", "id", "SET NULL"),
    ("expenses",        "expenses_project_id_fkey",        "project_id", "projects", "id", "CASCADE"),
    ("expenses",        "expenses_created_by_user_id_fkey","created_by_user_id", "users", "id", "RESTRICT"),
    ("expenses",        "expenses_receipt_id_fkey",        "receipt_id", "receipts","id", "SET NULL"),
    ("invites",         "invites_project_id_fkey",         "project_id", "projects", "id", "CASCADE"),
    ("invites",         "invites_issued_by_user_id_fkey",  "issued_by_user_id", "users", "id", "RESTRICT"),
    ("invites",         "invites_used_by_user_id_fkey",    "used_by_user_id",   "users", "id", "SET NULL"),
]


def upgrade() -> None:
    for table, old_name, col, parent_t, parent_c, action in _CASCADES:
        op.drop_constraint(old_name, table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_{col}_fkey", table, parent_t,
            [col], [parent_c], ondelete=action,
        )


def downgrade() -> None:
    for table, old_name, col, parent_t, parent_c, _action in _CASCADES:
        op.drop_constraint(f"{table}_{col}_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            old_name, table, parent_t, [col], [parent_c],
        )
