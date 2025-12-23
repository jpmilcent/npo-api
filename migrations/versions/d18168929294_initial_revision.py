"""Initial revision

Revision ID: d18168929294
Revises:
Create Date: 2025-12-23 10:19:11.769829

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d18168929294"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(length=250), nullable=False),
        sa.Column("mime", sa.String(length=50), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("hash", sa.String(length=32), nullable=False),
        sa.Column("hash_dir", sa.String(length=16), nullable=False),
        sa.Column("hash_file", sa.String(length=20), nullable=False),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
        sa.UniqueConstraint("hash"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("files")
