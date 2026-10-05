/* ============================================================
 * HR MANAGEMENT SYSTEM - FRONTEND (app.js)
 * Employees, Departments, Attendance, Leave, Payroll,
 * Notifications. Chat lives in chat.js.
 * ============================================================ */


// ============================================================
// BASE API ROUTE
// ============================================================

const API_BASE = "/api";

let currentUser = null;

function getAuthToken() {
    return localStorage.getItem("token");
}

async function apiFetch(endpoint, method = "GET", data = null) {

    const headers = {
        "Content-Type": "application/json"
    };

    const token = getAuthToken();

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const config = { method, headers };

    if (data !== null) {
        config.body = JSON.stringify(data);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, config);

    let resData;

    try {
        resData = await response.json();
    } catch {
        if (!response.ok) {
            throw new Error(`Server returned HTTP ${response.status}`);
        }
        resData = {};
    }

    if (!response.ok) {
        throw new Error(
            resData.error ||
            resData.message ||
            `API Request Failed (${response.status})`
        );
    }

    return resData;
}


// ============================================================
// ROLE HELPERS
// ============================================================

function isAdmin() {
    return !!currentUser && currentUser.role === "admin";
}

function isEmployee() {
    return !!currentUser && currentUser.role === "employee";
}

function isHR() {
    return !!currentUser && currentUser.role === "hr";
}

function isAdminOrHR() {
    return isAdmin() || isHR();
}


// ============================================================
// SMALL FORM HELPERS
// ============================================================

function setFieldValue(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.value = value === null || value === undefined ? "" : value;
    }
}

function getFieldValue(id) {
    const el = document.getElementById(id);
    return el ? String(el.value ?? "") : "";
}

const WORKING_DAY_KEYS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday"
];

function getWorkingDaysFromForm(prefix) {

    const anyCheckboxExists = WORKING_DAY_KEYS.some(
        (day) => document.getElementById(`${prefix}-day-${day}`)
    );

    if (anyCheckboxExists) {
        return WORKING_DAY_KEYS.filter((day) => {
            const cb = document.getElementById(`${prefix}-day-${day}`);
            return cb && cb.checked;
        });
    }

    const textInput = document.getElementById(`${prefix}-working-days-text`);

    if (textInput) {
        return textInput.value
            .split(",")
            .map((d) => d.trim().toLowerCase())
            .filter((d) => WORKING_DAY_KEYS.includes(d));
    }

    console.warn(
        `No working-day inputs found for prefix "${prefix}", defaulting to Mon-Fri.`
    );

    return ["monday", "tuesday", "wednesday", "thursday", "friday"];
}

function setWorkingDaysInForm(prefix, days) {

    const daySet = new Set(
        (Array.isArray(days) ? days : []).map((d) => String(d).toLowerCase())
    );

    const anyCheckboxExists = WORKING_DAY_KEYS.some(
        (day) => document.getElementById(`${prefix}-day-${day}`)
    );

    if (anyCheckboxExists) {
        WORKING_DAY_KEYS.forEach((day) => {
            const cb = document.getElementById(`${prefix}-day-${day}`);
            if (cb) cb.checked = daySet.has(day);
        });
        return;
    }

    const textInput = document.getElementById(`${prefix}-working-days-text`);

    if (textInput) {
        textInput.value = Array.from(daySet).join(", ");
    }
}


// ============================================================
// ROLE-BASED UI PERMISSIONS
// ============================================================

function applyRolePermissions() {

    if (!currentUser) {
        return;
    }

    // Employee cannot access Employees / Departments views
    ["employees", "departments"].forEach((view) => {
        const nav = document.getElementById(`nav-${view}`);
        if (nav) {
            nav.style.display = isEmployee() ? "none" : "";
        }
    });

    const addPayrollBtn = document.getElementById("add-payroll-btn");
    if (addPayrollBtn) {
        addPayrollBtn.style.display = isEmployee() ? "none" : "";
    }

    const addEmployeeBtn = document.getElementById("add-employee-btn");
    if (addEmployeeBtn) {
        addEmployeeBtn.style.display = isEmployee() ? "none" : "";
    }

    const addDepartmentBtn = document.getElementById("add-department-btn");
    if (addDepartmentBtn) {
        addDepartmentBtn.style.display = isEmployee() ? "none" : "";
    }

    // Late Markings section is Admin/HR only
    const lateMarkingsSection = document.getElementById("late-markings-section");
    if (lateMarkingsSection) {
        lateMarkingsSection.style.display = isAdminOrHR() ? "" : "none";
    }

    // Attendance check-in / check-out: employee only
    const checkInBtn = document.getElementById("check-in-btn");
    const checkOutBtn = document.getElementById("check-out-btn");

    if (checkInBtn) {
        checkInBtn.style.display = isEmployee() ? "" : "none";
    }

    if (checkOutBtn) {
        checkOutBtn.style.display = isEmployee() ? "" : "none";
    }
}


// ============================================================
// AUTH UI
// ============================================================

function toggleAuthMode(mode) {

    const loginBox = document.getElementById("login-container");
    const regBox = document.getElementById("register-container");

    if (!loginBox || !regBox) {
        return;
    }

    if (mode === "register") {
        loginBox.classList.add("hidden-view");
        regBox.classList.remove("hidden-view");
    } else {
        regBox.classList.add("hidden-view");
        loginBox.classList.remove("hidden-view");
    }
}


// ============================================================
// MODAL
// ============================================================

function toggleModal(modalId, show) {

    const modal = document.getElementById(modalId);

    if (!modal) {
        return;
    }

    // Employee restrictions: these modals are never for employees
    const restrictedForEmployee = [
        "modal-add-employee",
        "modal-add-department",
        "modal-add-payroll",
        "modal-edit-employee",
        "modal-edit-department",
        "modal-edit-payroll-payment"
    ];

    if (show && isEmployee() && restrictedForEmployee.includes(modalId)) {
        alert("You do not have permission to perform this action.");
        return;
    }

    if (show) {

        modal.classList.remove("hidden-view");

        if (modalId === "modal-add-leave" && currentUser) {
            const employeeGroup = document.getElementById("leave-employee-group");
            if (employeeGroup) {
                if (isAdminOrHR()) {
                    employeeGroup.classList.remove("hidden-view");
                    loadLeaveEmployees();
                } else {
                    employeeGroup.classList.add("hidden-view");
                }
            }
        }

        if (modalId === "modal-add-employee") {
            populateDepartmentSelect("emp-dept-select");
        }

    } else {
        modal.classList.add("hidden-view");
    }
}


// ============================================================
// ALERT / TOAST
// ============================================================

function showAlert(message) {

    const alertBox = document.getElementById("auth-alert");

    if (!alertBox) {
        return;
    }

    alertBox.textContent = message;
    alertBox.className = "alert alert-error";
    alertBox.classList.remove("hidden-view");
}

function showToast(message, type = "success") {

    const toast = document.createElement("div");

    toast.textContent = message;

    toast.style.position = "fixed";
    toast.style.top = "20px";
    toast.style.right = "20px";
    toast.style.zIndex = "9999";
    toast.style.padding = "12px 18px";
    toast.style.borderRadius = "8px";
    toast.style.color = "#ffffff";
    toast.style.fontSize = "14px";
    toast.style.fontWeight = "600";
    toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.2)";

    toast.style.background = type === "error" ? "#dc2626" : "#16a34a";

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}


// ============================================================
// REGISTER (role is decided by the server, never sent from here)
// ============================================================

function setupRegisterForm() {

    const registerForm = document.getElementById("register-form");

    if (!registerForm) {
        return;
    }

    registerForm.addEventListener("submit", async (e) => {

        e.preventDefault();

        try {

            const data = {
                first_name: getFieldValue("reg-fname").trim(),
                last_name: getFieldValue("reg-lname").trim(),
                email: getFieldValue("reg-email").trim().toLowerCase(),
                password: getFieldValue("reg-password")
            };

            const res = await apiFetch("/auth/register", "POST", data);

            localStorage.setItem("token", res.access_token);

            await initDashboard();

        } catch (err) {
            console.error("Registration error:", err);
            showAlert(err.message);
        }
    });
}


// ============================================================
// LOGIN
// ============================================================

function setupLoginForm() {

    const loginForm = document.getElementById("login-form");

    if (!loginForm) {
        return;
    }

    loginForm.addEventListener("submit", async (e) => {

        e.preventDefault();

        try {

            const data = {
                email: getFieldValue("login-email").trim().toLowerCase(),
                password: getFieldValue("login-password")
            };

            const res = await apiFetch("/auth/login", "POST", data);

            localStorage.setItem("token", res.access_token);

            await initDashboard();

        } catch (err) {
            console.error("Login error:", err);
            showAlert(err.message);
        }
    });
}


// ============================================================
// LOGOUT
// ============================================================

function logout() {

    localStorage.removeItem("token");
    currentUser = null;

    notifications = [];

    // Clear the previous person's chat state
    if (typeof resetChat === "function") {
        resetChat();
    }

    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.reset();
    }

    const appScreen = document.getElementById("app-screen");
    const authScreen = document.getElementById("auth-screen");

    if (appScreen) {
        appScreen.classList.add("hidden-view");
    }

    if (authScreen) {
        authScreen.classList.remove("hidden-view");
    }
}


// ============================================================
// INITIALIZE DASHBOARD
// ============================================================

async function initDashboard() {

    try {

        currentUser = await apiFetch("/auth/me");

        const authScreen = document.getElementById("auth-screen");
        const appScreen = document.getElementById("app-screen");

        if (authScreen) authScreen.classList.add("hidden-view");
        if (appScreen) appScreen.classList.remove("hidden-view");

        // Name shown at the bottom-left of the sidebar
        const firstName = currentUser.employee?.first_name || "";
        const lastName = currentUser.employee?.last_name || "";
        const fullName = `${firstName} ${lastName}`.trim();

        const displayName = fullName || currentUser.email;

        const initials = fullName
            ? ((firstName[0] || "") + (lastName[0] || "")).toUpperCase()
            : (currentUser.email[0] || "U").toUpperCase();

        const avatar = document.getElementById("user-avatar");
        if (avatar) avatar.textContent = initials;

        const nameDisplay = document.getElementById("user-name-display");
        if (nameDisplay) nameDisplay.textContent = displayName;

        const roleDisplay = document.getElementById("user-role-display");
        if (roleDisplay) roleDisplay.textContent = currentUser.role;

        applyRolePermissions();

        await switchView("dashboard");

    } catch (err) {
        console.error("Dashboard initialization error:", err);
        logout();
        showAlert(err.message || "Could not load your account. Please sign in again.");
    }
}


// ============================================================
// VIEW NAVIGATION
// ============================================================

async function switchView(viewName) {

    if (
        isEmployee() &&
        ["employees", "departments"].includes(viewName)
    ) {
        viewName = "dashboard";
    }

    const views = [
        "dashboard",
        "employees",
        "departments",
        "attendance",
        "leave",
        "payroll",
        "chat"
    ];

    views.forEach((view) => {

        const element = document.getElementById(`view-${view}`);
        const nav = document.getElementById(`nav-${view}`);

        if (element) {
            element.classList.add("hidden-view");
        }

        if (nav) {
            nav.classList.remove("active");
        }
    });

    const selectedView = document.getElementById(`view-${viewName}`);
    const selectedNav = document.getElementById(`nav-${viewName}`);

    if (!selectedView) {
        console.error(`View not found: view-${viewName}`);
        return;
    }

    selectedView.classList.remove("hidden-view");

    if (selectedNav) {
        selectedNav.classList.add("active");
    }

    const titleMap = {
        dashboard: "Dashboard",
        employees: "Employee Management",
        departments: "Departments",
        attendance: "Attendance Log",
        leave: "Leave Management",
        payroll: "Payroll Management",
        chat: "Messages"
    };

    const pageTitle = document.getElementById("page-title");

    if (pageTitle) {
        pageTitle.textContent = titleMap[viewName] || "Dashboard";
    }

    if (viewName === "dashboard") {
        await loadDashboardStats();
    }

    if (viewName === "employees") {
        await loadEmployees();
    }

    if (viewName === "departments") {
        await loadDepartments();
    }

    if (viewName === "attendance") {
        await loadAttendance();
    }

    if (viewName === "leave") {
        await loadLeaves();
    }

    if (viewName === "payroll") {

        await loadPayroll();

        if (!isEmployee()) {
            await loadPayrollEmployees();
        }

        if (isAdminOrHR()) {
            await loadLateMarkings();
        }
    }

    if (viewName === "chat") {

        if (typeof initializeChat === "function") {
            await initializeChat();
        }
    }

    applyRolePermissions();
}


// ============================================================
// DASHBOARD STATISTICS
// ============================================================

async function loadDashboardStats() {

    try {

        let emp = [];
        let dept = [];
        let att = [];
        let lve = [];

        if (isAdminOrHR()) {
            emp = await apiFetch("/employees/");
            dept = await apiFetch("/departments/");
        } else if (isEmployee()) {
            if (currentUser && currentUser.employee) {
                emp = [currentUser.employee];
                dept = Array.isArray(currentUser.employee.departments)
                    ? currentUser.employee.departments
                    : [];
            }
        }

        att = await apiFetch("/attendance/");
        lve = await apiFetch("/leave/");

        const totalEmp = document.getElementById("stat-total-emp");
        const totalDept = document.getElementById("stat-total-dept");
        const presentToday = document.getElementById("stat-present-today");
        const pendingLeaves = document.getElementById("stat-pending-leaves");

        if (totalEmp) {
            totalEmp.textContent = Array.isArray(emp) ? emp.length : 0;
        }

        if (totalDept) {
            totalDept.textContent = Array.isArray(dept) ? dept.length : 0;
        }

        if (presentToday) {

            const today = getLocalDateString();

            // Late employees are Present + Late, never Absent
            const presentCount = Array.isArray(att)
                ? att.filter((item) => item.work_date === today && item.status === "present").length
                : 0;

            presentToday.textContent = presentCount;
        }

        if (pendingLeaves) {
            const pendingCount = Array.isArray(lve)
                ? lve.filter((item) => item.status === "pending").length
                : 0;
            pendingLeaves.textContent = pendingCount;
        }

    } catch (err) {
        console.error("Dashboard statistics error:", err);
    }
}


// ============================================================
// EMPLOYEE MANAGEMENT
// ============================================================

async function loadEmployees() {

    if (isEmployee()) {
        await switchView("dashboard");
        return;
    }

    const tbody = document.getElementById("employee-table-body");
    if (!tbody) return;

    try {

        tbody.innerHTML = "";

        const list = await apiFetch("/employees/");

        if (!Array.isArray(list) || list.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" style="text-align:center;">
                        No employees found.
                    </td>
                </tr>
            `;
            return;
        }

        list.forEach((employee, index) => {

            // Admin cannot delete their own profile
            const isSelf =
                !!currentUser &&
                !!currentUser.employee &&
                Number(currentUser.employee.id) === Number(employee.id);

            const deleteButton = isAdmin() && !isSelf
                ? `
                    <button
                        onclick="deleteEmployee(${employee.id})"
                        class="btn btn-danger"
                        style="padding:0.35rem 0.6rem;font-size:0.75rem;"
                    >
                        <i class="fa-solid fa-trash"></i> Delete
                    </button>
                `
                : "";

            const employeeActions = isAdminOrHR()
                ? `
                    <button
                        onclick="editEmployee(${employee.id})"
                        class="btn btn-primary"
                        style="padding:0.35rem 0.6rem;font-size:0.75rem;margin-right:0.35rem;"
                    >
                        <i class="fa-solid fa-pen"></i> Edit
                    </button>
                    ${deleteButton}
                `
                : `<span style="color:#94a3b8;font-size:0.75rem;">View Only</span>`;

            let departmentHTML = "Unassigned";

            if (Array.isArray(employee.departments) && employee.departments.length > 0) {
                departmentHTML = employee.departments
                    .map((department) => `<span class="badge">${escapeHtml(department.name)}</span>`)
                    .join(" ");
            }

            let salaryDisplay = "N/A";

            if (
                employee.basic_salary !== null &&
                employee.basic_salary !== undefined &&
                employee.basic_salary !== ""
            ) {
                const salaryNumber = Number(employee.basic_salary);
                if (Number.isFinite(salaryNumber)) {
                    salaryDisplay = salaryNumber.toLocaleString("en-US", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    });
                }
            }

            const accountDisplay = escapeHtml(employee.account_number || "N/A");

            // First column is a running number (1, 2, 3...), not the database id
            tbody.innerHTML += `
                <tr>
                    <td>${index + 1}</td>
                    <td><strong>${escapeHtml(employee.first_name)} ${escapeHtml(employee.last_name)}</strong></td>
                    <td>${escapeHtml(employee.email)}</td>
                    <td>${escapeHtml(employee.job_title || "N/A")}</td>
                    <td>${escapeHtml(employee.phone || "N/A")}</td>
                    <td>${departmentHTML}</td>
                    <td>${salaryDisplay}</td>
                    <td>${accountDisplay}</td>
                    <td><span class="badge badge-${escapeHtml(employee.status)}">${escapeHtml(employee.status)}</span></td>
                    <td>${employeeActions}</td>
                </tr>
            `;
        });

    } catch (err) {
        console.error("Failed to load employees:", err);
        tbody.innerHTML = `
            <tr>
                <td colspan="10" style="text-align:center;color:red;">
                    Failed to load employees: ${escapeHtml(err.message)}
                </td>
            </tr>
        `;
    }
}


// ============================================================
// DELETE EMPLOYEE
// ============================================================

async function deleteEmployee(employeeId) {

    if (!isAdmin()) {
        alert("Only Admin can delete employees.");
        return;
    }

    if (
        currentUser &&
        currentUser.employee &&
        Number(currentUser.employee.id) === Number(employeeId)
    ) {
        alert("You cannot delete your own profile.");
        return;
    }

    if (!confirm("Are you sure you want to delete this employee?")) {
        return;
    }

    try {
        await apiFetch(`/employees/${employeeId}`, "DELETE");
        showToast("Employee deleted successfully.", "success");
        await loadEmployees();
        await loadDashboardStats();
    } catch (err) {
        console.error("Delete employee error:", err);
        showToast("Failed to delete employee: " + err.message, "error");
    }
}


// ============================================================
// EDIT EMPLOYEE (opens a modal)
// ============================================================

async function editEmployee(employeeId) {

    if (!isAdminOrHR()) {
        showToast("Only Admin or HR can edit employees.", "error");
        return;
    }

    try {

        const employee = await apiFetch(`/employees/${employeeId}`);

        const modal = document.getElementById("modal-edit-employee");

        if (!modal) {
            console.error("modal-edit-employee not found in DOM.");
            showToast("Edit employee modal is not available on this page yet.", "error");
            return;
        }

        setFieldValue("edit-emp-id", employee.id);
        setFieldValue("edit-emp-fname", employee.first_name || "");
        setFieldValue("edit-emp-lname", employee.last_name || "");
        setFieldValue("edit-emp-email", employee.email || "");
        setFieldValue("edit-emp-phone", employee.phone || "");
        setFieldValue("edit-emp-title", employee.job_title || "");
        setFieldValue("edit-emp-hire-date", employee.hire_date || "");
        setFieldValue("edit-emp-status", employee.status || "active");
        setFieldValue("edit-emp-salary", employee.basic_salary ?? "");
        setFieldValue("edit-emp-account", employee.account_number ?? "");

        const currentDeptIds = Array.isArray(employee.departments)
            ? employee.departments.map((d) => d.id)
            : [];

        await populateDepartmentSelect("edit-emp-dept-select", currentDeptIds);

        toggleModal("modal-edit-employee", true);

    } catch (err) {
        console.error("Edit employee error:", err);
        showToast("Failed to load employee: " + err.message, "error");
    }
}

function setupEditEmployeeForm() {

    const form = document.getElementById("form-edit-employee");
    if (!form) return;

    form.addEventListener("submit", async (e) => {

        e.preventDefault();

        if (!isAdminOrHR()) {
            showToast("Only Admin or HR can edit employees.", "error");
            return;
        }

        try {

            const employeeId = getFieldValue("edit-emp-id");
            if (!employeeId) throw new Error("Missing employee id.");

            const departmentSelect = document.getElementById("edit-emp-dept-select");
            const departmentIds = departmentSelect
                ? Array.from(departmentSelect.selectedOptions)
                    .map((o) => parseInt(o.value, 10))
                    .filter((id) => !isNaN(id))
                : [];

            const payload = {
                first_name: getFieldValue("edit-emp-fname").trim(),
                last_name: getFieldValue("edit-emp-lname").trim(),
                email: getFieldValue("edit-emp-email").trim().toLowerCase(),
                phone: getFieldValue("edit-emp-phone").trim(),
                job_title: getFieldValue("edit-emp-title").trim(),
                hire_date: getFieldValue("edit-emp-hire-date").trim() || null,
                basic_salary: getFieldValue("edit-emp-salary").trim() || null,
                account_number: getFieldValue("edit-emp-account").trim() || null,
                status: getFieldValue("edit-emp-status").trim().toLowerCase(),
                department_ids: departmentIds
            };

            if (!payload.first_name || !payload.last_name || !payload.email) {
                showToast("First name, last name and email are required.", "error");
                return;
            }

            await apiFetch(`/employees/${employeeId}`, "PUT", payload);

            showToast("Employee updated successfully.", "success");
            toggleModal("modal-edit-employee", false);
            form.reset();

            // If you edited your own profile, refresh the sidebar name
            if (
                currentUser &&
                currentUser.employee &&
                Number(currentUser.employee.id) === Number(employeeId)
            ) {
                await initDashboard();
                await switchView("employees");
                return;
            }

            await loadEmployees();
            await loadDepartments();
            await loadDashboardStats();

        } catch (err) {
            console.error("Edit employee error:", err);
            showToast("Failed to update employee: " + err.message, "error");
        }
    });
}


// ============================================================
// DEPARTMENT SELECT (shared by Add Employee + Edit Employee)
// ============================================================

async function populateDepartmentSelect(selectId, selectedIds = []) {

    const select = document.getElementById(selectId);
    if (!select || !isAdminOrHR()) return;

    try {

        const departments = await apiFetch("/departments/");

        select.innerHTML = "";

        if (!Array.isArray(departments) || departments.length === 0) {
            select.innerHTML = `<option value="">No departments found</option>`;
            return;
        }

        const selectedSet = new Set(selectedIds.map((id) => Number(id)));

        departments.forEach((department) => {
            const option = document.createElement("option");
            option.value = department.id;
            option.textContent = department.name;
            if (selectedSet.has(Number(department.id))) {
                option.selected = true;
            }
            select.appendChild(option);
        });

    } catch (err) {
        console.error("Failed to load departments for select:", err);
        select.innerHTML = `<option value="">Failed to load departments</option>`;
    }
}

// Kept for backward compatibility
async function loadEmployeeDepartments() {
    await populateDepartmentSelect("emp-dept-select");
}


// ============================================================
// FORMAT HELPERS
// ============================================================

function formatWorkingDays(workingDays) {

    if (!Array.isArray(workingDays) || workingDays.length === 0) {
        return "No working days";
    }

    const dayNames = {
        monday: "Mon", tuesday: "Tue", wednesday: "Wed",
        thursday: "Thu", friday: "Fri", saturday: "Sat", sunday: "Sun"
    };

    const days = workingDays
        .map((day) => dayNames[String(day).trim().toLowerCase()])
        .filter(Boolean);

    if (days.length === 0) return "No working days";

    const fullWeek = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    const indexes = days
        .map((day) => fullWeek.indexOf(day))
        .filter((index) => index !== -1)
        .sort((a, b) => a - b);

    if (indexes.length === 5 && indexes.join(",") === "0,1,2,3,4") return "Mon–Fri";
    if (indexes.length === 2 && indexes.join(",") === "5,6") return "Sat–Sun";
    if (indexes.length === 7 && indexes.join(",") === "0,1,2,3,4,5,6") return "Mon–Sun";

    return days.join(", ");
}

// 24-hour API time -> 12-hour display time
function formatDisplayTime(timeStr) {

    if (!timeStr) {
        return "--:--";
    }

    const parts = String(timeStr).split(":");

    if (parts.length < 2) {
        return timeStr;
    }

    const hours = parseInt(parts[0], 10);
    const minutes = parseInt(parts[1], 10);

    if (Number.isNaN(hours) || Number.isNaN(minutes)) {
        return timeStr;
    }

    const suffix = hours >= 12 ? "PM" : "AM";
    const displayHour = hours % 12 || 12;

    return `${displayHour}:${String(minutes).padStart(2, "0")} ${suffix}`;
}


// ============================================================
// LOAD DEPARTMENTS (renders department cards)
// ============================================================

async function loadDepartments() {

    if (isEmployee()) return;

    const container = document.getElementById("department-cards-container");

    if (!container) {
        console.error("department-cards-container not found.");
        return;
    }

    container.innerHTML = `
        <div style="grid-column:1 / -1;text-align:center;padding:2rem;color:#94a3b8;">
            <i class="fa-solid fa-spinner fa-spin" style="font-size:1.8rem;margin-bottom:0.75rem;"></i>
            <div>Loading departments...</div>
        </div>
    `;

    try {

        const departments = await apiFetch("/departments/");

        container.innerHTML = "";

        if (!Array.isArray(departments) || departments.length === 0) {
            container.innerHTML = `
                <div style="grid-column:1 / -1;text-align:center;padding:3rem 1rem;color:#94a3b8;">
                    <div style="width:70px;height:70px;margin:0 auto 1rem;border-radius:18px;display:flex;align-items:center;justify-content:center;background:#f1f5f9;color:#64748b;">
                        <i class="fa-solid fa-building" style="font-size:1.8rem;"></i>
                    </div>
                    <h3 style="margin-bottom:0.5rem;color:#1e293b;">No Departments Found</h3>
                    <p>Create your first department using the button above.</p>
                </div>
            `;
            return;
        }

        departments.forEach((department) => {

            let employeeHTML = `
                <div style="padding:1rem;border-radius:10px;background:#f8fafc;color:#94a3b8;font-size:0.85rem;margin-top:0.75rem;">
                    No employees assigned
                </div>
            `;

            if (Array.isArray(department.employees) && department.employees.length > 0) {
                employeeHTML = `
                    <div style="display:flex;flex-direction:column;gap:10px;margin-top:0.75rem;">
                        ${department.employees.map((employee) => {
                            const initials = `${employee.first_name?.[0] || ""}${employee.last_name?.[0] || ""}`.toUpperCase();
                            return `
                                <div style="display:flex;align-items:center;gap:10px;padding:10px;border-radius:10px;background:#f8fafc;">
                                    <div class="avatar" style="width:34px;height:34px;min-width:34px;font-size:0.75rem;">${escapeHtml(initials)}</div>
                                    <div style="min-width:0;">
                                        <strong style="display:block;color:#1e293b;font-size:0.85rem;">
                                            ${escapeHtml(employee.first_name || "")} ${escapeHtml(employee.last_name || "")}
                                        </strong>
                                        <span style="display:block;color:#94a3b8;font-size:0.75rem;overflow:hidden;text-overflow:ellipsis;">
                                            ${escapeHtml(employee.email || "")}
                                        </span>
                                    </div>
                                </div>
                            `;
                        }).join("")}
                    </div>
                `;
            }

            let actions = "";

            if (isAdminOrHR()) {
                actions = `
                    <div style="display:flex;gap:8px;margin-top:1.25rem;padding-top:1rem;border-top:1px solid #e2e8f0;">
                        <button onclick="editDepartment(${department.id})" class="btn btn-primary" style="padding:0.45rem 0.8rem;font-size:0.78rem;">
                            <i class="fa-solid fa-pen"></i> Edit
                        </button>
                        <button onclick="deleteDepartment(${department.id})" class="btn btn-danger" style="padding:0.45rem 0.8rem;font-size:0.78rem;">
                            <i class="fa-solid fa-trash"></i> Delete
                        </button>
                    </div>
                `;
            } else {
                actions = `
                    <div style="margin-top:1.25rem;padding-top:1rem;border-top:1px solid #e2e8f0;color:#94a3b8;font-size:0.78rem;">
                        <i class="fa-solid fa-eye"></i> View Only
                    </div>
                `;
            }

            container.innerHTML += `
                <div class="department-card" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:1.25rem;box-shadow:0 4px 14px rgba(15,23,42,0.05);transition:transform 0.2s ease, box-shadow 0.2s ease;">

                    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1.1rem;">
                        <div style="display:flex;align-items:center;gap:12px;">
                            <div class="stat-icon icon-purple" style="width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;">
                                <i class="fa-solid fa-building"></i>
                            </div>
                            <div>
                                <h3 style="margin:0;color:#1e293b;font-size:1rem;">${escapeHtml(department.name)}</h3>
                                <span style="color:#94a3b8;font-size:0.72rem;">Department #${department.id}</span>
                            </div>
                        </div>
                    </div>

                    <div style="color:#64748b;font-size:0.85rem;line-height:1.5;margin-bottom:1.1rem;">
                        ${escapeHtml(department.description || "No description provided.")}
                    </div>

                    <div style="padding:0.85rem;background:#f8fafc;border-radius:10px;margin-bottom:1rem;">
                        <div style="color:#64748b;font-size:0.72rem;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.04em;">
                            Working Days
                        </div>
                        <strong style="color:#1e293b;font-size:0.85rem;">
                            ${formatWorkingDays(department.working_days)}
                        </strong>
                    </div>

                    <div style="padding:0.85rem;background:#f8fafc;border-radius:10px;margin-bottom:1rem;">
                        <div style="color:#64748b;font-size:0.72rem;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.04em;">
                            Shift Timing
                        </div>
                        <strong style="color:#1e293b;font-size:0.85rem;">
                            ${formatDisplayTime(department.start_time)}
                            –
                            ${formatDisplayTime(department.end_time)}
                            <span style="color:#94a3b8;font-weight:400;">
                                (Late after ${formatDisplayTime(department.late_after)})
                            </span>
                        </strong>
                    </div>

                    <div>
                        <div style="display:flex;align-items:center;justify-content:space-between;">
                            <strong style="color:#1e293b;font-size:0.85rem;">Employees</strong>
                            <span style="padding:3px 8px;border-radius:20px;background:#f1f5f9;color:#64748b;font-size:0.72rem;">
                                ${department.employee_count || 0}
                            </span>
                        </div>
                        ${employeeHTML}
                    </div>

                    ${actions}
                </div>
            `;
        });

    } catch (err) {
        console.error("Failed to load departments:", err);
        container.innerHTML = `
            <div style="grid-column:1 / -1;text-align:center;padding:2rem;color:#ef4444;">
                <i class="fa-solid fa-triangle-exclamation" style="font-size:1.8rem;margin-bottom:0.75rem;"></i>
                <p>Failed to load departments: ${escapeHtml(err.message)}</p>
            </div>
        `;
    }
}


// ============================================================
// DELETE DEPARTMENT
// ============================================================

async function deleteDepartment(departmentId) {

    if (!isAdminOrHR()) {
        showToast("You do not have permission to delete departments.", "error");
        return;
    }

    if (!confirm("Are you sure you want to delete this department?")) {
        return;
    }

    try {
        await apiFetch(`/departments/${departmentId}`, "DELETE");
        showToast("Department deleted successfully.", "success");
        await loadDepartments();
        await loadDashboardStats();
    } catch (err) {
        console.error("Delete department error:", err);
        showToast("Failed to delete department: " + err.message, "error");
    }
}


// ============================================================
// EDIT DEPARTMENT (opens a modal)
// ============================================================

async function editDepartment(departmentId) {

    if (!isAdminOrHR()) {
        showToast("Only Admin or HR can edit departments.", "error");
        return;
    }

    try {

        const department = await apiFetch(`/departments/${departmentId}`);

        const modal = document.getElementById("modal-edit-department");

        if (!modal) {
            console.error("modal-edit-department not found in DOM.");
            showToast("Edit department modal is not available on this page yet.", "error");
            return;
        }

        setFieldValue("edit-dept-id", department.id);
        setFieldValue("edit-dept-name", department.name || "");
        setFieldValue("edit-dept-desc", department.description || "");

        setWorkingDaysInForm("edit-dept", department.working_days || []);

        setFieldValue(
            "edit-dept-start-time",
            department.start_time ? department.start_time.substring(0, 5) : "09:00"
        );
        setFieldValue(
            "edit-dept-end-time",
            department.end_time ? department.end_time.substring(0, 5) : "17:00"
        );
        setFieldValue(
            "edit-dept-late-after",
            department.late_after ? department.late_after.substring(0, 5) : "09:15"
        );

        toggleModal("modal-edit-department", true);

    } catch (err) {
        console.error("Edit department error:", err);
        showToast("Failed to load department: " + err.message, "error");
    }
}

function setupEditDepartmentForm() {

    const form = document.getElementById("form-edit-department");
    if (!form) return;

    form.addEventListener("submit", async (e) => {

        e.preventDefault();

        if (!isAdminOrHR()) {
            showToast("Only Admin or HR can edit departments.", "error");
            return;
        }

        try {

            const departmentId = getFieldValue("edit-dept-id");
            if (!departmentId) throw new Error("Missing department id.");

            const name = getFieldValue("edit-dept-name").trim();

            if (!name) {
                showToast("Department name is required.", "error");
                return;
            }

            const workingDays = getWorkingDaysFromForm("edit-dept");

            if (workingDays.length === 0) {
                showToast("Please select at least one working day.", "error");
                return;
            }

            const startTime = getFieldValue("edit-dept-start-time").trim() || "09:00";
            const endTime = getFieldValue("edit-dept-end-time").trim() || "17:00";
            const lateAfter = getFieldValue("edit-dept-late-after").trim() || startTime;

            const payload = {
                name,
                description: getFieldValue("edit-dept-desc").trim(),
                working_days: workingDays,
                start_time: startTime,
                end_time: endTime,
                late_after: lateAfter
            };

            await apiFetch(`/departments/${departmentId}`, "PUT", payload);

            // Clear cached shift info so attendance uses the fresh values
            delete departmentDetailsCache[departmentId];

            showToast("Department updated successfully.", "success");
            toggleModal("modal-edit-department", false);

            await loadDepartments();
            await loadDashboardStats();

        } catch (err) {
            console.error("Edit department error:", err);
            showToast("Failed to update department: " + err.message, "error");
        }
    });
}


// ============================================================
// ADD DEPARTMENT (full modal with shift timing + late threshold)
// ============================================================

function setupAddDepartmentForm() {

    const form = document.getElementById("form-add-department");
    if (!form) return;

    // Default the working-day checkboxes to Mon-Fri
    setWorkingDaysInForm("dept", ["monday", "tuesday", "wednesday", "thursday", "friday"]);

    form.addEventListener("submit", async (e) => {

        e.preventDefault();

        if (!isAdminOrHR()) {
            showToast("Only Admin or HR can add departments.", "error");
            return;
        }

        try {

            const name = getFieldValue("dept-name").trim();
            const description = getFieldValue("dept-desc").trim();

            if (!name) {
                showToast("Department name is required.", "error");
                return;
            }

            const workingDays = getWorkingDaysFromForm("dept");

            if (workingDays.length === 0) {
                showToast("Please select at least one working day.", "error");
                return;
            }

            const startTime = getFieldValue("dept-start-time").trim() || "09:00";
            const endTime = getFieldValue("dept-end-time").trim() || "17:00";
            const lateAfter = getFieldValue("dept-late-after").trim() || startTime;

            const payload = {
                name,
                description,
                working_days: workingDays,
                start_time: startTime,
                end_time: endTime,
                late_after: lateAfter
            };

            await apiFetch("/departments/", "POST", payload);

            showToast("Department added successfully!", "success");
            toggleModal("modal-add-department", false);

            form.reset();
            setWorkingDaysInForm("dept", ["monday", "tuesday", "wednesday", "thursday", "friday"]);
            setFieldValue("dept-start-time", "09:00");
            setFieldValue("dept-end-time", "17:00");
            setFieldValue("dept-late-after", "09:15");

            await loadDepartments();
            await loadDashboardStats();

        } catch (err) {
            console.error("Add department error:", err);
            showToast("Failed to add department: " + err.message, "error");
        }
    });
}


// ============================================================
// DEPARTMENT DETAILS CACHE + TIME HELPERS (for Attendance)
// ============================================================

const departmentDetailsCache = {};

async function getDepartmentDetails(departmentId) {

    if (!departmentId) return null;

    if (departmentDetailsCache[departmentId]) {
        return departmentDetailsCache[departmentId];
    }

    try {
        const dept = await apiFetch(`/departments/${departmentId}`);
        departmentDetailsCache[departmentId] = dept;
        return dept;
    } catch (err) {
        console.error("Failed to fetch department details:", err);
        return null;
    }
}

function timeToMinutes(timeStr) {

    if (!timeStr) return null;

    const parts = String(timeStr).split(":");
    if (parts.length < 2) return null;

    const hours = parseInt(parts[0], 10);
    const minutes = parseInt(parts[1], 10);

    if (Number.isNaN(hours) || Number.isNaN(minutes)) return null;

    return (hours * 60) + minutes;
}

function computeLateInfo(checkInTime, lateAfterTime) {

    const checkInMinutes = timeToMinutes(checkInTime);
    const lateAfterMinutes = timeToMinutes(lateAfterTime);

    if (checkInMinutes === null || lateAfterMinutes === null) {
        return { isLate: false, lateMinutes: 0 };
    }

    if (checkInMinutes > lateAfterMinutes) {
        return { isLate: true, lateMinutes: checkInMinutes - lateAfterMinutes };
    }

    return { isLate: false, lateMinutes: 0 };
}


// ============================================================
// ATTENDANCE
// ============================================================

async function loadAttendance() {

    const tbody = document.getElementById("attendance-table-body");
    if (!tbody) return;

    tbody.innerHTML = `
        <tr><td colspan="5" style="text-align: center;">Loading attendance...</td></tr>
    `;

    try {

        const list = await apiFetch("/attendance/");

        if (!Array.isArray(list) || list.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="5" style="text-align: center;">No attendance records found.</td></tr>
            `;
            return;
        }

        function formatTime(time) {
            if (!time) return "--:--";
            const parts = time.split(":");
            const hours = parseInt(parts[0], 10);
            const minutes = parts[1] || "00";
            const suffix = hours >= 12 ? "PM" : "AM";
            const displayHour = hours % 12 || 12;
            return `${displayHour}:${minutes} ${suffix}`;
        }

        function formatDate(date) {
            if (!date) return "-";
            const d = new Date(date + "T00:00:00");
            return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
        }

        // Late employees are shown as "Present • Late (n min)", never Absent
        function formatStatus(status, isLate = false, lateMinutes = 0) {
            if (!status) return "Unknown";
            let formatted = status.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
            if (isLate) {
                formatted += " • Late";
                if (Number(lateMinutes) > 0) {
                    formatted += ` (${lateMinutes} min)`;
                }
            }
            return formatted;
        }

        function getStatusClass(status, isLate = false) {
            if (isLate) return "badge-late";
            switch (status) {
                case "present": return "badge-present";
                case "absent": return "badge-absent";
                case "leave": return "badge-leave";
                case "half_day": return "badge-half-day";
                default: return "badge-default";
            }
        }

        tbody.innerHTML = "";

        list.forEach((attendance) => {

            const status = attendance.status ? attendance.status.toLowerCase() : "unknown";

            let employeeName = `Emp #${attendance.employee_id}`;

            if (attendance.employee) {
                const firstName = attendance.employee.first_name || "";
                const lastName = attendance.employee.last_name || "";
                const fullName = `${firstName} ${lastName}`.trim();
                if (fullName) employeeName = fullName;
            }

            tbody.innerHTML += `
                <tr>
                    <td>${escapeHtml(employeeName)}</td>
                    <td>${formatDate(attendance.work_date)}</td>
                    <td>${formatTime(attendance.check_in)}</td>
                    <td>${formatTime(attendance.check_out)}</td>
                    <td>
                        <span class="badge ${getStatusClass(status, attendance.is_late)}">
                            ${formatStatus(status, attendance.is_late, attendance.late_minutes)}
                        </span>
                    </td>
                </tr>
            `;
        });

    } catch (err) {
        console.error("Failed to load attendance:", err);
        tbody.innerHTML = `
            <tr><td colspan="5" style="text-align: center; color: red;">
                Failed to load attendance: ${escapeHtml(err.message)}
            </td></tr>
        `;
    }
}


// ============================================================
// EMPLOYEE CHECK-IN / CHECK-OUT
// ============================================================

async function triggerCheckIn() {

    if (!isEmployee()) {
        showToast("Only employees can check in.", "error");
        return;
    }

    try {

        await apiFetch("/attendance/check-in", "POST", null);
        showToast("Checked in successfully!", "success");

        const attendanceView = document.getElementById("view-attendance");
        if (attendanceView && !attendanceView.classList.contains("hidden-view")) {
            await loadAttendance();
        }

    } catch (err) {
        console.error("Check-in error:", err);
        showToast(err.message, "error");
    }
}

async function triggerCheckOut() {

    if (!isEmployee()) {
        showToast("Only employees can check out.", "error");
        return;
    }

    try {

        await apiFetch("/attendance/check-out", "POST", null);
        showToast("Checked out successfully!", "success");

        const attendanceView = document.getElementById("view-attendance");
        if (attendanceView && !attendanceView.classList.contains("hidden-view")) {
            await loadAttendance();
        }

    } catch (err) {
        console.error("Check-out error:", err);
        showToast(err.message, "error");
    }
}


// ============================================================
// TODAY'S DATE (local, not UTC)
// ============================================================

function getLocalDateString() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}


// ============================================================
// OPEN ADD ATTENDANCE MODAL (Admin / HR only)
// ============================================================

async function openAddAttendanceModal() {

    if (!isAdminOrHR()) {
        showToast("Only Admin or HR can add attendance.", "error");
        return;
    }

    const modal = document.getElementById("modal-add-attendance");
    const employeeSelect = document.getElementById("attendance-employee");
    const dateInput = document.getElementById("attendance-date");

    if (!modal || !employeeSelect || !dateInput) {
        console.error("Attendance modal elements not found.");
        return;
    }

    await loadAttendanceEmployees();

    dateInput.value = getLocalDateString();

    const lateInfoEl = document.getElementById("attendance-late-info");
    if (lateInfoEl) lateInfoEl.textContent = "";

    toggleModal("modal-add-attendance", true);
}


// ============================================================
// LOAD EMPLOYEES FOR ATTENDANCE DROPDOWN (Admin / HR only)
// Each option is tagged with the employee's primary department id
// ============================================================

async function loadAttendanceEmployees() {

    const select = document.getElementById("attendance-employee");
    if (!select) return;

    select.innerHTML = `<option value="">Loading employees...</option>`;

    try {

        const employees = await apiFetch("/employees/");

        select.innerHTML = `<option value="">Select Employee</option>`;

        if (!Array.isArray(employees) || employees.length === 0) {
            select.innerHTML = `<option value="">No employees found</option>`;
            return;
        }

        employees.forEach((employee) => {

            const option = document.createElement("option");
            option.value = employee.id;

            const firstName = employee.first_name || employee.fname || "";
            const lastName = employee.last_name || employee.lname || "";
            const fullName = `${firstName} ${lastName}`.trim();

            option.textContent = fullName
                ? `${fullName} (Emp #${employee.id})`
                : `Employee #${employee.id}`;

            const primaryDeptId = Array.isArray(employee.departments) && employee.departments.length > 0
                ? employee.departments[0].id
                : "";

            option.dataset.departmentId = primaryDeptId;

            select.appendChild(option);
        });

    } catch (err) {
        console.error("Failed to load employees:", err);
        select.innerHTML = `<option value="">Failed to load employees</option>`;
        showToast(err.message, "error");
    }
}


// ============================================================
// LIVE DEPARTMENT-TIMING / LATE PREVIEW (Add Attendance modal)
// ============================================================

async function handleAttendanceEmployeeOrTimeChange() {

    const employeeSelect = document.getElementById("attendance-employee");
    const checkInInput = document.getElementById("attendance-check-in");
    const lateInfoEl = document.getElementById("attendance-late-info");

    if (!employeeSelect || !checkInInput) return;

    const selectedOption = employeeSelect.options[employeeSelect.selectedIndex];
    const departmentId = selectedOption ? selectedOption.dataset.departmentId : "";

    if (!departmentId) {
        if (lateInfoEl) {
            lateInfoEl.textContent = "";
            lateInfoEl.classList.remove("is-late");
        }
        return;
    }

    const department = await getDepartmentDetails(departmentId);

    if (!department) {
        if (lateInfoEl) {
            lateInfoEl.textContent = "";
            lateInfoEl.classList.remove("is-late");
        }
        return;
    }

    const startTime = department.start_time ? department.start_time.substring(0, 5) : "--:--";
    const endTime = department.end_time ? department.end_time.substring(0, 5) : "--:--";
    const lateAfter = department.late_after ? department.late_after.substring(0, 5) : null;

    let text = `Department shift: ${startTime}–${endTime}`;
    if (lateAfter) text += ` · Late after ${lateAfter}`;

    let isLatePreview = false;

    if (checkInInput.value && lateAfter) {
        const { isLate, lateMinutes } = computeLateInfo(checkInInput.value, lateAfter);
        if (isLate) {
            isLatePreview = true;
            text += ` · This check-in is ${lateMinutes} min late (will still be marked Present).`;
        }
    }

    if (lateInfoEl) {
        lateInfoEl.textContent = text;
        lateInfoEl.classList.toggle("is-late", isLatePreview);
    }
}


// ============================================================
// ADD / SAVE ATTENDANCE (Admin / HR only)
// Late employees are saved as "present" with is_late attached
// ============================================================

async function submitAttendance(event) {

    event.preventDefault();

    if (!isAdminOrHR()) {
        showToast("Only Admin or HR can add attendance.", "error");
        return;
    }

    const employeeSelect = document.getElementById("attendance-employee");
    const dateInput = document.getElementById("attendance-date");
    const checkInInput = document.getElementById("attendance-check-in");
    const checkOutInput = document.getElementById("attendance-check-out");
    const statusInput = document.getElementById("attendance-status");

    if (!employeeSelect || !dateInput || !checkInInput || !checkOutInput || !statusInput) {
        console.error("Attendance form elements not found.");
        return;
    }

    const employeeId = employeeSelect.value;
    const workDate = dateInput.value;
    let status = statusInput.value;

    if (!employeeId) {
        showToast("Please select an employee.", "error");
        return;
    }

    if (!workDate) {
        showToast("Please select an attendance date.", "error");
        return;
    }

    if (checkInInput.value && checkOutInput.value && checkOutInput.value <= checkInInput.value) {
        showToast("Check-out time must be after check-in time.", "error");
        return;
    }

    if (status === "absent" || status === "leave") {
        checkInInput.value = "";
        checkOutInput.value = "";
    }

    // An old "late" status is treated as Present + Late
    if (status === "late") {
        status = "present";
    }

    let isLate = false;
    let lateMinutes = 0;

    const selectedOption = employeeSelect.options[employeeSelect.selectedIndex];
    const departmentId = selectedOption ? selectedOption.dataset.departmentId : "";

    if (status === "present" && checkInInput.value && departmentId) {
        const department = await getDepartmentDetails(departmentId);
        const lateAfter = department?.late_after ? department.late_after.substring(0, 5) : null;
        if (lateAfter) {
            const lateInfo = computeLateInfo(checkInInput.value, lateAfter);
            isLate = lateInfo.isLate;
            lateMinutes = lateInfo.lateMinutes;
        }
    }

    const attendanceData = {
        employee_id: Number(employeeId),
        work_date: workDate,
        check_in: checkInInput.value || null,
        check_out: checkOutInput.value || null,
        status: status,
        is_late: isLate,
        late_minutes: lateMinutes
    };

    try {

        await apiFetch("/attendance/", "POST", attendanceData);

        showToast(
            isLate
                ? `Attendance added — marked Present (Late by ${lateMinutes} min).`
                : "Attendance added successfully!",
            "success"
        );

        toggleModal("modal-add-attendance", false);

        const form = document.getElementById("form-add-attendance");
        if (form) form.reset();

        handleAttendanceStatusChange();

        const lateInfoEl = document.getElementById("attendance-late-info");
        if (lateInfoEl) {
            lateInfoEl.textContent = "";
            lateInfoEl.classList.remove("is-late");
        }

        await loadAttendance();
        await loadDashboardStats();

        if (isAdminOrHR()) {
            const payrollView = document.getElementById("view-payroll");
            if (payrollView && !payrollView.classList.contains("hidden-view")) {
                await loadLateMarkings();
            }
        }

    } catch (err) {
        console.error("Add attendance error:", err);
        showToast(err.message, "error");
    }
}


// ============================================================
// ATTENDANCE STATUS BEHAVIOR (Absent / Leave = no check-in/out)
// ============================================================

function handleAttendanceStatusChange() {

    const status = document.getElementById("attendance-status");
    const checkIn = document.getElementById("attendance-check-in");
    const checkOut = document.getElementById("attendance-check-out");

    if (!status || !checkIn || !checkOut) return;

    if (status.value === "absent" || status.value === "leave") {
        checkIn.value = "";
        checkOut.value = "";
        checkIn.disabled = true;
        checkOut.disabled = true;
    } else {
        checkIn.disabled = false;
        checkOut.disabled = false;
    }
}


// ============================================================
// ATTENDANCE FORM INITIALIZATION
// ============================================================

document.addEventListener("DOMContentLoaded", function () {

    const attendanceForm = document.getElementById("form-add-attendance");
    if (attendanceForm) {
        attendanceForm.addEventListener("submit", submitAttendance);
    }

    const attendanceStatus = document.getElementById("attendance-status");
    if (attendanceStatus) {
        attendanceStatus.addEventListener("change", handleAttendanceStatusChange);
        handleAttendanceStatusChange();
    }

    const attendanceEmployee = document.getElementById("attendance-employee");
    if (attendanceEmployee) {
        attendanceEmployee.addEventListener("change", handleAttendanceEmployeeOrTimeChange);
    }

    const attendanceCheckIn = document.getElementById("attendance-check-in");
    if (attendanceCheckIn) {
        attendanceCheckIn.addEventListener("change", handleAttendanceEmployeeOrTimeChange);
    }
});


// ============================================================
// NOTIFICATIONS
// ============================================================

let notifications = [];

async function loadNotifications() {
    try {
        const data = await apiFetch("/notifications/");
        notifications = Array.isArray(data) ? data : [];
        renderNotifications();
        updateNotificationBadge();
    } catch (error) {
        console.error("Could not load notifications:", error);
        notifications = [];
        renderNotifications();
        updateNotificationBadge();
    }
}

function updateNotificationBadge() {

    const badge = document.getElementById("notification-badge");
    if (!badge) return;

    const unreadCount = notifications.filter((notification) => !notification.is_read).length;

    if (unreadCount > 0) {
        badge.textContent = unreadCount > 99 ? "99+" : unreadCount;
        badge.classList.remove("hidden");
    } else {
        badge.textContent = "0";
        badge.classList.add("hidden");
    }
}

function renderNotifications() {

    const list = document.getElementById("notification-list");
    if (!list) return;

    if (!notifications.length) {
        list.innerHTML = `<div class="notification-empty">No notifications yet.</div>`;
        return;
    }

    list.innerHTML = notifications.map((notification) => {

        const unreadClass = notification.is_read ? "" : "unread";
        const icon = getNotificationIcon(notification.notification_type);
        const time = formatNotificationTime(notification.created_at);

        return `
            <div class="notification-item ${unreadClass}" onclick="openNotification(${notification.id})">
                <div class="notification-icon"><i class="${icon}"></i></div>
                <div class="notification-content">
                    <div class="notification-item-title">${escapeHtml(notification.title)}</div>
                    <div class="notification-item-message">${escapeHtml(notification.message)}</div>
                    <div class="notification-item-time">${time}</div>
                </div>
            </div>
        `;
    }).join("");
}

function getNotificationIcon(type) {
    switch (type) {
        case "leave_approved": return "fa-solid fa-calendar-check";
        case "leave_rejected": return "fa-solid fa-calendar-xmark";
        case "late_attendance": return "fa-solid fa-clock";
        case "attendance_present": return "fa-solid fa-user-check";
        case "attendance_absent": return "fa-solid fa-user-xmark";
        case "salary_paid": return "fa-solid fa-money-check-dollar";
        case "chat_message": return "fa-solid fa-comment-dots";
        default: return "fa-solid fa-bell";
    }
}

function formatNotificationTime(dateString) {
    if (!dateString) return "";
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString();
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function toggleNotificationPanel() {
    const panel = document.getElementById("notification-panel");
    if (!panel) return;
    panel.classList.toggle("hidden-view");
}

async function openNotification(notificationId) {
    try {
        await apiFetch(`/notifications/${notificationId}/read`, "PATCH");
        const notification = notifications.find((item) => item.id === notificationId);
        if (notification) notification.is_read = true;
        renderNotifications();
        updateNotificationBadge();
    } catch (error) {
        console.error("Could not mark notification as read:", error);
    }
}

async function markAllNotificationsRead() {
    try {
        await apiFetch("/notifications/mark-all-read", "PATCH");
        await loadNotifications();
    } catch (error) {
        console.error("Failed to mark notifications as read:", error);
        alert(error.message || "Unable to mark notifications as read.");
    }
}


// ============================================================
// LEAVE MANAGEMENT
// ============================================================

async function loadLeaves() {

    const tbody = document.getElementById("leave-table-body");
    if (!tbody) return;

    tbody.innerHTML = "";

    try {

        const list = await apiFetch("/leave/");

        if (!Array.isArray(list) || list.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="7" style="text-align:center;">No leave requests found.</td></tr>
            `;
            return;
        }

        list.forEach((leave) => {

            const canApprove = isAdminOrHR();

            let actions = `<span style="color:#94a3b8;font-size:0.75rem;">None</span>`;

            if (canApprove && leave.status === "pending") {
                actions = `
                    <button onclick="updateLeaveStatus(${leave.id}, 'approved')" class="btn btn-success" style="padding:0.25rem 0.5rem;font-size:0.75rem;">
                        Approve
                    </button>
                    <button onclick="updateLeaveStatus(${leave.id}, 'rejected')" class="btn btn-dark" style="padding:0.25rem 0.5rem;font-size:0.75rem;background:#dc2626;">
                        Reject
                    </button>
                `;
            }

            tbody.innerHTML += `
                <tr>
                    <td>Emp #${leave.employee_id}</td>
                    <td>${escapeHtml(leave.leave_type)}</td>
                    <td>${escapeHtml(leave.start_date)}</td>
                    <td>${escapeHtml(leave.end_date)}</td>
                    <td>${escapeHtml(leave.reason || "-")}</td>
                    <td><span class="badge badge-${escapeHtml(leave.status)}">${escapeHtml(leave.status)}</span></td>
                    <td>${actions}</td>
                </tr>
            `;
        });

    } catch (err) {
        console.error("Failed to load leaves:", err);
        tbody.innerHTML = `
            <tr><td colspan="7" style="text-align:center;color:red;">
                Failed to load leaves: ${escapeHtml(err.message)}
            </td></tr>
        `;
    }
}

async function updateLeaveStatus(leaveId, status) {

    if (!isAdminOrHR()) {
        alert("Only Admin or HR can update leave status.");
        return;
    }

    try {
        await apiFetch(`/leave/${leaveId}/status`, "PATCH", { status });
        showToast(`Leave ${status} successfully.`, "success");
        await loadLeaves();
        await loadDashboardStats();
    } catch (err) {
        console.error("Update leave status error:", err);
        showToast("Failed to update leave status: " + err.message, "error");
    }
}

async function loadLeaveEmployees() {

    if (!isAdminOrHR()) return;

    const select = document.getElementById("leave-employee");
    if (!select) return;

    try {

        const employees = await apiFetch("/employees/");

        select.innerHTML = `<option value="">Select Employee</option>`;

        if (!Array.isArray(employees) || employees.length === 0) {
            select.innerHTML = `<option value="">No employees found</option>`;
            return;
        }

        employees.forEach((employee) => {
            select.innerHTML += `
                <option value="${employee.id}">
                    ${escapeHtml(employee.first_name)} ${escapeHtml(employee.last_name)} — Emp #${employee.id}
                </option>
            `;
        });

    } catch (err) {
        console.error("Failed to load leave employees:", err);
        select.innerHTML = `<option value="">Failed to load employees</option>`;
    }
}


// ============================================================
// PAYROLL
// ============================================================

async function loadPayroll() {

    const tbody = document.getElementById("payroll-table-body");
    if (!tbody) return;

    try {

        const payroll = await apiFetch("/payroll/");

        if (!Array.isArray(payroll) || payroll.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="17" class="empty-state">No payroll records found.</td></tr>
            `;
            return;
        }

        tbody.innerHTML = payroll.map((record) => {

            const basicSalary = Number(record.basic_salary || 0);
            const dailySalary = Number(record.daily_salary || 0);
            const presentDays = Number(record.present_days || 0);
            const leaveDays = Number(record.leave_days || 0);
            const absentDays = Number(record.absent_days || 0);
            const payableDays = Number(record.payable_days || 0);
            const attendanceDeduction = Number(record.attendance_deduction || 0);
            const allowances = Number(record.allowances || 0);
            const deductions = Number(record.deductions || 0);
            const netSalary = Number(record.net_salary || 0);
            const workingDays = Number(record.working_days || 0);

            const payType = record.pay_type === "daily" ? "Daily" : "Monthly";
            const paymentMethod = record.payment_method === "cash" ? "Cash" : "Bank";
            const paymentStatus = record.payment_status === "paid" ? "Paid" : "Pending";

            const employeeName = record.employee?.first_name
                ? `${record.employee.first_name} ${record.employee.last_name || ""}`
                : `Employee #${record.employee_id}`;

            const paymentActions = isAdminOrHR()
                ? `
                    <div class="payroll-actions">
                        <button
                            class="btn btn-sm btn-primary"
                            onclick="openEditPayrollPaymentModal(${record.id}, '${record.payment_status || "pending"}', '${record.payment_method || "bank"}')"
                        >
                            Edit Payment
                        </button>
                        ${
                            isAdmin()
                                ? `
                                    <button class="btn btn-danger btn-sm" onclick="deletePayroll(${record.id})">
                                        Delete
                                    </button>
                                `
                                : ""
                        }
                    </div>
                `
                : `<span class="text-muted">View only</span>`;

            return `
                <tr>
                    <td>${escapeHtml(employeeName)}</td>
                    <td>${record.month}/${record.year}</td>
                    <td><span class="badge">${payType}</span></td>
                    <td>${basicSalary.toFixed(2)}</td>
                    <td>${dailySalary.toFixed(2)}</td>
                    <td>${workingDays}</td>
                    <td>${presentDays}</td>
                    <td>${leaveDays}</td>
                    <td>${absentDays}</td>
                    <td>${payableDays}</td>
                    <td>${attendanceDeduction.toFixed(2)}</td>
                    <td>${allowances.toFixed(2)}</td>
                    <td>${deductions.toFixed(2)}</td>
                    <td><strong>${netSalary.toFixed(2)}</strong></td>
                    <td><span class="badge">${paymentMethod}</span></td>
                    <td>
                        <span class="badge ${record.payment_status === "paid" ? "badge-approved" : "badge-pending"}">
                            ${paymentStatus}
                        </span>
                    </td>
                    <td>${paymentActions}</td>
                </tr>
            `;

        }).join("");

    } catch (error) {
        console.error("Load payroll error:", error);
        tbody.innerHTML = `
            <tr><td colspan="17" class="empty-state">Failed to load payroll records.</td></tr>
        `;
    }
}


// ============================================================
// PAYROLL: LATE MARKINGS SECTION
// ============================================================

async function loadLateMarkings() {

    if (!isAdminOrHR()) return;

    const tbody = document.getElementById("late-markings-table-body");
    if (!tbody) return;

    tbody.innerHTML = `
        <tr>
            <td colspan="5" style="text-align:center;">
                Loading late markings...
            </td>
        </tr>
    `;

    try {

        const lateMarkings = await apiFetch("/payroll/late-markings");

        if (!Array.isArray(lateMarkings) || lateMarkings.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center;">
                        No late markings found.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = lateMarkings.map((record) => {

            const employeeName = record.employee
                ? `${record.employee.first_name || ""} ${record.employee.last_name || ""}`.trim()
                : `Employee #${record.employee_id}`;

            const lateCount = Number(record.late_count || 0);
            const totalLateMinutes = Number(record.total_late_minutes || 0);
            const lateDeduction = Number(record.late_deduction || 0);

            const month = record.month || "";
            const year = record.year || "";

            return `
                <tr>
                    <td>${escapeHtml(employeeName)}</td>
                    <td>${month}/${year}</td>
                    <td><strong>${lateCount}</strong></td>
                    <td>${totalLateMinutes} min</td>
                    <td><strong>${lateDeduction.toFixed(2)}</strong></td>
                </tr>
            `;
        }).join("");

    } catch (err) {

        console.error("Failed to load late markings:", err);

        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align:center;color:red;">
                    Failed to load late markings: ${escapeHtml(err.message)}
                </td>
            </tr>
        `;
    }
}


// ============================================================
// LOAD EMPLOYEES INTO PAYROLL DROPDOWN
// ============================================================

async function loadPayrollEmployees() {

    const select = document.getElementById("payroll-employee");
    if (!select || !isAdminOrHR()) return;

    try {

        const employees = await apiFetch("/employees/");

        select.innerHTML = `<option value="">Select Employee</option>`;

        if (!Array.isArray(employees) || employees.length === 0) {
            select.innerHTML = `<option value="">No employees found</option>`;
            return;
        }

        employees.forEach((employee) => {
            const option = document.createElement("option");
            option.value = employee.id;
            option.textContent = `${employee.first_name} ${employee.last_name || ""}`.trim();
            select.appendChild(option);
        });

    } catch (error) {
        console.error("Load payroll employees error:", error);
        select.innerHTML = `<option value="">Unable to load employees</option>`;
    }
}


// ============================================================
// CREATE PAYROLL
// ============================================================

async function createPayroll() {

    if (!isAdminOrHR()) {
        showToast("You do not have permission to create payroll.", "error");
        return;
    }

    const employeeId = document.getElementById("payroll-employee")?.value;
    const month = document.getElementById("payroll-month")?.value;
    const year = document.getElementById("payroll-year")?.value;
    const salary = document.getElementById("payroll-basic")?.value;
    const allowances = document.getElementById("payroll-allowances")?.value || 0;
    const deductions = document.getElementById("payroll-deductions")?.value || 0;
    const payType = document.getElementById("payroll-type")?.value || "monthly";
    const paymentMethod = document.getElementById("payroll-payment-method")?.value || "bank";
    const paymentStatus = document.getElementById("payroll-payment-status")?.value || "pending";

    if (!employeeId) {
        showToast("Please select an employee.", "error");
        return;
    }
    if (!month) {
        showToast("Please select a month.", "error");
        return;
    }
    if (!year) {
        showToast("Please enter a year.", "error");
        return;
    }
    if (!salary || Number(salary) <= 0) {
        showToast("Please enter a valid salary.", "error");
        return;
    }
    if (!["cash", "bank"].includes(paymentMethod)) {
        showToast("Please select a valid payment method.", "error");
        return;
    }
    if (!["pending", "paid"].includes(paymentStatus)) {
        showToast("Please select a valid payment status.", "error");
        return;
    }

    try {

        const result = await apiFetch("/payroll/", "POST", {
            employee_id: Number(employeeId),
            month: Number(month),
            year: Number(year),
            pay_type: payType,
            basic_salary: Number(salary),
            allowances: Number(allowances),
            deductions: Number(deductions),
            payment_method: paymentMethod,
            payment_status: paymentStatus
        });

        showToast(result.message || "Payroll created successfully.", "success");

        const form = document.getElementById("form-add-payroll");
        if (form) form.reset();

        const typeSelect = document.getElementById("payroll-type");
        if (typeSelect) typeSelect.value = "monthly";

        const paymentMethodSelect = document.getElementById("payroll-payment-method");
        if (paymentMethodSelect) paymentMethodSelect.value = "bank";

        const paymentStatusSelect = document.getElementById("payroll-payment-status");
        if (paymentStatusSelect) paymentStatusSelect.value = "pending";

        const workingDaysInput = document.getElementById("payroll-working-days");
        if (workingDaysInput) workingDaysInput.value = "22";

        updateSalaryFields();

        toggleModal("modal-add-payroll", false);

        await loadPayroll();
        await loadLateMarkings();

    } catch (error) {
        console.error("Create payroll error:", error);
        showToast(error.message || "Failed to create payroll.", "error");
    }
}


// ============================================================
// PAYROLL PAYMENT (status + method edited together via modal)
// ============================================================

function openEditPayrollPaymentModal(payrollId, currentStatus, currentMethod) {

    if (!isAdminOrHR()) {
        showToast("You do not have permission to edit payment details.", "error");
        return;
    }

    const modal = document.getElementById("modal-edit-payroll-payment");

    if (!modal) {
        console.error("modal-edit-payroll-payment not found in DOM.");
        showToast("Edit payment modal is not available on this page yet.", "error");
        return;
    }

    setFieldValue("edit-payroll-id", payrollId);
    setFieldValue("edit-payroll-status", currentStatus || "pending");
    setFieldValue("edit-payroll-method", currentMethod || "bank");

    toggleModal("modal-edit-payroll-payment", true);
}

function setupEditPayrollPaymentForm() {

    const form = document.getElementById("form-edit-payroll-payment");
    if (!form) return;

    form.addEventListener("submit", async (e) => {

        e.preventDefault();

        if (!isAdminOrHR()) {
            showToast("You do not have permission to edit payment details.", "error");
            return;
        }

        try {

            const payrollId = getFieldValue("edit-payroll-id");
            if (!payrollId) throw new Error("Missing payroll id.");

            const status = getFieldValue("edit-payroll-status");
            const method = getFieldValue("edit-payroll-method");

            if (!["pending", "paid"].includes(status)) {
                showToast("Please select a valid payment status.", "error");
                return;
            }
            if (!["cash", "bank"].includes(method)) {
                showToast("Please select a valid payment method.", "error");
                return;
            }

            await apiFetch(`/payroll/${payrollId}/payment`, "PATCH", {
                payment_status: status,
                payment_method: method
            });

            showToast("Payment details updated successfully.", "success");
            toggleModal("modal-edit-payroll-payment", false);

            await loadPayroll();

        } catch (err) {
            console.error("Edit payroll payment error:", err);
            showToast("Failed to update payment details: " + err.message, "error");
        }
    });
}


// ============================================================
// DELETE PAYROLL
// ============================================================

async function deletePayroll(payrollId) {

    if (!isAdmin()) {
        showToast("Only admins can delete payroll records.", "error");
        return;
    }

    if (!confirm("Are you sure you want to delete this payroll record?")) {
        return;
    }

    try {
        await apiFetch(`/payroll/${payrollId}`, "DELETE");
        showToast("Payroll deleted successfully.", "success");
        await loadPayroll();
        await loadLateMarkings();
    } catch (error) {
        console.error("Delete payroll error:", error);
        showToast(error.message || "Failed to delete payroll.", "error");
    }
}


// ============================================================
// PAYROLL SALARY CALCULATOR (preview only, backend is authoritative)
// ============================================================

function updateSalaryFields() {

    const type = document.getElementById("payroll-type")?.value || "monthly";
    const salaryInput = document.getElementById("payroll-basic");
    const workingDaysInput = document.getElementById("payroll-working-days");
    const salaryLabel = document.getElementById("payroll-salary-label");
    const dailyPreview = document.getElementById("payroll-daily-preview");
    const monthlyPreview = document.getElementById("payroll-monthly-preview");
    const allowancesInput = document.getElementById("payroll-allowances");
    const deductionsInput = document.getElementById("payroll-deductions");
    const netPreview = document.getElementById("payroll-net-preview");

    if (!salaryInput) return;

    const salary = Number(salaryInput.value) || 0;
    const allowances = Number(allowancesInput?.value) || 0;
    const deductions = Number(deductionsInput?.value) || 0;
    const workingDays = Number(workingDaysInput?.value) || 22;

    let dailySalary = 0;
    let monthlySalary = 0;

    if (type === "daily") {
        dailySalary = salary;
        monthlySalary = dailySalary * workingDays;
        if (salaryLabel) salaryLabel.textContent = "Daily Salary";
        salaryInput.placeholder = "Enter daily salary";
    } else {
        monthlySalary = salary;
        dailySalary = workingDays > 0 ? monthlySalary / workingDays : 0;
        if (salaryLabel) salaryLabel.textContent = "Monthly Salary";
        salaryInput.placeholder = "Enter monthly salary";
    }

    if (dailyPreview) dailyPreview.value = dailySalary.toFixed(2);
    if (monthlyPreview) monthlyPreview.value = monthlySalary.toFixed(2);

    const netSalary = monthlySalary + allowances - deductions;
    if (netPreview) netPreview.value = netSalary.toFixed(2);
}

function setupPayrollCalculator() {

    const salaryFields = [
        "payroll-type", "payroll-basic", "payroll-working-days",
        "payroll-allowances", "payroll-deductions"
    ];

    salaryFields.forEach((id) => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener("input", updateSalaryFields);
            element.addEventListener("change", updateSalaryFields);
        }
    });

    updateSalaryFields();
}


// ============================================================
// ADD EMPLOYEE FORM
// ============================================================

function setupAddEmployeeForm() {

    const addEmployeeForm = document.getElementById("form-add-employee");
    if (!addEmployeeForm) return;

    addEmployeeForm.addEventListener("submit", async (e) => {

        e.preventDefault();

        if (!isAdminOrHR()) {
            alert("Only Admin or HR can add employees.");
            return;
        }

        try {

            const firstName = getFieldValue("emp-fname").trim();
            const lastName = getFieldValue("emp-lname").trim();
            const email = getFieldValue("emp-email").trim().toLowerCase();

            if (!firstName) throw new Error("First name is required.");
            if (!lastName) throw new Error("Last name is required.");
            if (!email) throw new Error("Email is required.");

            const departmentSelect = document.getElementById("emp-dept-select");

            const departmentIds = departmentSelect
                ? Array.from(departmentSelect.selectedOptions)
                    .map((option) => parseInt(option.value, 10))
                    .filter((id) => !isNaN(id))
                : [];

            const basicSalary = getFieldValue("emp-salary").trim();
            const accountNumber = getFieldValue("emp-account").trim();

            const payload = {
                first_name: firstName,
                last_name: lastName,
                email: email,
                job_title: getFieldValue("emp-title").trim(),
                phone: getFieldValue("emp-phone").trim(),
                basic_salary: basicSalary !== "" ? basicSalary : null,
                account_number: accountNumber !== "" ? accountNumber : null,
                department_ids: departmentIds
            };

            await apiFetch("/employees/", "POST", payload);

            showToast("Employee added successfully!", "success");
            toggleModal("modal-add-employee", false);

            addEmployeeForm.reset();

            await loadEmployees();
            await loadDepartments();
            await loadDashboardStats();

        } catch (err) {
            console.error("Add employee error:", err);
            showToast("Failed to add employee: " + err.message, "error");
        }
    });
}


// ============================================================
// ADD LEAVE FORM
// ============================================================

function setupAddLeaveForm() {

    const addLeaveForm = document.getElementById("form-add-leave");
    if (!addLeaveForm) return;

    addLeaveForm.addEventListener("submit", async (e) => {

        e.preventDefault();

        try {

            const payload = {
                leave_type: getFieldValue("leave-type"),
                start_date: getFieldValue("leave-start"),
                end_date: getFieldValue("leave-end"),
                reason: getFieldValue("leave-reason")
            };

            if (isAdminOrHR()) {

                const employeeId = getFieldValue("leave-employee");

                if (!employeeId) {
                    alert("Please select an employee.");
                    return;
                }

                payload.employee_id = parseInt(employeeId, 10);
            }

            await apiFetch("/leave/", "POST", payload);

            showToast("Leave request submitted successfully!", "success");
            toggleModal("modal-add-leave", false);

            addLeaveForm.reset();

            await loadLeaves();
            await loadDashboardStats();

        } catch (err) {
            console.error("Leave submission error:", err);
            showToast("Failed to submit leave request: " + err.message, "error");
        }
    });
}


// ============================================================
// ADD PAYROLL FORM
// ============================================================

function setupAddPayrollForm() {

    const addPayrollForm = document.getElementById("form-add-payroll");
    if (!addPayrollForm) return;

    addPayrollForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        await createPayroll();
    });
}


// ============================================================
// AUTO REFRESH NOTIFICATIONS
// ============================================================

setInterval(() => {
    if (getAuthToken() && currentUser) {
        loadNotifications();
    }
}, 5000);


// ============================================================
// DOM READY
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    setupRegisterForm();
    setupLoginForm();

    setupAddEmployeeForm();
    setupEditEmployeeForm();

    setupAddDepartmentForm();
    setupEditDepartmentForm();

    setupAddLeaveForm();

    setupAddPayrollForm();
    setupEditPayrollPaymentForm();
    setupPayrollCalculator();

    if (getAuthToken()) {
        initDashboard();
    }
});