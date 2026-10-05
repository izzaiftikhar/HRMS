from calendar import monthrange
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import or_

from extensions import db
from models.employee import Employee
from models.notification import Notification
from models.payroll import Payroll
from models.attendance import Attendance
from models.leave import Leave
from utils.decorators import get_current_user, roles_required
from utils.helpers import error


payroll_bp = Blueprint("payroll", __name__)


# ============================================================
# CONSTANTS
# ============================================================

PAID_LEAVE_TYPES = {
    "annual",
    "sick",
    "maternity",
    "paternity",
}

CASUAL_LEAVE_TYPES = {
    "casual",
}

UNPAID_LEAVE_TYPES = {
    "unpaid",
}

ALLOWED_PAYMENT_METHODS = {
    "cash",
    "bank",
}

ALLOWED_PAYMENT_STATUSES = {
    "pending",
    "paid",
}

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


# Payroll penalties
LATE_DEDUCTION = Decimal("1000")
ABSENT_DEDUCTION = Decimal("1500")
HALF_DAY_DEDUCTION = Decimal("750")
CASUAL_LEAVE_DEDUCTION = Decimal("1500")
UNPAID_LEAVE_DEDUCTION = Decimal("1500")


DEFAULT_WORKING_DAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
}

VALID_WEEKDAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}


# ============================================================
# DATE HELPERS
# ============================================================

def pakistan_today():
    return datetime.now(PAKISTAN_TZ).date()


def _normalize_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    return None


def _normalize_text(value):
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _normalize_leave_type(value):
    value = _normalize_text(value)

    aliases = {
        "annual_leave": "annual",
        "sick_leave": "sick",
        "maternity_leave": "maternity",
        "paternity_leave": "paternity",
        "casual_leave": "casual",
        "unpaid_leave": "unpaid",
    }

    return aliases.get(value, value)


# ============================================================
# DECIMAL HELPERS
# ============================================================

def _to_decimal(value, field_name, default=None):
    if value is None:
        if default is not None:
            return Decimal(default)

        raise ValueError(f"{field_name} is required")

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(
            f"{field_name} must be a valid number"
        )


# ============================================================
# MONTH HELPERS
# ============================================================

def _days_in_month(month, year):
    return monthrange(year, month)[1]


def _get_period_dates(month, year):
    start_date = date(year, month, 1)
    end_date = date(
        year,
        month,
        _days_in_month(month, year)
    )

    return start_date, end_date


def _is_pre_hire_period(employee, month, year):
    if not employee or not employee.hire_date:
        return False

    _, period_end = _get_period_dates(month, year)

    return employee.hire_date > period_end


# ============================================================
# DEPARTMENT WORKING DAYS
# ============================================================

WEEKDAY_ALIASES = {
    "monday": "Monday",
    "mon": "Monday",

    "tuesday": "Tuesday",
    "tue": "Tuesday",
    "tues": "Tuesday",

    "wednesday": "Wednesday",
    "wed": "Wednesday",

    "thursday": "Thursday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",

    "friday": "Friday",
    "fri": "Friday",

    "saturday": "Saturday",
    "sat": "Saturday",

    "sunday": "Sunday",
    "sun": "Sunday",
}


def _normalize_weekday(value):
    """
    Normalize department working-day values.

    Examples:
        Monday -> Monday
        monday -> Monday
        MONDAY -> Monday
        Mon -> Monday
        mon -> Monday
    """
    if value is None:
        return None

    text = str(value).strip().lower()

    return WEEKDAY_ALIASES.get(text)


def _get_employee_working_day_names(employee):
    """
    Get working days from the employee's first department.

    Working-day values are normalized so configurations such as:

        ["Monday", "Tuesday", "Wednesday"]

    and:

        ["monday", "tuesday", "wednesday"]

    and:

        ["Mon", "Tue", "Wed"]

    all work correctly.

    If no department or invalid configuration exists,
    Monday-Friday is used.
    """

    if not employee:
        return DEFAULT_WORKING_DAYS.copy()

    if not employee.departments:
        return DEFAULT_WORKING_DAYS.copy()

    department = employee.departments[0]

    configured_days = department.working_days

    if not configured_days:
        return DEFAULT_WORKING_DAYS.copy()

    valid_days = set()

    for day in configured_days:
        normalized_day = _normalize_weekday(day)

        if normalized_day:
            valid_days.add(normalized_day)

    if not valid_days:
        return DEFAULT_WORKING_DAYS.copy()

    return valid_days


def _get_working_dates(month, year, employee):
    """
    Return all dates in the month that are working days
    according to the employee's department.
    """

    working_day_names = _get_employee_working_day_names(employee)

    start_date, end_date = _get_period_dates(
        month,
        year
    )

    dates = []

    current_date = start_date

    while current_date <= end_date:
        if current_date.strftime("%A") in working_day_names:
            dates.append(current_date)

        current_date += timedelta(days=1)

    return dates


# ============================================================
# NOTIFICATIONS
# ============================================================

def _create_payroll_notification(
    employee_id,
    month,
    year,
    notification_type
):
    if notification_type == "salary_paid":
        title = "Salary Paid"
        message = (
            f"Your salary for {month}/{year} has been marked as paid."
        )

    elif notification_type == "salary_pending":
        title = "Salary Pending"
        message = (
            f"Your salary for {month}/{year} is currently pending."
        )

    else:
        return

    notification = Notification(
        employee_id=employee_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
    )

    db.session.add(notification)


# ============================================================
# ATTENDANCE CALCULATION
# ============================================================

def _calculate_attendance(employee_id, month, year):
    employee = Employee.query.get(employee_id)

    zero = Decimal("0")

    empty_result = {
        "working_days": 0,
        "completed_working_days": 0,
        "present_days": zero,
        "leave_days": zero,
        "absent_days": zero,
        "payable_days": zero,
        "paid_leave_days": zero,
        "casual_leave_days": zero,
        "unpaid_leave_days": zero,
        "late_days": zero,
        "half_day_days": zero,
        "deduction_days": zero,
    }

    if not employee:
        return empty_result

    # ========================================================
    # PRE-HIRE PERIOD
    # ========================================================

    if _is_pre_hire_period(employee, month, year):
        return empty_result

    # ========================================================
    # PERIOD
    # ========================================================

    period_start, period_end = _get_period_dates(
        month,
        year
    )

    today = pakistan_today()

    # ========================================================
    # WORKING DAYS
    # ========================================================

    working_dates = _get_working_dates(
        month,
        year,
        employee
    )

    total_working_days = len(working_dates)

    # ========================================================
    # DO NOT COUNT FUTURE DAYS
    # ========================================================

    if period_start > today:
        completed_end_date = period_start - timedelta(days=1)

    elif period_end < today:
        completed_end_date = period_end

    else:
        completed_end_date = today

    completed_working_dates = [
        working_date
        for working_date in working_dates
        if working_date <= completed_end_date
    ]

    # ========================================================
    # RESPECT HIRE DATE
    # ========================================================

    if employee.hire_date:
        eligible_working_dates = [
            working_date
            for working_date in completed_working_dates
            if working_date >= employee.hire_date
        ]
    else:
        eligible_working_dates = completed_working_dates

    completed_working_days = len(
        eligible_working_dates
    )

    eligible_working_date_set = set(
        eligible_working_dates
    )

    # ========================================================
    # ATTENDANCE RECORDS
    # ========================================================

    attendance_records = Attendance.query.filter(
        Attendance.employee_id == employee_id,
        Attendance.work_date >= period_start,
        Attendance.work_date <= period_end,
    ).all()

    attendance_by_date = {}

    for record in attendance_records:

        if not record.work_date:
            continue

        attendance_by_date[
            record.work_date
        ] = record

    # ========================================================
    # APPROVED LEAVES
    # ========================================================

    leave_records = Leave.query.filter(
        Leave.employee_id == employee_id,
        Leave.status.ilike("approved"),
        Leave.start_date <= period_end,
        Leave.end_date >= period_start,
    ).all()

    paid_leave_dates = set()
    casual_leave_dates = set()
    unpaid_leave_dates = set()

    working_date_set = set(working_dates)

    for leave in leave_records:

        leave_type = _normalize_leave_type(
            getattr(
                leave,
                "leave_type",
                None
            )
        )

        leave_start = _normalize_date(
            getattr(
                leave,
                "start_date",
                None
            )
        )

        leave_end = _normalize_date(
            getattr(
                leave,
                "end_date",
                None
            )
        )

        if not leave_start or not leave_end:
            continue

        current_date = max(
            leave_start,
            period_start
        )

        final_date = min(
            leave_end,
            period_end
        )

        while current_date <= final_date:

            # Do not count future leave days.
            if current_date <= completed_end_date:

                if current_date in working_date_set:

                    if leave_type in PAID_LEAVE_TYPES:
                        paid_leave_dates.add(
                            current_date
                        )

                    elif leave_type in CASUAL_LEAVE_TYPES:
                        casual_leave_dates.add(
                            current_date
                        )

                    elif leave_type in UNPAID_LEAVE_TYPES:
                        unpaid_leave_dates.add(
                            current_date
                        )

            current_date += timedelta(days=1)

    # ========================================================
    # COUNTERS
    # ========================================================

    present_days = zero
    leave_days = zero
    absent_days = zero
    payable_days = zero

    paid_leave_days = zero
    casual_leave_days = zero
    unpaid_leave_days = zero

    late_days = zero
    half_day_days = zero
    deduction_days = zero

    # ========================================================
    # LOOP THROUGH COMPLETED WORKING DAYS
    # ========================================================

    for work_date in eligible_working_dates:

        # ----------------------------------------------------
        # PAID LEAVE
        # ----------------------------------------------------

        if work_date in paid_leave_dates:

            paid_leave_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # CASUAL LEAVE
        # ----------------------------------------------------

        if work_date in casual_leave_dates:

            casual_leave_days += Decimal("1")
            deduction_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # UNPAID LEAVE
        # ----------------------------------------------------

        if work_date in unpaid_leave_dates:

            unpaid_leave_days += Decimal("1")
            deduction_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # GET ATTENDANCE
        # ----------------------------------------------------

        attendance = attendance_by_date.get(
            work_date
        )

        # ----------------------------------------------------
        # NO ATTENDANCE = ABSENT
        # ----------------------------------------------------

        if not attendance:

            absent_days += Decimal("1")
            deduction_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # NORMALIZE STATUS
        # ----------------------------------------------------

        status = _normalize_text(
            getattr(
                attendance,
                "status",
                None
            )
        )

        is_late = bool(
            getattr(
                attendance,
                "is_late",
                False
            )
        )

        # ----------------------------------------------------
        # PRESENT
        # ----------------------------------------------------
        #
        # This handles:
        #
        # present
        # Present
        # PRESENT
        #
        # because _normalize_text() converts everything
        # to lowercase.
        # ----------------------------------------------------

        if status == "present":

            present_days += Decimal("1")

            if is_late:
                late_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # OLD LATE RECORDS
        # ----------------------------------------------------

        if status == "late":

            present_days += Decimal("1")
            late_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # HALF DAY
        # ----------------------------------------------------

        if status in {
            "half_day",
            "halfday"
        }:

            present_days += Decimal("0.5")

            half_day_days += Decimal("1")

            deduction_days += Decimal("0.5")

            if is_late:
                late_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # ABSENT
        # ----------------------------------------------------

        if status == "absent":

            absent_days += Decimal("1")
            deduction_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # OLD LEAVE STATUS
        # ----------------------------------------------------

        if status == "leave":

            paid_leave_days += Decimal("1")

            continue

        # ----------------------------------------------------
        # UNKNOWN STATUS
        #
        # Safely treat unknown attendance as present.
        # ----------------------------------------------------

        present_days += Decimal("1")

        if is_late:
            late_days += Decimal("1")

    # ========================================================
    # LEAVE COUNTS
    # ========================================================

    leave_days = (
        paid_leave_days
        + casual_leave_days
        + unpaid_leave_days
    )

    # ========================================================
    # PAYABLE DAYS
    #
    # Payable days are:
    #
    # Present
    # + Paid Leave
    # + Half Day (0.5)
    #
    # Casual and unpaid leave are not payable.
    # ========================================================

    payable_days = (
        present_days
        + paid_leave_days
    )

    if payable_days < zero:
        payable_days = zero

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "working_days": total_working_days,
        "completed_working_days": completed_working_days,

        "present_days": present_days,

        "leave_days": leave_days,

        "absent_days": absent_days,

        "payable_days": payable_days,

        "paid_leave_days": paid_leave_days,

        "casual_leave_days": casual_leave_days,

        "unpaid_leave_days": unpaid_leave_days,

        "late_days": late_days,

        "half_day_days": half_day_days,

        "deduction_days": deduction_days,
    }


# ============================================================
# SALARY CALCULATION
# ============================================================

def _calculate_salary(
    employee,
    pay_type,
    basic_salary,
    allowances,
    deductions,
    attendance,
    month,
    year,
):
    zero = Decimal("0")

    basic_salary = _to_decimal(
        basic_salary,
        "basic_salary",
        default="0"
    )

    allowances = _to_decimal(
        allowances,
        "allowances",
        default="0"
    )

    deductions = _to_decimal(
        deductions,
        "deductions",
        default="0"
    )

    # ========================================================
    # PRE-HIRE
    # ========================================================

    if _is_pre_hire_period(
        employee,
        month,
        year
    ):
        return {
            "daily_salary": zero,
            "monthly_salary": zero,
            "attendance_deduction": zero,
            "allowances": zero,
            "deductions": zero,
            "net_salary": zero,
        }

    # ========================================================
    # PENALTIES
    # ========================================================

    absent_penalty = (
        attendance["absent_days"]
        * ABSENT_DEDUCTION
    )

    half_day_penalty = (
        attendance["half_day_days"]
        * HALF_DAY_DEDUCTION
    )

    late_penalty = (
        attendance["late_days"]
        * LATE_DEDUCTION
    )

    casual_leave_penalty = (
        attendance["casual_leave_days"]
        * CASUAL_LEAVE_DEDUCTION
    )

    unpaid_leave_penalty = (
        attendance["unpaid_leave_days"]
        * UNPAID_LEAVE_DEDUCTION
    )

    # ========================================================
    # TOTAL ATTENDANCE DEDUCTION
    # ========================================================

    displayed_attendance_deduction = (
        absent_penalty
        + half_day_penalty
        + late_penalty
        + casual_leave_penalty
        + unpaid_leave_penalty
    )

    # ========================================================
    # DAILY PAY TYPE
    # ========================================================

    if pay_type == "daily":

        completed_working_days = Decimal(
            attendance["completed_working_days"]
        )

        payable_working_days = (
            completed_working_days
            - attendance["casual_leave_days"]
            - attendance["unpaid_leave_days"]
        )

        if payable_working_days < zero:
            payable_working_days = zero

        daily_salary = basic_salary

        monthly_salary = (
            daily_salary
            * payable_working_days
        )

        # For daily payroll:
        #
        # Present/Absent days are already represented
        # by payable working days.
        #
        # Late has its separate Rs. 1000 penalty.
        applied_attendance_deduction = late_penalty

    # ========================================================
    # MONTHLY PAY TYPE
    # ========================================================

    else:

        total_month_working_days = Decimal(
            attendance["working_days"]
        )

        if total_month_working_days <= zero:

            daily_salary = zero
            monthly_salary = zero

        else:

            daily_salary = (
                basic_salary
                / total_month_working_days
            )

            # If employee was hired during the month,
            # prorate salary from hire date.

            if employee.hire_date:

                period_start, period_end = (
                    _get_period_dates(
                        month,
                        year
                    )
                )

                if (
                    employee.hire_date >= period_start
                    and employee.hire_date <= period_end
                ):

                    eligible_working_days = Decimal(
                        len([
                            work_date
                            for work_date
                            in _get_working_dates(
                                month,
                                year,
                                employee
                            )
                            if work_date >= employee.hire_date
                        ])
                    )

                    monthly_salary = (
                        daily_salary
                        * eligible_working_days
                    )

                else:

                    monthly_salary = basic_salary

            else:

                monthly_salary = basic_salary

        applied_attendance_deduction = (
            displayed_attendance_deduction
        )

    # ========================================================
    # NET SALARY
    #
    # Late deduction IS included here.
    # ========================================================

    net_salary = (
        monthly_salary
        - applied_attendance_deduction
        + allowances
        - deductions
    )

    if net_salary < zero:
        net_salary = zero

    return {
        "daily_salary": daily_salary,
        "monthly_salary": monthly_salary,
        "attendance_deduction": applied_attendance_deduction,
        "allowances": allowances,
        "deductions": deductions,
        "net_salary": net_salary,
    }

# ============================================================
# UPDATE EXISTING PAYROLL RECORD
# ============================================================

def _update_payroll_record(record):

    employee = Employee.query.get(
        record.employee_id
    )

    if not employee:
        return

    # ========================================================
    # PRE-HIRE PAYROLL
    # ========================================================

    if _is_pre_hire_period(
        employee,
        record.month,
        record.year
    ):

        record.basic_salary = Decimal("0")
        record.daily_salary = Decimal("0")

        record.working_days = 0
        record.present_days = Decimal("0")
        record.leave_days = Decimal("0")
        record.absent_days = Decimal("0")
        record.payable_days = Decimal("0")
        record.late_days = Decimal("0")

        record.attendance_deduction = Decimal("0")

        record.allowances = Decimal("0")
        record.deductions = Decimal("0")

        record.net_salary = Decimal("0")

        return

    # ========================================================
    # ATTENDANCE
    # ========================================================

    attendance = _calculate_attendance(
        employee.id,
        record.month,
        record.year
    )

    # ========================================================
    # SALARY
    # ========================================================

    salary = _calculate_salary(
        employee=employee,
        pay_type=record.pay_type,
        basic_salary=record.basic_salary,
        allowances=record.allowances,
        deductions=record.deductions,
        attendance=attendance,
        month=record.month,
        year=record.year,
    )

    # ========================================================
    # UPDATE RECORD
    # ========================================================

    record.daily_salary = salary[
        "daily_salary"
    ]

    record.working_days = attendance[
        "working_days"
    ]

    record.present_days = attendance[
        "present_days"
    ]

    record.leave_days = attendance[
        "leave_days"
    ]

    record.absent_days = attendance[
        "absent_days"
    ]

    record.payable_days = attendance[
        "payable_days"
    ]

    record.late_days = attendance[
        "late_days"
    ]

    record.attendance_deduction = salary[
        "attendance_deduction"
    ]

    record.net_salary = salary[
        "net_salary"
    ]

# ============================================================
# GET ALL PAYROLL
# ============================================================

@payroll_bp.route("/", methods=["GET"])
@jwt_required()
def get_payroll():

    current_user = get_current_user()

    if not current_user:
        return error("Unauthorized", 401)

    employee_id = request.args.get(
        "employee_id",
        type=int
    )

    # ========================================================
    # ADMIN / HR
    # ========================================================

    if current_user.role in {"admin", "hr"}:

        query = Payroll.query

        if employee_id:
            query = query.filter(
                Payroll.employee_id == employee_id
            )

        records = query.order_by(
            Payroll.year.desc(),
            Payroll.month.desc()
        ).all()

    # ========================================================
    # EMPLOYEE
    # ========================================================

    elif current_user.role == "employee":

        employee = Employee.query.filter_by(
            user_id=current_user.id
        ).first()

        if not employee:
            return jsonify([])

        records = Payroll.query.filter_by(
            employee_id=employee.id
        ).order_by(
            Payroll.year.desc(),
            Payroll.month.desc()
        ).all()

    else:
        return error("Access denied", 403)

    # ========================================================
    # RECALCULATE
    # ========================================================

    for record in records:
        _update_payroll_record(record)

    db.session.commit()

    return jsonify([
        record.to_dict()
        for record in records
    ])


# ============================================================
# GET SINGLE PAYROLL
# ============================================================

@payroll_bp.route(
    "/<int:payroll_id>",
    methods=["GET"]
)
@jwt_required()
def get_single_payroll(payroll_id):

    current_user = get_current_user()

    if not current_user:
        return error("Unauthorized", 401)

    record = Payroll.query.get(payroll_id)

    if not record:
        return error(
            "Payroll record not found",
            404
        )

    # ========================================================
    # EMPLOYEE ACCESS
    # ========================================================

    if current_user.role == "employee":

        employee = Employee.query.filter_by(
            user_id=current_user.id
        ).first()

        if not employee:
            return error(
                "Employee record not found",
                404
            )

        if record.employee_id != employee.id:
            return error(
                "Access denied",
                403
            )

    # ========================================================
    # ROLE CHECK
    # ========================================================

    elif current_user.role not in {
        "admin",
        "hr"
    }:

        return error(
            "Access denied",
            403
        )

    # ========================================================
    # RECALCULATE
    # ========================================================

    _update_payroll_record(record)

    db.session.commit()

    return jsonify(
        record.to_dict()
    )


# ============================================================
# CREATE PAYROLL
# ============================================================

@payroll_bp.route("/", methods=["POST"])
@jwt_required()
@roles_required("admin", "hr")
def create_payroll():

    data = request.get_json() or {}

    # ========================================================
    # EMPLOYEE
    # ========================================================

    employee_id = data.get("employee_id")

    if not employee_id:
        return error(
            "employee_id is required",
            400
        )

    employee = Employee.query.get(
        employee_id
    )

    if not employee:
        return error(
            "Employee not found",
            404
        )

    # ========================================================
    # MONTH
    # ========================================================

    try:
        month = int(
            data.get("month")
        )
    except (TypeError, ValueError):

        return error(
            "month must be a valid number",
            400
        )

    if month < 1 or month > 12:
        return error(
            "month must be between 1 and 12",
            400
        )

    # ========================================================
    # YEAR
    # ========================================================

    try:
        year = int(
            data.get("year")
        )
    except (TypeError, ValueError):

        return error(
            "year must be a valid number",
            400
        )

    if year < 2000:
        return error(
            "Invalid year",
            400
        )

    # ========================================================
    # PAY TYPE
    # ========================================================

    pay_type = _normalize_text(
        data.get(
            "pay_type",
            "monthly"
        )
    )

    if pay_type not in {
        "monthly",
        "daily"
    }:

        return error(
            "pay_type must be monthly or daily",
            400
        )

    # ========================================================
    # PAYMENT METHOD
    # ========================================================

    payment_method = _normalize_text(
        data.get(
            "payment_method",
            "bank"
        )
    )

    if payment_method not in ALLOWED_PAYMENT_METHODS:

        return error(
            "payment_method must be cash or bank",
            400
        )

    # ========================================================
    # PAYMENT STATUS
    # ========================================================

    payment_status = _normalize_text(
        data.get(
            "payment_status",
            "pending"
        )
    )

    if payment_status not in ALLOWED_PAYMENT_STATUSES:

        return error(
            "payment_status must be pending or paid",
            400
        )

    # ========================================================
    # DUPLICATE CHECK
    # ========================================================

    existing = Payroll.query.filter_by(
        employee_id=employee_id,
        month=month,
        year=year
    ).first()

    if existing:
        return error(
            "Payroll already exists for this employee and month",
            409
        )

    # ========================================================
    # SALARY VALUES
    # ========================================================

    try:

        basic_salary = _to_decimal(
            data.get(
                "basic_salary",
                employee.basic_salary or 0
            ),
            "basic_salary",
            default="0"
        )

        allowances = _to_decimal(
            data.get(
                "allowances",
                0
            ),
            "allowances",
            default="0"
        )

        deductions = _to_decimal(
            data.get(
                "deductions",
                0
            ),
            "deductions",
            default="0"
        )

    except ValueError as exc:

        return error(
            str(exc),
            400
        )

    if basic_salary < 0:
        return error(
            "basic_salary cannot be negative",
            400
        )

    if allowances < 0:
        return error(
            "allowances cannot be negative",
            400
        )

    if deductions < 0:
        return error(
            "deductions cannot be negative",
            400
        )

    # ========================================================
    # PRE-HIRE
    # ========================================================

    if _is_pre_hire_period(
        employee,
        month,
        year
    ):

        basic_salary = Decimal("0")
        allowances = Decimal("0")
        deductions = Decimal("0")

    # ========================================================
    # ATTENDANCE
    # ========================================================

    attendance = _calculate_attendance(
        employee.id,
        month,
        year
    )

    # ========================================================
    # SALARY
    # ========================================================

    salary = _calculate_salary(
        employee=employee,
        pay_type=pay_type,
        basic_salary=basic_salary,
        allowances=allowances,
        deductions=deductions,
        attendance=attendance,
        month=month,
        year=year,
    )

    # ========================================================
    # CREATE PAYROLL
    # ========================================================

    record = Payroll(
        employee_id=employee_id,
        month=month,
        year=year,
        pay_type=pay_type,
        basic_salary=basic_salary,
        daily_salary=salary["daily_salary"],
        allowances=allowances,
        deductions=deductions,
        attendance_deduction=salary[
            "attendance_deduction"
        ],
        net_salary=salary["net_salary"],
        working_days=attendance[
            "working_days"
        ],
        present_days=attendance[
            "present_days"
        ],
        leave_days=attendance[
            "leave_days"
        ],
        absent_days=attendance[
            "absent_days"
        ],
        payable_days=attendance[
            "payable_days"
        ],
        late_days=attendance[
            "late_days"
        ],
        payment_method=payment_method,
        payment_status=payment_status,
    )

    db.session.add(record)

    # ========================================================
    # INITIAL SALARY NOTIFICATION
    # ========================================================

    if payment_status == "paid":

        _create_payroll_notification(
            employee_id,
            month,
            year,
            "salary_paid"
        )

    else:

        _create_payroll_notification(
            employee_id,
            month,
            year,
            "salary_pending"
        )

    db.session.commit()

    return jsonify(
        record.to_dict()
    ), 201


# ============================================================
# UPDATE PAYROLL
# ============================================================

@payroll_bp.route(
    "/<int:payroll_id>",
    methods=["PUT"]
)
@jwt_required()
@roles_required("admin", "hr")
def update_payroll(payroll_id):

    record = Payroll.query.get(
        payroll_id
    )

    if not record:
        return error(
            "Payroll record not found",
            404
        )

    data = request.get_json() or {}

    # ========================================================
    # PAY TYPE
    # ========================================================

    if "pay_type" in data:

        pay_type = _normalize_text(
            data.get("pay_type")
        )

        if pay_type not in {
            "monthly",
            "daily"
        }:

            return error(
                "pay_type must be monthly or daily",
                400
            )

        record.pay_type = pay_type

    # ========================================================
    # BASIC SALARY
    # ========================================================

    if "basic_salary" in data:

        try:

            basic_salary = _to_decimal(
                data.get(
                    "basic_salary"
                ),
                "basic_salary"
            )

        except ValueError as exc:

            return error(
                str(exc),
                400
            )

        if basic_salary < 0:

            return error(
                "basic_salary cannot be negative",
                400
            )

        record.basic_salary = basic_salary

    # ========================================================
    # ALLOWANCES
    # ========================================================

    if "allowances" in data:

        try:

            allowances = _to_decimal(
                data.get(
                    "allowances"
                ),
                "allowances"
            )

        except ValueError as exc:

            return error(
                str(exc),
                400
            )

        if allowances < 0:

            return error(
                "allowances cannot be negative",
                400
            )

        record.allowances = allowances

    # ========================================================
    # DEDUCTIONS
    # ========================================================

    if "deductions" in data:

        try:

            deductions = _to_decimal(
                data.get(
                    "deductions"
                ),
                "deductions"
            )

        except ValueError as exc:

            return error(
                str(exc),
                400
            )

        if deductions < 0:

            return error(
                "deductions cannot be negative",
                400
            )

        record.deductions = deductions

    # ========================================================
    # RECALCULATE
    # ========================================================

    _update_payroll_record(record)

    db.session.commit()

    return jsonify(
        record.to_dict()
    )


# ============================================================
# PAYMENT METHOD / PAYMENT STATUS
# ============================================================

@payroll_bp.route(
    "/<int:payroll_id>/payment",
    methods=["PATCH"]
)
@jwt_required()
@roles_required("admin", "hr")
def update_payment(payroll_id):

    record = Payroll.query.get(
        payroll_id
    )

    if not record:
        return error(
            "Payroll record not found",
            404
        )

    data = request.get_json() or {}

    payment_method = data.get(
        "payment_method"
    )

    payment_status = data.get(
        "payment_status"
    )

    old_status = record.payment_status

    # ========================================================
    # PAYMENT METHOD
    # ========================================================

    if payment_method is not None:

        payment_method = _normalize_text(
            payment_method
        )

        if payment_method not in ALLOWED_PAYMENT_METHODS:

            return error(
                "payment_method must be cash or bank",
                400
            )

        record.payment_method = payment_method

    # ========================================================
    # PAYMENT STATUS
    # ========================================================

    if payment_status is not None:

        payment_status = _normalize_text(
            payment_status
        )

        if payment_status not in ALLOWED_PAYMENT_STATUSES:

            return error(
                "payment_status must be pending or paid",
                400
            )

        record.payment_status = payment_status

    # ========================================================
    # REQUIRE SOMETHING TO UPDATE
    # ========================================================

    if (
        payment_method is None
        and payment_status is None
    ):

        return error(
            "payment_method or payment_status is required",
            400
        )

    # ========================================================
    # NOTIFICATION
    # ========================================================

    if payment_status is not None:

        if (
            old_status != "paid"
            and payment_status == "paid"
        ):

            _create_payroll_notification(
                record.employee_id,
                record.month,
                record.year,
                "salary_paid"
            )

        elif (
            old_status != "pending"
            and payment_status == "pending"
        ):

            _create_payroll_notification(
                record.employee_id,
                record.month,
                record.year,
                "salary_pending"
            )

    db.session.commit()

    return jsonify(
        record.to_dict()
    )


# ============================================================
# RECALCULATE PAYROLL
# ============================================================

@payroll_bp.route(
    "/<int:payroll_id>/recalculate",
    methods=["POST"]
)
@jwt_required()
@roles_required("admin", "hr")
def recalculate_payroll(payroll_id):

    record = Payroll.query.get(
        payroll_id
    )

    if not record:
        return error(
            "Payroll record not found",
            404
        )

    _update_payroll_record(record)

    db.session.commit()

    return jsonify(
        record.to_dict()
    )


# ============================================================
# LATE MARKINGS
# ============================================================

@payroll_bp.route(
    "/late-markings",
    methods=["GET"]
)
@jwt_required()
@roles_required("admin", "hr")
def get_late_markings():
    """
    Dedicated Payroll -> Late Markings section.

    Results are aggregated by:

        employee + month + year

    Therefore an employee with multiple late records
    in the same month appears only ONCE.

    Example:

        Ali:
        Late 1 = 75 minutes
        Late 2 = 0 minutes

    becomes:

        Ali | 9/2026 | 2 | 75 min | 2000
    """

    employee_id = request.args.get(
        "employee_id",
        type=int
    )

    month = request.args.get(
        "month",
        type=int
    )

    year = request.args.get(
        "year",
        type=int
    )

    query = Attendance.query.filter(
        or_(
            Attendance.is_late.is_(True),
            Attendance.status.ilike("late")
        )
    )

    # ========================================================
    # EMPLOYEE FILTER
    # ========================================================

    if employee_id:

        query = query.filter(
            Attendance.employee_id == employee_id
        )

    # ========================================================
    # MONTH / YEAR FILTER
    # ========================================================

    if month and year:

        if month < 1 or month > 12:

            return error(
                "month must be between 1 and 12",
                400
            )

        period_start, period_end = (
            _get_period_dates(
                month,
                year
            )
        )

        query = query.filter(
            Attendance.work_date >= period_start,
            Attendance.work_date <= period_end,
        )

    elif year:

        if year < 2000:

            return error(
                "Invalid year",
                400
            )

        period_start = date(
            year,
            1,
            1
        )

        period_end = date(
            year,
            12,
            31
        )

        query = query.filter(
            Attendance.work_date >= period_start,
            Attendance.work_date <= period_end,
        )

    records = query.order_by(
        Attendance.work_date.desc()
    ).all()

    # ========================================================
    # AGGREGATE
    # ========================================================

    aggregated = {}

    for attendance in records:

        employee = attendance.employee

        if not employee:
            continue

        # ----------------------------------------------------
        # Make sure this really is a late record
        # ----------------------------------------------------

        is_late_record = (
            bool(
                attendance.is_late
            )
            or
            _normalize_text(
                attendance.status
            ) == "late"
        )

        if not is_late_record:
            continue

        # ----------------------------------------------------
        # Determine month/year
        # ----------------------------------------------------

        if not attendance.work_date:
            continue

        record_month = attendance.work_date.month
        record_year = attendance.work_date.year

        # ----------------------------------------------------
        # Employee + Month + Year
        # ----------------------------------------------------

        aggregation_key = (
            employee.id,
            record_month,
            record_year
        )

        # ----------------------------------------------------
        # Department
        # ----------------------------------------------------

        department = None

        if employee.departments:
            department = employee.departments[0]

        # ----------------------------------------------------
        # Late minutes
        # ----------------------------------------------------

        late_minutes = int(
            attendance.late_minutes or 0
        )

        # ----------------------------------------------------
        # Create group
        # ----------------------------------------------------

        if aggregation_key not in aggregated:

            aggregated[aggregation_key] = {
                "employee_id": employee.id,

                "employee": {
                    "id": employee.id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "email": employee.email,
                },

                "department": (
                    {
                        "id": department.id,
                        "name": department.name,
                    }
                    if department
                    else None
                ),

                "month": record_month,
                "year": record_year,

                "late_count": 0,
                "total_late_minutes": 0,
                "late_deduction": Decimal("0"),
            }

        # ----------------------------------------------------
        # ADD THIS LATE RECORD
        # ----------------------------------------------------

        aggregated[
            aggregation_key
        ]["late_count"] += 1

        aggregated[
            aggregation_key
        ]["total_late_minutes"] += late_minutes

        aggregated[
            aggregation_key
        ]["late_deduction"] += LATE_DEDUCTION

    # ========================================================
    # BUILD RESPONSE
    # ========================================================

    result = []

    for group in aggregated.values():

        result.append({
            "employee_id": group[
                "employee_id"
            ],

            "employee": group[
                "employee"
            ],

            "department": group[
                "department"
            ],

            "month": group[
                "month"
            ],

            "year": group[
                "year"
            ],

            "late_count": group[
                "late_count"
            ],

            "total_late_minutes": group[
                "total_late_minutes"
            ],

            "late_deduction": float(
                group[
                    "late_deduction"
                ]
            ),

            # Compatibility fields
            "is_late": True,
            "status": "present",
        })

    # ========================================================
    # SORT
    # Newest year/month first
    # ========================================================

    result.sort(
        key=lambda item: (
            item["year"],
            item["month"],
            item["employee"]["last_name"],
            item["employee"]["first_name"],
        ),
        reverse=True
    )

    return jsonify(result)


# ============================================================
# DELETE PAYROLL
# ============================================================

@payroll_bp.route(
    "/<int:payroll_id>",
    methods=["DELETE"]
)
@jwt_required()
@roles_required("admin")
def delete_payroll(payroll_id):

    record = Payroll.query.get(
        payroll_id
    )

    if not record:
        return error(
            "Payroll record not found",
            404
        )

    db.session.delete(record)

    db.session.commit()

    return jsonify({
        "message": "Payroll deleted successfully"
    })