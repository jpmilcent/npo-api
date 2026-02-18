"""Add users

Revision ID: cbc74160f60a
Revises: d18168929294
Create Date: 2026-02-08 22:10:20.061181

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cbc74160f60a"
down_revision: str | Sequence[str] | None = "d18168929294"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("firstname", sa.String(length=150), nullable=True),
        sa.Column("lastname", sa.String(length=150), nullable=True),
        sa.Column("picture_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False),
        sa.Column("password", sa.String(length=250), nullable=True),
        sa.Column("refresh_token_jti", sa.String(length=36), nullable=True),
        sa.Column("oauth_providers", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("idx_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("idx_users_sub"), "users", ["uid"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("idx_users_sub"), table_name="users")
    op.drop_index(op.f("idx_users_email"), table_name="users")
    op.drop_table("users")
