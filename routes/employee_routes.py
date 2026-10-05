from flask import Blueprint, jsonify, request

from extensions import db
from models.department import Department
from models.employee import Employee
from models.user import User
from utils.decorators import get_current_user, roles_required
from utils.helpers import error, parse_date
from decimal import Decimal, InvalidOperation

employee_bp = Blueprint("employees", __name__)


# ---------------------------------------------------------
# Check if user can view an employee
# ---------------------------------------------------------
def _can_view_employee(user, employee):
    if user.role in ("admin", "hr"):
        return True

    return user.employee and user.employee.id == employee.id


# ---------------------------------------------------------
# List employees
# ---------------------------------------------------------
@employee_bp.get("/")
@roles_required("admin", "hr", "employee")
def list_employees():
    user = get_current_user()

    if user.role in ("admin", "hr"):
        employees = Employee.query.order_by(Employee.id).all()
    else:
        if not user.employee:
            return error(
                "No employee profile is linked to this account",
                400
            )

        employees = [user.employee]

    return jsonify([
        employee.to_dict()
        for employee in employees
    ])


# ---------------------------------------------------------
# Get one employee
# ---------------------------------------------------------
@employee_bp.get("/<int:employee_id>")
@roles_required("admin", "hr", "employee")
def get_employee(employee_id):
    user = get_current_user()

    employee = db.session.get(Employee, employee_id)

    if not employee:
        return error("Employee not found", 404)

    if not _can_view_employee(user, employee):
        return error(
            "You do not have permission to view this employee",
            403
        )

    return jsonify(employee.to_dict())


# ---------------------------------------------------------
# Create an employee
# ---------------------------------------------------------
@employee_bp.post("/")
@roles_required("admin", "hr")
def create_employee():
    data = request.get_json(silent=True) or {}

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()

    # Validate required fields
    if not first_name or not last_name or not email:
        return error(
            "first_name, last_name, and email are required"
        )

    # Check duplicate email
    if Employee.query.filter_by(email=email).first():
        return error(
            "Employee email already exists",
            409
        )

    # -----------------------------------------------------
    # Multiple departments
    # -----------------------------------------------------
    department_ids = data.get("department_ids", [])

    if department_ids is None:
        department_ids = []

    if not isinstance(department_ids, list):
        return error(
            "department_ids must be a list"
        )

    departments = []

    for department_id in department_ids:
        try:
            department_id = int(department_id)
        except (TypeError, ValueError):
            return error(
                f"Invalid department id: {department_id}"
            )

        department = db.session.get(
            Department,
            department_id
        )

        if not department:
            return error(
                f"Department with id {department_id} not found",
                404
            )

        departments.append(department)

    # -----------------------------------------------------
    # Linked user
    # -----------------------------------------------------
    user_id = data.get("user_id")

    if user_id is not None:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return error("Invalid user_id")

        user = db.session.get(User, user_id)

        if not user:
            return error(
                "User not found",
                404
            )

        if user.employee:
            return error(
                "User is already linked to an employee",
                409
            )

    # -----------------------------------------------------
    # Parse hire date
    # -----------------------------------------------------
    try:
        hire_date = parse_date(
            data.get("hire_date"),
            "hire_date"
        )
    except ValueError as exc:
        return error(str(exc))

    basic_salary = data.get("basic_salary")

    if basic_salary in (None, ""):
        basic_salary = None
    else:
        try:
            basic_salary = Decimal(str(basic_salary))
            
            if basic_salary < 0:
                return jsonify({
                    "error": "Basic salary cannot be negative"
                }), 400

        except (InvalidOperation, ValueError, TypeError):
            return jsonify({
                "error": "Invalid basic salary"
            }), 400


    account_number = data.get("account_number")

    if isinstance(account_number, str):
        account_number = account_number.strip() or None
    else:
        account_number = None

    # -----------------------------------------------------
    # Create employee
    # -----------------------------------------------------
    employee = Employee(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=data.get("phone"),
        job_title=data.get("job_title"),
        basic_salary=basic_salary,
        account_number=account_number,
        hire_date=hire_date,
        status=(data.get("status") or "active").strip().lower()
    )

    # Assign multiple departments
    employee.departments = departments

    try:
        db.session.add(employee)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()

        return error(
            f"Could not create employee: {str(exc)}",
            500
        )

    return jsonify(employee.to_dict()), 201


# ---------------------------------------------------------
# Update an employee
# ---------------------------------------------------------
@employee_bp.put("/<int:employee_id>")
@roles_required("admin", "hr")
def update_employee(employee_id):
    employee = db.session.get(
        Employee,
        employee_id
    )

    if not employee:
        return error(
            "Employee not found",
            404
        )

    data = request.get_json(silent=True) or {}

    # -----------------------------------------------------
    # Update email
    # -----------------------------------------------------
    if "email" in data:
        email = (
            data.get("email") or ""
        ).strip().lower()

        if not email:
            return error(
                "email cannot be empty"
            )

        existing = Employee.query.filter(
            Employee.email == email,
            Employee.id != employee_id
        ).first()

        if existing:
            return error(
                "Employee email already exists",
                409
            )

        employee.email = email

    # -----------------------------------------------------
    # Update basic fields
    # -----------------------------------------------------
    for field in (
        "first_name",
        "last_name",
        "phone",
        "job_title",
        "status"
    ):
        if field in data and data[field] is not None:
            value = data[field]

            setattr(
                employee,
                field,
                value.strip()
                if isinstance(value, str)
                else value
            )

    # -----------------------------------------------------
    # Update salary
    # -----------------------------------------------------
    if "basic_salary" in data:
        try:
            if data.get("basic_salary") in (None, ""):
                employee.basic_salary = None
            else:
                salary = Decimal(str(data.get("basic_salary")))

                if salary < 0:
                    return error("basic_salary cannot be negative")

                employee.basic_salary = salary

        except (InvalidOperation, ValueError, TypeError):
            return error("Invalid basic_salary")    

    # -----------------------------------------------------
    # Update account number
    # -----------------------------------------------------
    if "account_number" in data:
        account_number = data.get("account_number")

        employee.account_number = (
            account_number.strip()
            if isinstance(account_number, str) and account_number.strip()
            else None
            )

    # -----------------------------------------------------
    # Update multiple departments
    # -----------------------------------------------------
    if "department_ids" in data:
        department_ids = data.get("department_ids")

        if department_ids is None:
            department_ids = []

        if not isinstance(department_ids, list):
            return error(
                "department_ids must be a list"
            )

        departments = []

        for department_id in department_ids:
            try:
                department_id = int(department_id)
            except (TypeError, ValueError):
                return error(
                    f"Invalid department id: {department_id}"
                )

            department = db.session.get(
                Department,
                department_id
            )

            if not department:
                return error(
                    f"Department with id {department_id} not found",
                    404
                )

            departments.append(department)

        # Replace existing department assignments
        employee.departments = departments

    # -----------------------------------------------------
    # Update hire date
    # -----------------------------------------------------
    if "hire_date" in data:
        try:
            employee.hire_date = parse_date(
                data.get("hire_date"),
                "hire_date"
            )
        except ValueError as exc:
            return error(str(exc))

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()

        return error(
            f"Could not update employee: {str(exc)}",
            500
        )

    return jsonify(
        employee.to_dict()
    )

# ---------------------------------------------------------
# Delete an employee
# ---------------------------------------------------------
@employee_bp.delete("/<int:employee_id>")
@roles_required("admin")
def delete_employee(employee_id):
    employee = db.session.get(
        Employee,
        employee_id
    )

    if not employee:
        return error(
            "Employee not found",
            404
        )

    try:
        db.session.delete(employee)
        db.session.commit()

        return jsonify({
            "message": "Employee deleted"
        })

    except Exception as exc:
        db.session.rollback()

        return error(
            f"Could not delete employee: {str(exc)}",
            500
        )

