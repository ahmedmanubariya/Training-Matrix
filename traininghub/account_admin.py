from flask import Blueprint, abort, flash, redirect, request, url_for
from werkzeug.security import generate_password_hash

from .db import get_db
from .routes import audit, manager_department, role_required, user

bp = Blueprint('account_admin', __name__, url_prefix='/users')


def can_manage(target):
    current = user()
    if current['access_role'] == 'admin':
        return True
    return (
        current['access_role'] == 'manager'
        and target['access_role'] == 'staff'
        and target['employee_department'] == manager_department(current)
    )


@bp.post('/<int:user_id>/reset-password')
@role_required('manager', 'admin')
def reset_password(user_id):
    temp = request.form.get('temp_password', '')
    if len(temp) < 12:
        flash('Temporary password must be at least 12 characters.')
        return redirect(url_for('main.users'))

    db = get_db()
    target = db.execute(
        '''SELECT u.*,e.department employee_department
           FROM users u LEFT JOIN employees e ON e.id=u.employee_id
           WHERE u.id=?''', (user_id,)
    ).fetchone()
    if not target:
        abort(404)
    if not can_manage(target):
        abort(403)

    db.execute(
        'UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?',
        (generate_password_hash(temp), user_id),
    )
    db.commit()
    audit('RESET_PASSWORD', 'user', user_id, 'Temporary password issued')
    flash('Temporary password reset. The user must change it at next login.')
    return redirect(url_for('main.users'))


@bp.post('/<int:user_id>/toggle')
@role_required('manager', 'admin')
def toggle_user(user_id):
    db = get_db()
    target = db.execute(
        '''SELECT u.*,e.department employee_department
           FROM users u LEFT JOIN employees e ON e.id=u.employee_id
           WHERE u.id=?''', (user_id,)
    ).fetchone()
    if not target:
        abort(404)
    if not can_manage(target):
        abort(403)
    if target['id'] == user()['id']:
        flash('You cannot disable your own account.')
        return redirect(url_for('main.users'))

    new_state = 0 if target['active'] else 1
    db.execute('UPDATE users SET active=? WHERE id=?', (new_state, user_id))
    db.commit()
    audit('ENABLE_USER' if new_state else 'DISABLE_USER', 'user', user_id,
          'Account enabled' if new_state else 'Account disabled')
    flash('Account enabled.' if new_state else 'Account disabled.')
    return redirect(url_for('main.users'))
