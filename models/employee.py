from datetime import datetime, timezone

from extensions import db


# ============================================================
# ASSOCIATION TABLE
# EMPLOYEES <-> DEPARTMENTS
# ============================================================

employee_departments = db.Table(
    "employee_departments",

    db.Column(
        "employee_id",
        db.Integer,
        db.ForeignKey(
            "employees.id",
            ondelete="CASCADE"
        ),
        primary_key=True
    ),

    db.Column(
        "department_id",
        db.Integer,
        db.ForeignKey(
            "departments.id",
            ondelete="CASCADE"
        ),
        primary_key=True
    )
)


class Employee(db.Model):
    __tablename__ = "employees"

    # ============================================================
    # BASIC INFORMATION
    # ============================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=True
    )

    first_name = db.Column(
        db.String(80),
        nullable=False
    )

    last_name = db.Column(
        db.String(80),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(30)
    )

    job_title = db.Column(
        db.String(100)
    )

    # ============================================================
    # SALARY INFORMATION
    # ============================================================

    basic_salary = db.Column(
        db.Numeric(12, 2),
        nullable=True
    )

    account_number = db.Column(
        db.String(50),
        nullable=True
    )

    # ============================================================
    # EMPLOYMENT INFORMATION
    # ============================================================

    hire_date = db.Column(
        db.Date
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # ============================================================
    # USER RELATIONSHIP
    # ============================================================

    user = db.relationship(
        "User",
        back_populates="employee"
    )

    # ============================================================
    # DEPARTMENT RELATIONSHIP
    # ============================================================

    departments = db.relationship(
        "Department",
        secondary=employee_departments,
        back_populates="employees"
    )

    # ============================================================
    # ATTENDANCE
    # ============================================================

    attendance_records = db.relationship(
        "Attendance",
        back_populates="employee",
        cascade="all, delete-orphan"
    )

    # ============================================================
    # LEAVE
    # ============================================================

    leave_requests = db.relationship(
        "Leave",
        back_populates="employee",
        cascade="all, delete-orphan"
    )

    # ============================================================
    # PAYROLL
    # ============================================================

    payroll_records = db.relationship(
        "Payroll",
        back_populates="employee",
        cascade="all, delete-orphan"
    )

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    notifications = db.relationship(
        "Notification",
        back_populates="employee",
        cascade="all, delete-orphan"
    )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self):
        return {
            "id": self.id,

            "user_id": self.user_id,

            # ----------------------------------------------------
            # DEPARTMENTS
            # ----------------------------------------------------

            "departments": [
                {
                    "id": department.id,
                    "name": department.name,

                    "working_days": (
                        department.working_days or []
                    ),

                    "start_time": (
                        department.start_time.isoformat()
                        if department.start_time
                        else None
                    ),

                    "end_time": (
                        department.end_time.isoformat()
                        if department.end_time
                        else None
                    ),

                    "late_after": (
                        department.late_after.isoformat()
                        if department.late_after
                        else None
                    ),
                }

                for department in self.departments
            ],

            # ----------------------------------------------------
            # EMPLOYEE INFORMATION
            # ----------------------------------------------------

            "first_name": self.first_name,

            "last_name": self.last_name,

            "email": self.email,

            "phone": self.phone,

            "job_title": self.job_title,

            # ----------------------------------------------------
            # SALARY
            # ----------------------------------------------------

            "basic_salary": (
                float(self.basic_salary)
                if self.basic_salary is not None
                else None
            ),

            "account_number": self.account_number,

            # ----------------------------------------------------
            # EMPLOYMENT
            # ----------------------------------------------------

            "hire_date": (
                self.hire_date.isoformat()
                if self.hire_date
                else None
            ),

            "status": self.status,

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }