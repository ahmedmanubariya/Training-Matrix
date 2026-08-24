from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .routes import (
    assignment_rows, audit, can_manage_employee, compliance, ensure_role_assignments,
    manager_department, role_required, user,
)

bp = Blueprint('staff_admin', __name__, url_prefix='/staff')


@bp.route('/<int:employee_id>')
@role_required('manager', 'admin')
def detail(employee_id):
    current = user()
    db = get_db()
    employee = db.execute('SELECT * FROM employees WHERE id=?', (employee_id,)).fetchone()
    if not employee:
        abort(404)
    if not can_manage_employee(current, employee):
        abort(403)
    return render_template(
        'staff_detail.html',
        employee=employee,
        rows=assignment_rows(employee_id),
        comp=compliance(employee_id),
    )


@bp.post('/<int:employee_id>/edit')
@role_required('manager', 'admin')
def edit(employee_id):
    current = user()
    db = get_db()
    employee = db.execute('SELECT * FROM employees WHERE id=?', (employee_id,)).fetchone()
    if not employee:
        abort(404)
    if not can_manage_employee(current, employee):
        abort(403)

    department = request.form.get('department', '').strip() or 'Unassigned'
    if current['access_role'] == 'manager':
        department = manager_department(current)

    name = request.form.get('name', '').strip()
    if not name:
        flash('Staff name is required.')
        return redirect(url_for('staff_admin.detail', employee_id=employee_id))

    db.execute(
        '''UPDATE employees SET employee_number=?,name=?,email=?,site=?,department=?,job_role=?,
                  updated_at=CURRENT_TIMESTAMP WHERE id=?''',
        (
            request.form.get('employee_number', '').strip(), name,
            request.form.get('email', '').strip(), request.form.get('site', '').strip(),
            department, request.form.get('job_role', '').strip(), employee_id,
        ),
    )
    db.commit()
    ensure_role_assignments(employee_id)
    audit('EDIT_EMPLOYEE', 'employee', employee_id, 'Staff record updated')
    flash('Staff record updated.')
    return redirect(url_for('staff_admin.detail', employee_id=employee_id))


@bp.post('/<int:employee_id>/deactivate')
@role_required('manager', 'admin')
def deactivate(employee_id):
    current = user()
    db = get_db()
    employee = db.execute('SELECT * FROM employees WHERE id=?', (employee_id,)).fetchone()
    if not employee:
        abort(404)
    if not can_manage_employee(current, employee):
        abort(403)

    db.execute('UPDATE employees SET active=0,updated_at=CURRENT_TIMESTAMP WHERE id=?', (employee_id,))
    db.execute('UPDATE employee_assignments SET active=0 WHERE employee_id=?', (employee_id,))
    db.execute('UPDATE users SET active=0 WHERE employee_id=?', (employee_id,))
    db.commit()
    audit('DEACTIVATE_EMPLOYEE', 'employee', employee_id, 'Staff member and linked login deactivated')
    flash('Staff member deactivated. Training history remains preserved.')
    return redirect(url_for('main.staff'))
