"""update payroll for daily payroll and attendance

Revision ID: 5b5e4822a93d
Revises: 7e5400034481
Create Date: 2026-09-04 13:03:06.322358
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b5e4822a93d"
down_revision = "7e5400034481"
branch_labels = None
depends_on = None


def upgrade():
    # Add new payroll fields.
    with op.batch_alter_table("payroll", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "pay_type",
                sa.String(length=20),
                nullable=False,
                server_default="monthly",
            )
        )

        batch_op.add_column(
            sa.Column(
                "daily_salary",
                sa.Numeric(precision=12, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column(
                "working_days",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )

        batch_op.add_column(
            sa.Column(
                "present_days",
                sa.Numeric(precision=6, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column(
                "leave_days",
                sa.Numeric(precision=6, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column(
                "absent_days",
                sa.Numeric(precision=6, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column(
                "payable_days",
                sa.Numeric(precision=6, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column(
                "attendance_deduction",
                sa.Numeric(precision=12, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        # Remove migration-only defaults after existing rows
        # have been safely populated.
        batch_op.alter_column(
            "pay_type",
            server_default=None,
        )

        batch_op.alter_column(
            "daily_salary",
            server_default=None,
        )

        batch_op.alter_column(
            "working_days",
            server_default=None,
        )

        batch_op.alter_column(
            "present_days",
            server_default=None,
        )

        batch_op.alter_column(
            "leave_days",
            server_default=None,
        )

        batch_op.alter_column(
            "absent_days",
            server_default=None,
        )

        batch_op.alter_column(
            "payable_days",
            server_default=None,
        )

        batch_op.alter_column(
            "attendance_deduction",
            server_default=None,
        )


def downgrade():
    with op.batch_alter_table("payroll", schema=None) as batch_op:
        batch_op.drop_column("attendance_deduction")
        batch_op.drop_column("payable_days")
        batch_op.drop_column("absent_days")
        batch_op.drop_column("leave_days")
        batch_op.drop_column("present_days")
        batch_op.drop_column("working_days")
        batch_op.drop_column("daily_salary")
        batch_op.drop_column("pay_type")
