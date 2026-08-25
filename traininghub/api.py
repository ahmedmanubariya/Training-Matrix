from functools import wraps

from flask import Blueprint, abort, jsonify, request, session
from werkzeug.security import check_password_hash

from .db import get_db
from .experience import library_rows, personal_metrics
from .routes import compliance, manager_department, user

bp = Blueprint('api', __name__, url_prefix='/api')


def json_login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        current = user()
        if not current:
            return jsonify({'error': 'unauthenticated'}), 401
        return fn(*args, **kwargs)
    return wrapped


def effective_role(current):
    return (current['permission_role'] or current['access_role']) if current else None


def user_payload(current):
    return {
        'id': current['id'],
        'username': current['username'],
        'employeeId': current['employee_id'],
        'name': current['employee_name'] or current['username'],
        'department': current['employee_department'] or current['department'],
        'jobRole': current['employee_job_role'],
        'role': effective_role(current),
    }


@bp.get('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'traininghub-api'})


@bp.post('/auth/login')
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    account = get_db().execute(
        'SELECT * FROM users WHERE username=? AND active=1', (username,)
    ).fetchone()
    if not account or not check_password_hash(account['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    session.clear()
    session['user_id'] = account['id']
    db = get_db()
    db.execute('UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?', (account['id'],))
    db.commit()
    return jsonify({'user': user_payload(user()), 'mustChangePassword': bool(account['must_change_password'])})


@bp.post('/auth/logout')
def logout():
    session.clear()
    return jsonify({'ok': True})


@bp.get('/auth/me')
@json_login_required
def me():
    return jsonify({'user': user_payload(user())})


@bp.get('/overview')
@json_login_required
def overview():
    current = user()
    metrics = personal_metrics(current['employee_id']) if current['employee_id'] else {
        'total': 0, 'completed': 0, 'outstanding': 0, 'overdue': 0, 'percentage': 100.0
    }
    return jsonify({'user': user_payload(current), 'metrics': metrics, 'threshold': 80})


@bp.get('/documents')
@json_login_required
def documents():
    current = user()
    query = request.args.get('q', '').strip()
    rows = library_rows(current['employee_id'], query)
    return jsonify({'documents': [
        {
            'id': r['sop_id'],
            'reference': r['reference'],
            'title': r['title'],
            'category': r['category'],
            'revision': r['version_revision'] or r['current_revision'],
            'status': r['status'],
            'assigned': bool(r['assignment_id']),
            'read': bool(r['has_read']),
            'signedAt': r['signed_at'],
            'expiryDate': r['expiry_date'],
        } for r in rows
    ]})


@bp.get('/documents/<int:sop_id>')
@json_login_required
def document(sop_id):
    current = user()
    db = get_db()
    sop = db.execute('SELECT * FROM sops WHERE id=? AND active=1', (sop_id,)).fetchone()
    if not sop:
        abort(404)
    version = db.execute(
        "SELECT * FROM sop_versions WHERE sop_id=? AND status='ACTIVE' ORDER BY uploaded_at DESC LIMIT 1",
        (sop_id,),
    ).fetchone()
    assigned = False
    if current['employee_id']:
        assigned = bool(db.execute(
            'SELECT 1 FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1',
            (current['employee_id'], sop_id),
        ).fetchone())
    signatures = []
    if current['employee_id']:
        signatures = db.execute(
            '''SELECT sig.signed_at,sig.revision,sig.signed_name,v.original_name
               FROM signatures sig JOIN sop_versions v ON v.id=sig.version_id
               WHERE sig.employee_id=? AND sig.sop_id=? ORDER BY sig.signed_at DESC''',
            (current['employee_id'], sop_id),
        ).fetchall()
    return jsonify({
        'document': {
            'id': sop['id'], 'reference': sop['reference'], 'title': sop['title'],
            'category': sop['category'], 'revision': version['revision'] if version else sop['current_revision'],
            'assigned': assigned,
            'versionId': version['id'] if version else None,
            'fileName': version['original_name'] if version else None,
            'materialUrl': f"/controlled-documents/material/{version['id']}" if version else None,
        },
        'signatures': [dict(row) for row in signatures],
    })


@bp.post('/documents/<int:sop_id>/acknowledge')
@json_login_required
def acknowledge(sop_id):
    current = user()
    if not current['employee_id']:
        return jsonify({'error': 'This account is not linked to a staff record'}), 403
    data = request.get_json(silent=True) or {}
    version_id = data.get('versionId')
    signed_name = str(data.get('signedName', '')).strip()
    password = str(data.get('password', ''))
    db = get_db()
    assignment = db.execute(
        'SELECT 1 FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1',
        (current['employee_id'], sop_id),
    ).fetchone()
    if not assignment:
        return jsonify({'error': 'Document is not assigned as training'}), 403
    version = db.execute(
        "SELECT * FROM sop_versions WHERE id=? AND sop_id=? AND status='ACTIVE'",
        (version_id, sop_id),
    ).fetchone()
    read = db.execute(
        'SELECT 1 FROM material_reads WHERE user_id=? AND version_id=?',
        (current['id'], version_id),
    ).fetchone()
    if not version or not read:
        return jsonify({'error': 'Open and read the current document before acknowledging it'}), 400
    if signed_name.casefold() != str(current['employee_name'] or '').strip().casefold():
        return jsonify({'error': 'Signature name must match the staff record'}), 400
    if not check_password_hash(current['password_hash'], password):
        return jsonify({'error': 'Password confirmation failed'}), 400

    from datetime import date
    statement = 'I confirm that I have read and understood this controlled document.'
    db.execute(
        '''INSERT INTO signatures(user_id,employee_id,sop_id,version_id,signed_name,statement,revision,ip_address)
           VALUES(?,?,?,?,?,?,?,?)''',
        (current['id'], current['employee_id'], sop_id, version_id, signed_name, statement,
         version['revision'], request.remote_addr),
    )
    db.execute(
        '''INSERT INTO training_records(employee_id,sop_id,status,completion_date,revision_completed)
           VALUES(?,?,'COMPLIANT',?,?)
           ON CONFLICT(employee_id,sop_id) DO UPDATE SET status='COMPLIANT',completion_date=excluded.completion_date,
             revision_completed=excluded.revision_completed,updated_at=CURRENT_TIMESTAMP''',
        (current['employee_id'], sop_id, date.today().isoformat(), version['revision']),
    )
    db.commit()
    return jsonify({'ok': True})


@bp.get('/team')
@json_login_required
def team():
    current = user()
    role = effective_role(current)
    if role not in ('manager', 'qa', 'admin'):
        return jsonify({'error': 'forbidden'}), 403
    db = get_db()
    if role in ('qa', 'admin'):
        employees = db.execute('SELECT * FROM employees WHERE active=1 ORDER BY department,name').fetchall()
    else:
        employees = db.execute(
            'SELECT * FROM employees WHERE active=1 AND department=? ORDER BY name',
            (manager_department(current),),
        ).fetchall()
    data = []
    for emp in employees:
        c = compliance(emp['id'])
        data.append({
            'id': emp['id'], 'name': emp['name'], 'department': emp['department'],
            'jobRole': emp['job_role'], **c,
        })
    return jsonify({'team': data})


@bp.get('/audit')
@json_login_required
def audit_log():
    current = user()
    if effective_role(current) not in ('qa', 'admin'):
        return jsonify({'error': 'forbidden'}), 403
    rows = get_db().execute(
        '''SELECT a.created_at,a.action,a.entity_type,a.entity_id,a.details,a.ip_address,u.username
           FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
           ORDER BY a.id DESC LIMIT 500'''
    ).fetchall()
    return jsonify({'events': [dict(r) for r in rows]})
