from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from extensions import db
from models.leave import Leave
from models.employee import Employee
from models.notification import Notification
from utils.decorators import get_current_user
from utils.helpers import error, parse_date


leave_bp = Blueprint("leave", __name__)


# ============================================================
# LIST LEAVE REQUESTS
# ============================================================

@leave_bp.get("/")
@jwt_required()
def list_leaves():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    query = Leave.query

    employee_id = request.args.get(
        "employee_id",
        type=int
    )

    # --------------------------------------------------------
    # ADMIN / HR
    # --------------------------------------------------------

    if user.role in ("admin", "hr"):

        if employee_id:
            query = query.filter_by(
                employee_id=employee_id
            )

    # --------------------------------------------------------
    # EMPLOYEE
    # --------------------------------------------------------

    else:

        if not user.employee:
            return error(
                "No employee profile is linked to this account",
                400
            )

        if (
            employee_id
            and employee_id != user.employee.id
        ):
            return error(
                "You can only view your own leave requests",
                403
            )

        query = query.filter_by(
            employee_id=user.employee.id
        )

    # --------------------------------------------------------
    # GET RECORDS
    # --------------------------------------------------------

    records = (
        query
        .order_by(
            Leave.created_at.desc()
        )
        .all()
    )

    return jsonify([
        record.to_dict()
        for record in records
    ]), 200


# ============================================================
# CREATE LEAVE REQUEST
# ============================================================

@leave_bp.post("/")
@jwt_required()
def create_leave():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    data = request.get_json(
        silent=True
    ) or {}

    # --------------------------------------------------------
    # DETERMINE EMPLOYEE
    # --------------------------------------------------------

    employee_id = data.get(
        "employee_id"
    )

    # --------------------------------------------------------
    # ADMIN / HR
    # --------------------------------------------------------

    if user.role in ("admin", "hr"):

        if not employee_id:
            return error(
                "Employee ID is required for admin/HR leave requests"
            )

        try:
            employee_id = int(
                employee_id
            )

        except (TypeError, ValueError):
            return error(
                "Invalid employee ID"
            )

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
    # EMPLOYEE
    # --------------------------------------------------------

    else:

        if not user.employee:
            return error(
                "No employee profile is linked to this account",
                400
            )

        employee = user.employee
        employee_id = employee.id

    # --------------------------------------------------------
    # GET FORM DATA
    # --------------------------------------------------------

    leave_type = (
        data.get("leave_type") or ""
    ).strip().lower()

    start_date = data.get(
        "start_date"
    )

    end_date = data.get(
        "end_date"
    )

    reason = (
        data.get("reason") or ""
    ).strip()

    # --------------------------------------------------------
    # VALIDATE LEAVE TYPE
    # --------------------------------------------------------

    allowed_leave_types = {
        "annual",
        "sick",
        "casual",
        "unpaid",
        "maternity",
        "paternity",
    }

    if not leave_type:
        return error(
            "Leave type is required"
        )

    if leave_type not in allowed_leave_types:
        return error(
            "Invalid leave type. Allowed types: "
            "annual, sick, casual, unpaid, maternity, paternity"
        )

    # --------------------------------------------------------
    # VALIDATE DATES
    # --------------------------------------------------------

    if not start_date:
        return error(
            "Start date is required"
        )

    if not end_date:
        return error(
            "End date is required"
        )

    try:

        start_date = parse_date(
            start_date,
            "start_date"
        )

        end_date = parse_date(
            end_date,
            "end_date"
        )

    except ValueError as exc:

        return error(
            str(exc)
        )

    if end_date < start_date:
        return error(
            "End date cannot be before start date"
        )

    # --------------------------------------------------------
    # CREATE LEAVE
    # --------------------------------------------------------

    record = Leave(
        employee_id=employee_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason or None,
        status="pending"
    )

    try:

        db.session.add(record)
        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not create leave request: {str(exc)}",
            500
        )

    return jsonify(
        record.to_dict()
    ), 201


# ============================================================
# APPROVE / REJECT LEAVE REQUEST
# ============================================================

@leave_bp.patch("/<int:leave_id>/status")
@jwt_required()
def update_leave_status(leave_id):

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # --------------------------------------------------------
    # ONLY ADMIN / HR CAN APPROVE OR REJECT
    # --------------------------------------------------------

    if user.role not in ("admin", "hr"):
        return error(
            "You do not have permission to update leave status",
            403
        )

    record = db.session.get(
        Leave,
        leave_id
    )

    if not record:
        return error(
            "Leave request not found",
            404
        )

    data = request.get_json(
        silent=True
    ) or {}

    status = (
        data.get("status") or ""
    ).strip().lower()

    # --------------------------------------------------------
    # VALIDATE STATUS
    # --------------------------------------------------------

    if status not in (
        "approved",
        "rejected"
    ):
        return error(
            "Status must be approved or rejected"
        )

    # --------------------------------------------------------
    # UPDATE STATUS
    # --------------------------------------------------------

    record.status = status

    try:
        if status == "approved":
            notification = Notification(
                employee_id=record.employee_id,
                title="Leave Approved",
                message=f"Your {record.leave_type} leave from "
                        f"{record.start_date} to {record.end_date} "
                        f"has been approved.",
                notification_type="leave_approved",
                is_read=False
            )
            db.session.add(notification)

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not update leave status: {str(exc)}",
            500
        )

    return jsonify(
        record.to_dict()
    ), 200

    leave.status = status
    if status == "approved":
        notification = Notification(
            employee_id=leave.employee_id,
            title="Leave Approved",
            message=(
                f"Your {leave.leave_type} leave "
                f"from {leave.start_date} to {leave.end_date} "
                f"has been approved."
                ),
            notification_type="leave_approved",
            is_read=False
            )

    db.session.add(notification)