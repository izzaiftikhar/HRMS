from datetime import time

from flask import Blueprint, jsonify, request

from extensions import db
from models.department import Department
from utils.decorators import roles_required
from utils.helpers import error


department_bp = Blueprint("departments", __name__)


# ============================================================
# CONSTANTS
# ============================================================

VALID_DAYS = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
}


DEFAULT_WORKING_DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]

DEFAULT_START_TIME = time(11, 0)
DEFAULT_END_TIME = time(19, 0)
DEFAULT_LATE_AFTER = time(11, 15)


# ============================================================
# TIME HELPER
# ============================================================

def _parse_time(value, field_name, default=None):
    """
    Convert a time value such as:
        "11:00"
        "11:15"
        "19:00"
        "20:00"

    into a Python time object.
    """

    if value is None or str(value).strip() == "":
        if default is not None:
            return default

        raise ValueError(f"{field_name} is required")

    if isinstance(value, time):
        return value

    value = str(value).strip()

    try:
        # Browser <input type="time"> normally sends HH:MM
        parsed = time.fromisoformat(value)

        return time(
            parsed.hour,
            parsed.minute,
            parsed.second
        )

    except ValueError:
        raise ValueError(
            f"{field_name} must be a valid time in HH:MM format"
        )


# ============================================================
# WORKING DAYS HELPER
# ============================================================

def _normalize_working_days(value):
    """
    Validate and normalize department working days.
    """

    if value is None:
        value = DEFAULT_WORKING_DAYS.copy()

    if not isinstance(value, list):
        raise ValueError("working_days must be a list")

    normalized_days = []

    for day in value:
        cleaned_day = str(day).strip().lower()

        if cleaned_day not in VALID_DAYS:
            raise ValueError(f"Invalid working day: {day}")

        normalized_days.append(
            VALID_DAYS[cleaned_day]
        )

    # Remove duplicates while preserving order
    normalized_days = list(dict.fromkeys(normalized_days))

    if not normalized_days:
        raise ValueError(
            "At least one working day is required"
        )

    return normalized_days


# ============================================================
# DEPARTMENT TIMING VALIDATION
# ============================================================

def _validate_department_times(
    start_time,
    end_time,
    late_after
):
    """
    Make sure department timing is logically valid.

    Rules:
    - start_time must be before end_time
    - late_after cannot be before start_time
    - late_after cannot be after end_time
    """

    if start_time >= end_time:
        raise ValueError(
            "start_time must be earlier than end_time"
        )

    if late_after < start_time:
        raise ValueError(
            "late_after cannot be earlier than start_time"
        )

    if late_after > end_time:
        raise ValueError(
            "late_after cannot be later than end_time"
        )


# ============================================================
# GET ALL DEPARTMENTS
# ============================================================

@department_bp.get("/")
@roles_required("admin", "hr", "employee")
def list_departments():

    departments = Department.query.order_by(
        Department.name
    ).all()

    return jsonify([
        department.to_dict()
        for department in departments
    ])


# ============================================================
# GET SINGLE DEPARTMENT
# ============================================================

@department_bp.get("/<int:department_id>")
@roles_required("admin", "hr", "employee")
def get_department(department_id):

    department = db.session.get(
        Department,
        department_id
    )

    if not department:
        return error(
            "Department not found",
            404
        )

    return jsonify(
        department.to_dict()
    )


# ============================================================
# CREATE DEPARTMENT
# ============================================================

@department_bp.post("/")
@roles_required("admin", "hr")
def create_department():

    data = request.get_json(
        silent=True
    ) or {}

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    name = (
        data.get("name") or ""
    ).strip()

    if not name:
        return error(
            "name is required"
        )

    existing = Department.query.filter_by(
        name=name
    ).first()

    if existing:
        return error(
            "Department name already exists",
            409
        )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = data.get(
        "description"
    )

    # --------------------------------------------------------
    # WORKING DAYS
    # --------------------------------------------------------

    try:
        working_days = _normalize_working_days(
            data.get("working_days")
        )
    except ValueError as exc:
        return error(
            str(exc)
        )

    # --------------------------------------------------------
    # WORKING TIMES
    # --------------------------------------------------------

    try:
        start_time = _parse_time(
            data.get("start_time"),
            "start_time",
            DEFAULT_START_TIME
        )

        end_time = _parse_time(
            data.get("end_time"),
            "end_time",
            DEFAULT_END_TIME
        )

        late_after = _parse_time(
            data.get("late_after"),
            "late_after",
            DEFAULT_LATE_AFTER
        )

        _validate_department_times(
            start_time,
            end_time,
            late_after
        )

    except ValueError as exc:
        return error(
            str(exc)
        )

    # --------------------------------------------------------
    # CREATE DEPARTMENT
    # --------------------------------------------------------

    department = Department(
        name=name,
        description=description,
        working_days=working_days,
        start_time=start_time,
        end_time=end_time,
        late_after=late_after,
    )

    try:
        db.session.add(department)
        db.session.commit()

    except Exception as exc:
        db.session.rollback()

        return error(
            f"Could not create department: {str(exc)}",
            500
        )

    return jsonify(
        department.to_dict()
    ), 201


# ============================================================
# UPDATE DEPARTMENT
# ============================================================

@department_bp.put("/<int:department_id>")
@roles_required("admin", "hr")
def update_department(department_id):

    department = db.session.get(
        Department,
        department_id
    )

    if not department:
        return error(
            "Department not found",
            404
        )

    data = request.get_json(
        silent=True
    ) or {}

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if "name" in data:

        name = (
            data.get("name") or ""
        ).strip()

        if not name:
            return error(
                "name cannot be empty"
            )

        existing = Department.query.filter(
            Department.name == name,
            Department.id != department_id
        ).first()

        if existing:
            return error(
                "Department name already exists",
                409
            )

        department.name = name

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    if "description" in data:
        department.description = data.get(
            "description"
        )

    # --------------------------------------------------------
    # WORKING DAYS
    # --------------------------------------------------------

    if "working_days" in data:

        try:
            department.working_days = (
                _normalize_working_days(
                    data.get("working_days")
                )
            )

        except ValueError as exc:
            return error(
                str(exc)
            )

    # --------------------------------------------------------
    # START TIME
    # --------------------------------------------------------

    if "start_time" in data:

        try:
            department.start_time = _parse_time(
                data.get("start_time"),
                "start_time"
            )

        except ValueError as exc:
            return error(
                str(exc)
            )

    # --------------------------------------------------------
    # END TIME
    # --------------------------------------------------------

    if "end_time" in data:

        try:
            department.end_time = _parse_time(
                data.get("end_time"),
                "end_time"
            )

        except ValueError as exc:
            return error(
                str(exc)
            )

    # --------------------------------------------------------
    # LATE AFTER
    # --------------------------------------------------------

    if "late_after" in data:

        try:
            department.late_after = _parse_time(
                data.get("late_after"),
                "late_after"
            )

        except ValueError as exc:
            return error(
                str(exc)
            )

    # --------------------------------------------------------
    # VALIDATE FINAL TIMING
    # --------------------------------------------------------

    try:
        _validate_department_times(
            department.start_time,
            department.end_time,
            department.late_after
        )

    except ValueError as exc:
        return error(
            str(exc)
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:
        db.session.commit()

    except Exception as exc:
        db.session.rollback()

        return error(
            f"Could not update department: {str(exc)}",
            500
        )

    return jsonify(
        department.to_dict()
    )


# ============================================================
# DELETE DEPARTMENT
# ============================================================

@department_bp.delete("/<int:department_id>")
@roles_required("admin", "hr")
def delete_department(department_id):

    department = db.session.get(
        Department,
        department_id
    )

    if not department:
        return error(
            "Department not found",
            404
        )

    # Do not allow deletion while employees
    # are still assigned to this department.
    if department.employees:
        return error(
            "Cannot delete a department that still has employees",
            409
        )

    try:
        db.session.delete(department)
        db.session.commit()

    except Exception as exc:
        db.session.rollback()

        return error(
            f"Could not delete department: {str(exc)}",
            500
        )

    return jsonify({
        "message": "Department deleted"
    })