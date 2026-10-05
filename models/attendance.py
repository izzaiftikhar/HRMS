from extensions import db


class Attendance(db.Model):
    __tablename__ = "attendance"

    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "work_date",
            name="uq_attendance_employee_date"
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "employees.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    work_date = db.Column(
        db.Date,
        nullable=False
    )

    check_in = db.Column(
        db.Time
    )

    check_out = db.Column(
        db.Time
    )

    # ============================================================
    # ATTENDANCE STATUS
    # ============================================================

    # Keep the existing status field.
    #
    # Possible values:
    # present
    # absent
    # leave
    # half_day
    #
    # IMPORTANT:
    # Late is NOT required to replace Present.
    # Late information is stored separately in is_late.
    status = db.Column(
        db.String(20),
        nullable=False,
        default="present"
    )

    # ============================================================
    # LATE MARKING
    # ============================================================

    # True when the employee checked in after
    # the department's late_after time.
    is_late = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # Number of minutes the employee was late.
    #
    # Example:
    # Department late_after = 09:15
    # Check-in = 09:27
    # late_minutes = 12
    late_minutes = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    # ============================================================
    # RELATIONSHIP
    # ============================================================

    employee = db.relationship(
        "Employee",
        back_populates="attendance_records"
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
                "email": self.employee.email,
            } if self.employee else None,

            "work_date": (
                self.work_date.isoformat()
                if self.work_date
                else None
            ),

            "check_in": (
                self.check_in.isoformat()
                if self.check_in
                else None
            ),

            "check_out": (
                self.check_out.isoformat()
                if self.check_out
                else None
            ),

            "status": self.status,

            "is_late": self.is_late,

            "late_minutes": self.late_minutes,
        }