# HRMS Project

A simple **Human Resource Management System** built with Flask and PostgreSQL for managing employees, departments, attendance, leave, and payroll.

## Features

* JWT-based authentication
* Role-based access (`admin`, `hr`, `employee`)
* Employee management
* Department management
* Attendance check-in / check-out
* Leave requests and approval
* Payroll management and calculation
* Multiple department assignments for employees
* Responsive web interface
* Protected API routes with role-based permissions

## Tech Stack

* **Backend:** Flask, Flask-SQLAlchemy
* **Authentication:** Flask-JWT-Extended
* **Database:** PostgreSQL
* **Migrations:** Flask-Migrate / Alembic
* **Frontend:** HTML, CSS, JavaScript, Jinja
* **Other:** Flask-CORS, python-dotenv, Werkzeug

## Project Structure

```text
HRMS_Project/
├── app.py
├── config.py
├── extensions.py
├── requirements.txt
├── migrations/
├── models/
│   ├── user.py
│   ├── employee.py
│   ├── department.py
│   ├── attendance.py
│   ├── leave.py
│   └── payroll.py
├── routes/
│   ├── auth_routes.py
│   ├── employee_routes.py
│   ├── department_routes.py
│   ├── attendance_routes.py
│   ├── leave_routes.py
│   └── payroll_routes.py
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── app.js
```

## Installation

### 1. Create a virtual environment

```bash
python -m venv venv
```

**Windows:**

```bash
venv\Scripts\activate
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file:

```env
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/hrms_db
JWT_SECRET_KEY=your-secret-key
```

### 4. Create the database

```sql
CREATE DATABASE hrms_db;
```

Then run the migrations:

```bash
flask db upgrade
```

### 5. Start the application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Role Permissions

| Feature               | Admin |  HR | Employee |
| --------------------- | :---: | :-: | :------: |
| Employee Management   |  Yes  | Yes |    No    |
| Department Management |  Yes  | Yes |   View   |
| Attendance            |  Yes  | Yes |    Own   |
| Leave Approval        |  Yes  | Yes |    No    |
| Payroll               |  Yes  | Yes |    Own   |
| Payroll Delete        |  Yes  |  No |    No    |

## Project Status

**Completed and functionally tested**

The core HRMS workflows, authentication, role-based permissions, attendance, leave, employee and department management, and payroll functionality have been implemented and tested.
