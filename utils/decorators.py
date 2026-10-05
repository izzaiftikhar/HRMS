from functools import wraps

from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.user import User
from utils.helpers import error


def get_current_user():
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return error("User not found", 401)
            if user.role not in roles:
                return error("You do not have permission to perform this action", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
