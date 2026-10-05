from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
from extensions import db
from models.employee import Employee
from models.user import User
from utils.decorators import get_current_user
from utils.helpers import error

auth_bp = Blueprint("auth", __name__)

VALID_ROLES = {"admin", "hr", "employee"}

# Register a new user
@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    role = (data.get("role") or "employee").strip().lower()

    # Validate required fields
    if not email or not password:
        return error("Email and password are required")

    if not first_name or not last_name:
        return error("first_name and last_name are required")

    # Validate user role
    if role not in VALID_ROLES:
        return error("role must be admin, hr, or employee")

    # Check for duplicate email
    if User.query.filter_by(email=email).first():
        return error("Email is already registered", 409)

    # Only the first user can choose admin/hr
    if User.query.count() > 0:
        role = "employee"

    # Create user account
    user = User(email=email, role=role)
    user.set_password(password)

    db.session.add(user)
    db.session.flush()

    # Find existing employee profile
    employee = Employee.query.filter_by(email=email).first()

    if employee:
        # Employee already exists, so connect it to this user
        if employee.user_id is not None:
            db.session.rollback()
            return error("This employee is already linked to a user account", 409)

        employee.user_id = user.id

    else:
        # No employee exists, so create a new one
        employee = Employee(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            job_title=data.get("job_title"),
            phone=data.get("phone"),
        )

        db.session.add(employee)
    db.session.commit()

    # Generate JWT token
    token = create_access_token(identity=str(user.id))

    return (
        jsonify(
            {
                "message": "Registration successful",
                "access_token": token,
                "user": user.to_dict(),
            }
        ),
        201,
    )

# Log in an existing user
@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # Find and verify user
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return error("Invalid email or password", 401)

    # Generate JWT token
    token = create_access_token(identity=str(user.id))

    return jsonify({
        "access_token": token,
        "user": user.to_dict()
    })

# Get current logged-in user
@auth_bp.get("/me")
@jwt_required()
def me():
    user = get_current_user()

    if not user:
        return error("User not found", 401)

    print("DEBUG USER ID:", user.id)
    print("DEBUG USER EMAIL:", user.email)
    print("DEBUG USER ROLE:", user.role)
    print("DEBUG EMPLOYEE:", user.employee)
    print("DEBUG EMPLOYEE ID:", user.employee.id if user.employee else None)

    # Build user response
    payload = user.to_dict()

    if user.employee:
        payload["employee"] = user.employee.to_dict()

    return jsonify(payload)
