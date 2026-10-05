from datetime import time

from extensions import db
from models.employee import employee_departments


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    # ============================================================
    # WORKING DAYS
    # ============================================================

    working_days = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday"
        ]
    )

    # ============================================================
    # WORKING TIMING
    # ============================================================

    # Department normal starting time
    start_time = db.Column(
        db.Time,
        nullable=False,
        default=time(11, 0)
    )

    # Department normal ending time
    end_time = db.Column(
        db.Time,
        nullable=False,
        default=time(19, 0)
    )

    # Time after which employee is considered late
    #
    # Example:
    # start_time = 11:00
    # late_after = 11:15
    #
    # Employee checking in at:
    # 10:55 -> Present
    # 11:10 -> Present
    # 11:16 -> Present + Late
    late_after = db.Column(
        db.Time,
        nullable=False,
        default=time(11, 15)
    )

    # ============================================================
    # EMPLOYEES
    # ============================================================

    employees = db.relationship(
        "Employee",
        secondary=employee_departments,
        back_populates="departments"
    )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,

            "working_days": self.working_days or [],

            "start_time": (
                self.start_time.isoformat()
                if self.start_time
                else None
            ),

            "end_time": (
                self.end_time.isoformat()
                if self.end_time
                else None
            ),

            "late_after": (
                self.late_after.isoformat()
                if self.late_after
                else None
            ),

            "employee_count": len(self.employees),

            "employees": [
                {
                    "id": employee.id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "email": employee.email
                }
                for employee in self.employees
            ]
        }