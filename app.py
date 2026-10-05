from flask import Flask, jsonify, render_template
from flask_cors import CORS

from config import Config
from extensions import db, jwt, migrate


def create_app():
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Enable CORS
    CORS(app)

    # Import models so SQLAlchemy knows about them
    import models  # noqa: F401

    # Import blueprints
    from routes.auth_routes import auth_bp
    from routes.department_routes import department_bp
    from routes.employee_routes import employee_bp
    from routes.attendance_routes import attendance_bp
    from routes.leave_routes import leave_bp
    from routes.payroll_routes import payroll_bp
    from routes.notification_routes import notification_bp
    from routes.chat_routes import chat_bp

    # Register blueprints
    app.register_blueprint(
        auth_bp,
        url_prefix="/api/auth"
    )

    app.register_blueprint(
        department_bp,
        url_prefix="/api/departments"
    )

    app.register_blueprint(
        employee_bp,
        url_prefix="/api/employees"
    )

    app.register_blueprint(
        attendance_bp,
        url_prefix="/api/attendance"
    )

    app.register_blueprint(
        leave_bp,
        url_prefix="/api/leave"
    )

    app.register_blueprint(
        payroll_bp,
        url_prefix="/api/payroll"
    )

    app.register_blueprint(
        notification_bp,
        url_prefix="/api/notifications"
    )

    app.register_blueprint(
        chat_bp,
        url_prefix="/api/chat"
    )

    # =========================================================
    # FRONTEND
    # =========================================================

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/dashboard")
    def dashboard():
        return render_template("index.html")

    # =========================================================
    # HEALTH CHECK
    # =========================================================

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok"
        })

    return app


# Create Flask application
app = create_app()


if __name__ == "__main__":
    app.run(debug=True)