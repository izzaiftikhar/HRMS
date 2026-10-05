from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from extensions import db
from models.notification import Notification
from models.employee import Employee
from utils.decorators import get_current_user
from utils.helpers import error


notification_bp = Blueprint(
    "notification",
    __name__
)


# ============================================================
# GET NOTIFICATIONS
# ============================================================

@notification_bp.get("/")
@jwt_required()
def list_notifications():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # --------------------------------------------------------
    # ADMIN / HR
    # --------------------------------------------------------
    # Keep existing behavior:
    # Admin and HR can view notifications.
    # --------------------------------------------------------

    if user.role in ("admin", "hr"):

        employee_id = request.args.get(
            "employee_id",
            type=int
        )

        query = Notification.query

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

        query = Notification.query.filter(
            db.or_(
                Notification.employee_id == user.employee.id,
                Notification.user_id == user.id
            )
        )

    notifications = (
        query
        .order_by(
            Notification.created_at.desc()
        )
        .all()
    )

    return jsonify(
        [
            notification.to_dict()
            for notification in notifications
        ]
    ), 200


# ============================================================
# CREATE NOTIFICATION
# ============================================================

@notification_bp.post("/")
@jwt_required()
def create_notification():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # Only Admin / HR can manually create notifications
    if user.role not in ("admin", "hr"):
        return error(
            "You do not have permission to create notifications",
            403
        )

    data = request.get_json(
        silent=True
    ) or {}

    employee_id = data.get("employee_id")

    title = (
        data.get("title") or ""
    ).strip()

    message = (
        data.get("message") or ""
    ).strip()

    notification_type = (
        data.get("notification_type") or ""
    ).strip().lower()

    if not employee_id:
        return error(
            "Employee ID is required"
        )

    try:
        employee_id = int(employee_id)

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

    if not title:
        return error(
            "Notification title is required"
        )

    if not message:
        return error(
            "Notification message is required"
        )

    allowed_types = {
        "salary_paid",
        "leave_approved",
        "late_attendance",
        "general",
        "chat_message"
    }

    if notification_type not in allowed_types:
        return error(
            "Invalid notification type. "
            "Allowed types: salary_paid, "
            "leave_approved, late_attendance, "
            "general, chat_message"
        )

    notification = Notification(
        employee_id=employee_id,
        user_id=employee.user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False
    )

    try:

        db.session.add(notification)

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not create notification: {str(exc)}",
            500
        )

    return jsonify(
        notification.to_dict()
    ), 201


# ============================================================
# MARK NOTIFICATION AS READ
# ============================================================

@notification_bp.patch(
    "/<int:notification_id>/read"
)
@jwt_required()
def mark_notification_read(notification_id):

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    notification = db.session.get(
        Notification,
        notification_id
    )

    if not notification:
        return error(
            "Notification not found",
            404
        )

    # --------------------------------------------------------
    # ADMIN / HR
    # --------------------------------------------------------

    if user.role in ("admin", "hr"):

        pass

    # --------------------------------------------------------
    # EMPLOYEE
    # --------------------------------------------------------

    else:

        if not user.employee:
            return error(
                "No employee profile is linked to this account",
                400
            )

        belongs_to_employee = (
            notification.employee_id == user.employee.id
        )

        belongs_to_user = (
            notification.user_id == user.id
        )

        if not (
            belongs_to_employee
            or belongs_to_user
        ):
            return error(
                "You can only update your own notifications",
                403
            )

    notification.is_read = True

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not update notification: {str(exc)}",
            500
        )

    return jsonify(
        notification.to_dict()
    ), 200


# ============================================================
# MARK ALL NOTIFICATIONS AS READ
# ============================================================

@notification_bp.patch(
    "/mark-all-read"
)
@jwt_required()
def mark_all_notifications_read():

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # --------------------------------------------------------
    # ADMIN / HR
    # --------------------------------------------------------

    if user.role in ("admin", "hr"):

        notifications = Notification.query.all()

    # --------------------------------------------------------
    # EMPLOYEE
    # --------------------------------------------------------

    else:

        if not user.employee:
            return error(
                "No employee profile is linked to this account",
                400
            )

        notifications = (
            Notification.query
            .filter(
                db.or_(
                    Notification.employee_id == user.employee.id,
                    Notification.user_id == user.id
                )
            )
            .all()
        )

    for notification in notifications:

        notification.is_read = True

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not mark notifications as read: {str(exc)}",
            500
        )

    return jsonify({
        "message": "All notifications marked as read"
    }), 200


# ============================================================
# DELETE NOTIFICATION
# ============================================================

@notification_bp.delete(
    "/<int:notification_id>"
)
@jwt_required()
def delete_notification(notification_id):

    user = get_current_user()

    if not user:
        return error(
            "User not found",
            401
        )

    # Only Admin can delete notifications
    if user.role != "admin":
        return error(
            "Only admin can delete notifications",
            403
        )

    notification = db.session.get(
        Notification,
        notification_id
    )

    if not notification:
        return error(
            "Notification not found",
            404
        )

    try:

        db.session.delete(notification)

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        return error(
            f"Could not delete notification: {str(exc)}",
            500
        )

    return jsonify({
        "message": "Notification deleted successfully"
    }), 200