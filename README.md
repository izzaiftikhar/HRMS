# HRMS - Human Resource Management System

A full-stack **Human Resource Management System (HRMS)** built with Flask and PostgreSQL for managing employees, departments, attendance, leave, and payroll.

## Features

- JWT-based authentication
- Role-based access control (`admin`, `hr`, `employee`)
- Employee management
- Department management
- Attendance check-in / check-out
- Leave requests and approval
- Payroll management and calculation
- Multiple department assignments for employees
- Protected API routes with role-based permissions
- Responsive web interface
- Database migrations using Flask-Migrate

## Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy
- **Authentication:** Flask-JWT-Extended
- **Database:** PostgreSQL
- **Migrations:** Flask-Migrate / Alembic
- **Frontend:** HTML, CSS, JavaScript, Jinja2
- **Other:** Flask-CORS, python-dotenv, Werkzeug

## Project Structure

```text
HRMS/
├── app.py
├── config.py
├── extensions.py
├── requirements.txt
├── migrations/
├── models/
├── routes/
├── utils/
├── templates/
├── static/
├── .gitignore
└── README.md
