"""add department timing and late payroll fields

Revision ID: 1eaac3de9a89
Revises: 
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1eaac3de9a89"
down_revision = "4bc3bde0e260"
branch_labels = None
depends_on = None


def upgrade():

    # ============================================================
    # DEPARTMENTS
    # ============================================================

    with op.batch_alter_table("departments", schema=None) as batch_op:

        batch_op.add_column(
            sa.Column(
                "start_time",
                sa.Time(),
                nullable=False,
                server_default=sa.text("'11:00:00'")
            )
        )

        batch_op.add_column(
            sa.Column(
                "end_time",
                sa.Time(),
                nullable=False,
                server_default=sa.text("'19:00:00'")
            )
        )

        batch_op.add_column(
            sa.Column(
                "late_after",
                sa.Time(),
                nullable=False,
                server_default=sa.text("'11:15:00'")
            )
        )


    # ============================================================
    # ATTENDANCE
    # ============================================================

    with op.batch_alter_table("attendance", schema=None) as batch_op:

        batch_op.add_column(
            sa.Column(
                "is_late",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false")
            )
        )

        batch_op.add_column(
            sa.Column(
                "late_minutes",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0")
            )
        )


    # ============================================================
    # PAYROLL
    # ============================================================

    with op.batch_alter_table("payroll", schema=None) as batch_op:

        batch_op.add_column(
            sa.Column(
                "late_days",
                sa.Numeric(5, 2),
                nullable=False,
                server_default=sa.text("0")
            )
        )


def downgrade():

    # ============================================================
    # PAYROLL
    # ============================================================

    with op.batch_alter_table("payroll", schema=None) as batch_op:
        batch_op.drop_column("late_days")


    # ============================================================
    # ATTENDANCE
    # ============================================================

    with op.batch_alter_table("attendance", schema=None) as batch_op:
        batch_op.drop_column("late_minutes")
        batch_op.drop_column("is_late")


    # ============================================================
    # DEPARTMENTS
    # ============================================================

    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_column("late_after")
        batch_op.drop_column("end_time")
        batch_op.drop_column("start_time")

