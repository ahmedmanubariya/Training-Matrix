from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .db import get_db
from .document_sync import sync_approved_folder
from .routes import audit, login_required, user
from .experience import effective_role

bp = Blueprint('system_admin', __name__, url_prefix='/system')


def require_qa_admin():
    u = user()
    if not u:
        abort(401)
    if effective_role(u) not in ('qa', 'admin'):
        abort(403)
    return u


@bp.route('/')
@login_required
def index():
    u = require_qa_admin()
    db = get_db()
    source_count = db.execute('SELECT COUNT(*) c FROM document_sources').fetchone()['c']
    users = db.execute(
        '''SELECT u.*,e.name employee_name,e.department employee_department,
                  COALESCE(u.permission_role,u.access_role) effective_role
           FROM users u LEFT JOIN employees e ON e.id=u.employee_id ORDER BY u.username'''
    ).fetchall()
    return render_template('system.html', root=current_app.config.get('APPROVED_DOCS_ROOT',''),
                           source_count=source_count, users=users, role=effective_role(u))


@bp.post('/sync')
@login_required
def sync_now():
    u = require_qa_admin()
    result = sync_approved_folder(actor_user_id=u['id'])
    audit('SYNC_APPROVED_DOCUMENTS', 'system', None, str(result))
    if not result.get('configured'):
        flash('Approved document folder is not configured or cannot be reached from this server.')
    else:
        flash(f"Sync complete: {result['created']} new, {result['updated']} updated, {result['unchanged']} unchanged, {len(result['errors'])} errors.")
    return redirect(url_for('system_admin.index'))


@bp.post('/users/<int:user_id>/permission')
@login_required
def set_permission(user_id):
    current = require_qa_admin()
    requested = request.form.get('permission_role', 'user')
    if requested not in ('user', 'manager', 'qa', 'admin'):
        abort(400)
    if effective_role(current) == 'qa' and requested == 'admin':
        abort(403)
    db = get_db()
    target = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not target:
        abort(404)
    # Keep legacy access_role compatible with the existing application routes.
    legacy = {'user': 'staff', 'manager': 'manager', 'qa': 'admin', 'admin': 'admin'}[requested]
    db.execute('UPDATE users SET access_role=?,permission_role=? WHERE id=?', (legacy, requested, user_id))
    db.commit()
    audit('CHANGE_PERMISSION_ROLE', 'user', user_id, f'permission_role={requested}')
    flash('User permission updated.')
    return redirect(url_for('system_admin.index'))
