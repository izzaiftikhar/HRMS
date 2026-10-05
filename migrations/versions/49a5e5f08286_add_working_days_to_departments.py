"""add working days to departments

Revision ID: 49a5e5f08286
Revises: bf7491117e95
Create Date: 2026-09-09 13:49:23.284954
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "49a5e5f08286"
down_revision = "bf7491117e95"
branch_labels = None
depends_on = None


def upgrade():
    # Add working_days with an empty JSON list for existing departments.
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "working_days",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json")
            )
        )


def downgrade():
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_column("working_days")