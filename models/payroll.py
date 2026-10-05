from datetime import datetime

from extensions import db


class Payroll(db.Model):
    __tablename__ = "payroll"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False
    )

    # ============================================================
    # PAYROLL PERIOD
    # ============================================================

    month = db.Column(
        db.Integer,
        nullable=False
    )

    year = db.Column(
        db.Integer,
        nullable=False
    )

    pay_type = db.Column(
        db.String(20),
        nullable=False,
        default="monthly"
    )

    # ============================================================
    # SALARY
    # ============================================================

    basic_salary = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    daily_salary = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    allowances = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    deductions = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    attendance_deduction = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    net_salary = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    # ============================================================
    # ATTENDANCE / PAYABLE DAYS
    # ============================================================

    working_days = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    present_days = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=0
    )

    leave_days = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=0
    )

    absent_days = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=0
    )

    payable_days = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=0
    )

    # ============================================================
    # LATE MARKINGS
    # ============================================================

    # Number of late attendance days in this payroll period.
    #
    # Late days are still included in present_days.
    late_days = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=0
    )

    # ============================================================
    # PAYMENT
    # ============================================================

    payment_method = db.Column(
        db.String(20),
        nullable=False,
        default="bank"
    )

    payment_status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    # ============================================================
    # TIMESTAMPS
    # ============================================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # ============================================================
    # RELATIONSHIP
    # ============================================================

    employee = db.relationship(
        "Employee",
        back_populates="payroll_records"
    )

    # ============================================================
    # UNIQUE PAYROLL PERIOD
    # ============================================================

    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "month",
            "year",
            name="uq_employee_payroll_period"
        ),
    )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self):
        return {
            "id": self.id,

            "employee_id": self.employee_id,

            "employee": {
                "id": self.employee.id,
                "first_name": self.employee.first_name,
                "last_name": self.employee.last_name,
            } if self.employee else None,

            "month": self.month,
            "year": self.year,

            "pay_type": self.pay_type,

            "basic_salary": float(
                self.basic_salary or 0
            ),

            "daily_salary": float(
                self.daily_salary or 0
            ),

            "working_days": self.working_days,

            "present_days": float(
                self.present_days or 0
            ),

            "leave_days": float(
                self.leave_days or 0
            ),

            "absent_days": float(
                self.absent_days or 0
            ),

            "payable_days": float(
                self.payable_days or 0
            ),

            "late_days": float(
                self.late_days or 0
            ),

            "attendance_deduction": float(
                self.attendance_deduction or 0
            ),

            "allowances": float(
                self.allowances or 0
            ),

            "deductions": float(
                self.deductions or 0
            ),

            "net_salary": float(
                self.net_salary or 0
            ),

            "payment_method": self.payment_method,

            "payment_status": self.payment_status,

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),

            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }