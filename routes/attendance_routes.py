from datetime import datetime, time
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from extensions import db
from models.attendance import Attendance
from models.employee import Employee
from models.notification import Notification
from utils.decorators import get_current_user, roles_required
from utils.helpers import error, parse_date, parse_time


attendance_bp = Blueprint("attendance", __name__)


# ============================================================
# PAKISTAN TIMEZONE
# ============================================================

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


# ============================================================
# DEFAULT DEPARTMENT TIMING
# ============================================================
#
# These are only fallbacks.
#
# Actual timing comes from the employee's department.
#
# Example:
# Department:
#   Start      = 09:00
#   End        = 17:00
#   Late After = 09:15
#
# Employee checking in at 09:16:
#   status     = present
#   is_late    = True
#   late_minutes = 1
#
# ============================================================

DEFAULT_START_TIME = time(11, 0)
DEFAULT_END_TIME = time(19, 0)
DEFAULT_LATE_AFTER = time(11, 15)


# ============================================================
# ALLOWED ATTENDANCE STATUSES
# ============================================================
#
# IMPORTANT:
# "late" is kept here for backward compatibility with
# existing attendance records.
#
# New late attendance will be stored as:
#
# status = "present"
# is_late = True
#
# ============================================================

ALLOWED_ATTENDANCE_STATUSES = {
    "present",
    "absent",
    "leave",
    "half_day",
    "late",
}


# ============================================================
# GET CURRENT PAKISTAN DATE/TIME
# ============================================================

def pakistan_now():
    return datetime.now(PAKISTAN_TZ)


# ============================================================
# GET EMPLOYEE'S PRIMARY DEPARTMENT
# ============================================================
#
# Your Employee model currently allows multiple departments.
#
# To avoid breaking your existing structure, we use the first
# department as the employee's primary department for attendance
# timing.
#
# Payroll already follows the same approach for working days.
#
# ============================================================

def _get_employee_department(employee):
    if not employee:
        return None

    if not employee.departments:
        return None

    return employee.departments[0]


# ============================================================
# GET DEPARTMENT TIMING
# ============================================================

def _get_department_timing(employee):
    """
    Get the employee's department timing.

    Returns:
        start_time
        end_time
        late_after
    """

    department = _get_employee_department(employee)

    if not department:
        return (
            DEFAULT_START_TIME,
            DEFAULT_END_TIME,
            DEFAULT_LATE_AFTER,
        )

    start_time = (
        department.start_time
        if department.start_time
        else DEFAULT_START_TIME
    )

    end_time = (
        department.end_time
        if department.end_time
        else DEFAULT_END_TIME
    )

    late_after = (
        department.late_after
        if department.late_after
        else DEFAULT_LATE_AFTER
    )

    return (
        start_time,
        end_time,
        late_after,
    )


# ============================================================
# CALCULATE LATE MINUTES
# ============================================================

def _calculate_late_minutes(check_in_time, late_after):
    """
    Calculate how many minutes late an employee is.

    Example:

        late_after = 09:15
        check_in   = 09:27

        result = 12 minutes
    """

    if not check_in_time or not late_after:
        return 0

    check_in_minutes = (
        check_in_time.hour * 60
        + check_in_time.minute
    )

    late_after_minutes = (
        late_after.hour * 60
        + late_after.minute
    )

    difference = (
        check_in_minutes
        - late_after_minutes
    )

    return max(difference, 0)


# ============================================================
# CHECK WHETHER EMPLOYEE IS LATE
# ============================================================

def is_late(check_in_time, late_after):
    """
    Employee is late only when checking in after the
    department's late_after time.
    """

    if not check_in_time or not late_after:
        return False

    return check_in_time > late_after


# ============================================================
# DECIDE WHICH EMPLOYEE'S ATTENDANCE CAN BE ACCESSED
# ============================================================

def _target_employee_id(user):

    requested = request.args.get(
        "employee_id",
        type=int
    )

    # --------------------------------------------------------
    # Admin and HR can view any employee
    # --------------------------------------------------------

    if user.role in ("admin", "hr"):
        return requested

    # --------------------------------------------------------
    # Normal employee must have an employee profile
    # --------------------------------------------------------

    if not user.employee:
        return None

    # --------------------------------------------------------
    # Employee cannot view another employee's attendance
    # --------------------------------------------------------

    if requested and requested != user.employee.id:
        return "forbidden"

    return user.employee.id


# ============================================================
# VIEW ATTENDANCE RECORDS
# ============================================================

@attendance_bp.get("/")
@jwt_required()
def list_attendance():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    employee_id = _target_employee_id(user)

    if employee_id == "forbidden":
        return error(
            "You can only view your own attendance",
            403
        )

    query = Attendance.query

    if employee_id:
        query = query.filter_by(
            employee_id=employee_id
        )

    elif user.role not in ("admin", "hr"):
        return error(
            "No employee profile is linked to this account",
            400
        )

    records = (
        query
        .order_by(
            Attendance.work_date.desc(),
            Attendance.check_in.desc()
        )
        .all()
    )

    return jsonify([
        record.to_dict()
        for record in records
    ])


# ============================================================
# EMPLOYEE CHECK-IN
# ============================================================

@attendance_bp.post("/check-in")
@jwt_required()
def check_in():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # --------------------------------------------------------
    # Only employees can use self check-in
    # --------------------------------------------------------

    if user.role != "employee":
        return error(
            "Only employees can check themselves in",
            403
        )

    employee = user.employee

    if not employee:
        return error(
            "Employee profile not found",
            404
        )

    # --------------------------------------------------------
    # Get current Pakistan date/time
    # --------------------------------------------------------

    now = pakistan_now()

    today = now.date()

    current_time = now.time().replace(
        microsecond=0
    )

    # --------------------------------------------------------
    # Get department timing
    # --------------------------------------------------------

    (
        start_time,
        end_time,
        late_after
    ) = _get_department_timing(employee)

    # --------------------------------------------------------
    # Check if attendance already exists today
    # --------------------------------------------------------

    existing = Attendance.query.filter_by(
        employee_id=employee.id,
        work_date=today
    ).first()

    if existing and existing.check_in:
        return error(
            "Already checked in today",
            409
        )

    # --------------------------------------------------------
    # Determine late status
    # --------------------------------------------------------

    late = is_late(
        current_time,
        late_after
    )

    late_minutes = (
        _calculate_late_minutes(
            current_time,
            late_after
        )
        if late
        else 0
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Late is STILL PRESENT.
    #
    # We do NOT set:
    #
    # status = "late"
    #
    # Instead:
    #
    # status = "present"
    # is_late = True
    #
    # --------------------------------------------------------

    attendance_status = "present"

    # --------------------------------------------------------
    # Update existing attendance record
    # --------------------------------------------------------

    if existing:

        existing.check_in = current_time

        existing.status = attendance_status

        existing.is_late = late

        existing.late_minutes = late_minutes

        record = existing

    # --------------------------------------------------------
    # Create new attendance record
    # --------------------------------------------------------

    else:

        record = Attendance(
            employee_id=employee.id,
            work_date=today,
            check_in=current_time,
            status=attendance_status,
            is_late=late,
            late_minutes=late_minutes
        )

        db.session.add(record)

    # --------------------------------------------------------
    # Late notification
    # --------------------------------------------------------

    if late:

        notification = Notification(
            employee_id=employee.id,
            title="Late Attendance",
            message=(
                f"You checked in at "
                f"{current_time.strftime('%I:%M %p')}. "
                f"You are {late_minutes} minute(s) late."
            ),
            notification_type="late_attendance",
            is_read=False
        )

        db.session.add(notification)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not check in: {str(exc)}",
            500
        )

    return jsonify(
        record.to_dict()
    ), 201


# ============================================================
# EMPLOYEE CHECK-OUT
# ============================================================

@attendance_bp.post("/check-out")
@jwt_required()
def check_out():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # --------------------------------------------------------
    # Only employees can use self check-out
    # --------------------------------------------------------

    if user.role != "employee":
        return error(
            "Only employees can check themselves out",
            403
        )

    employee = user.employee

    if not employee:
        return error(
            "Employee profile not found",
            404
        )

    # --------------------------------------------------------
    # Current Pakistan time
    # --------------------------------------------------------

    now = pakistan_now()

    today = now.date()

    current_time = now.time().replace(
        microsecond=0
    )

    # --------------------------------------------------------
    # Find today's attendance
    # --------------------------------------------------------

    record = Attendance.query.filter_by(
        employee_id=employee.id,
        work_date=today
    ).first()

    if not record or not record.check_in:
        return error(
            "Check in before checking out",
            400
        )

    if record.check_out:
        return error(
            "Already checked out today",
            409
        )

    # --------------------------------------------------------
    # Save checkout
    # --------------------------------------------------------

    record.check_out = current_time

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not check out: {str(exc)}",
            500
        )

    return jsonify(
        record.to_dict()
    )


# ============================================================
# ADMIN / HR MANUALLY CREATE ATTENDANCE
# ============================================================

@attendance_bp.post("/")
@roles_required("admin", "hr")
def create_attendance():

    data = request.get_json(
        silent=True
    ) or {}

    employee_id = data.get("employee_id")

    if not employee_id:
        return error(
            "employee_id is required"
        )

    # --------------------------------------------------------
    # Validate employee ID
    # --------------------------------------------------------

    try:

        employee_id = int(employee_id)

    except (TypeError, ValueError):

        return error(
            "employee_id must be a valid number"
        )

    # --------------------------------------------------------
    # Get employee
    # --------------------------------------------------------

    employee = db.session.get(
        Employee,
        employee_id
    )

    if not employee:

        return error(
            "Employee not found",
            404
        )

    # --------------------------------------------------------
    # Parse date/time
    # --------------------------------------------------------

    try:

        work_date = (
            parse_date(
                data.get("work_date"),
                "work_date"
            )
            or pakistan_now().date()
        )

        check_in_time = parse_time(
            data.get("check_in"),
            "check_in"
        )

        check_out_time = parse_time(
            data.get("check_out"),
            "check_out"
        )

    except ValueError as exc:

        return error(
            str(exc)
        )

    # --------------------------------------------------------
    # Validate status
    # --------------------------------------------------------

    status = (
        data.get("status")
        or "present"
    ).strip().lower()

    if status not in ALLOWED_ATTENDANCE_STATUSES:

        return error(
            "Invalid attendance status. "
            "Allowed statuses: "
            "present, absent, leave, half_day, late"
        )

    # --------------------------------------------------------
    # Prevent duplicate attendance
    # --------------------------------------------------------

    existing = Attendance.query.filter_by(
        employee_id=employee_id,
        work_date=work_date
    ).first()

    if existing:

        return error(
            "Attendance already exists for this employee and date",
            409
        )

    # --------------------------------------------------------
    # Get department timing
    # --------------------------------------------------------

    (
        start_time,
        end_time,
        late_after
    ) = _get_department_timing(employee)

    # --------------------------------------------------------
    # Determine late status
    # --------------------------------------------------------
    #
    # If check-in exists, the system automatically decides
    # whether the employee is late based on the department's
    # late_after time.
    #
    # Late employee remains PRESENT.
    #
    # --------------------------------------------------------

    late = False
    late_minutes = 0

    if check_in_time:

        late = is_late(
            check_in_time,
            late_after
        )

        if late:

            late_minutes = _calculate_late_minutes(
                check_in_time,
                late_after
            )

        # ----------------------------------------------------
        # If admin selected "late", normalize it to:
        #
        # status = present
        # is_late = true
        #
        # ----------------------------------------------------

        if status == "late":

            late = True

            late_minutes = _calculate_late_minutes(
                check_in_time,
                late_after
            )

        status = "present"

    # --------------------------------------------------------
    # If no check-in and admin explicitly selected late
    # --------------------------------------------------------
    #
    # We don't have a time from which to calculate minutes.
    # Still allow the manual late marking.
    #
    # --------------------------------------------------------

    elif status == "late":

        late = True
        late_minutes = 0
        status = "present"

    # --------------------------------------------------------
    # Absent / leave cannot have check-in/out
    # --------------------------------------------------------

    if status in ("absent", "leave"):

        check_in_time = None
        check_out_time = None

        late = False
        late_minutes = 0

    # --------------------------------------------------------
    # Half day without check-in is allowed.
    #
    # If a half-day has a check-in, we can still determine
    # whether that check-in was late.
    # --------------------------------------------------------

    if status == "half_day" and check_in_time:

        late = is_late(
            check_in_time,
            late_after
        )

        if late:

            late_minutes = _calculate_late_minutes(
                check_in_time,
                late_after
            )

    # --------------------------------------------------------
    # Validate check-in/check-out consistency
    # --------------------------------------------------------

    if (
        check_in_time
        and check_out_time
        and check_out_time <= check_in_time
    ):

        return error(
            "Check-out time must be after check-in time"
        )

    # --------------------------------------------------------
    # Create attendance record
    # --------------------------------------------------------

    record = Attendance(
        employee_id=employee_id,
        work_date=work_date,
        check_in=check_in_time,
        check_out=check_out_time,
        status=status,
        is_late=late,
        late_minutes=late_minutes
    )

    db.session.add(record)

    # --------------------------------------------------------
    # Late notification
    # --------------------------------------------------------

    if late:

        if late_minutes > 0:

            message = (
                f"Your attendance for {work_date} "
                f"has been marked as late by "
                f"{late_minutes} minute(s)."
            )

        else:

            message = (
                f"Your attendance for {work_date} "
                f"has been marked as late."
            )

        notification = Notification(
            employee_id=employee.id,
            title="Late Attendance",
            message=message,
            notification_type="late_attendance",
            is_read=False
        )

        db.session.add(notification)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not create attendance: {str(exc)}",
            500
        )

    return jsonify(
        record.to_dict()
    ), 201