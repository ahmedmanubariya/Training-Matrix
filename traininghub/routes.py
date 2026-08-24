import os
import uuid
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    send_from_directory, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .db import get_db

bp = Blueprint('main', __name__)
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'pptx'}
SIGNATURE_STATEMENT = (
    'I confirm that I have read and understood the assigned training material '
    'and that this electronic acknowledgement represents my completion of this training.'
)


def user():
    uid = session.get('user_id')
    if not uid:
        return None
    return get_db().execute(
        '''SELECT u.*, e.name employee_name, e.department employee_department,
                  e.job_role employee_job_role
           FROM users u LEFT JOIN employees e ON e.id=u.employee_id
           WHERE u.id=? AND u.active=1''', (uid,)
    ).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not user():
            return redirect(url_for('main.login'))
        return fn(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            u = user()
            if not u:
                return redirect(url_for('main.login'))
            if u['access_role'] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return deco


def audit(action, entity_type, entity_id=None, details=''):
    db = get_db()
    db.execute(
        '''INSERT INTO audit_log(user_id,action,entity_type,entity_id,details,ip_address)
           VALUES(?,?,?,?,?,?)''',
        (session.get('user_id'), action, entity_type, entity_id, details, request.remote_addr),
    )
    db.commit()


def manager_department(u):
    return u['department'] or u['employee_department']


def can_manage_employee(u, emp):
    return u['access_role'] == 'admin' or (
        u['access_role'] == 'manager' and manager_department(u) == emp['department']
    )


def ensure_role_assignments(employee_id):
    db = get_db()
    emp = db.execute('SELECT * FROM employees WHERE id=? AND active=1', (employee_id,)).fetchone()
    if not emp:
        return
    reqs = db.execute(
        '''SELECT rr.sop_id FROM role_requirements rr
           JOIN sops s ON s.id=rr.sop_id
           WHERE rr.job_role=? AND rr.required=1 AND s.active=1''',
        (emp['job_role'] or '',),
    ).fetchall()
    for req in reqs:
        db.execute(
            '''INSERT INTO employee_assignments(employee_id,sop_id,source,active)
               VALUES(?,?,'ROLE',1)
               ON CONFLICT(employee_id,sop_id) DO UPDATE SET active=1''',
            (employee_id, req['sop_id']),
        )
        db.execute(
            '''INSERT INTO training_records(employee_id,sop_id,status)
               VALUES(?,?,'OUTSTANDING') ON CONFLICT(employee_id,sop_id) DO NOTHING''',
            (employee_id, req['sop_id']),
        )
    db.commit()


def assignment_rows(employee_id):
    ensure_role_assignments(employee_id)
    return get_db().execute(
        '''SELECT ea.id assignment_id, ea.due_date, ea.source,
                  s.id sop_id, s.reference, s.title, s.current_revision, s.validity_months,
                  COALESCE(tr.status,'OUTSTANDING') status, tr.completion_date,
                  tr.expiry_date, tr.revision_completed,
                  v.id version_id, v.original_name, v.revision version_revision,
                  CASE WHEN mr.id IS NULL THEN 0 ELSE 1 END has_read,
                  (SELECT MAX(sig.signed_at) FROM signatures sig
                    WHERE sig.employee_id=ea.employee_id AND sig.sop_id=s.id) signed_at
           FROM employee_assignments ea
           JOIN sops s ON s.id=ea.sop_id AND s.active=1
           LEFT JOIN training_records tr ON tr.employee_id=ea.employee_id AND tr.sop_id=s.id
           LEFT JOIN sop_versions v ON v.sop_id=s.id AND v.status='ACTIVE'
           LEFT JOIN users u ON u.employee_id=ea.employee_id AND u.active=1
           LEFT JOIN material_reads mr ON mr.user_id=u.id AND mr.version_id=v.id
           WHERE ea.employee_id=? AND ea.active=1
           GROUP BY ea.id
           ORDER BY s.reference,s.title''', (employee_id,)
    ).fetchall()


def compliance(employee_id):
    rows = assignment_rows(employee_id)
    counted = [r for r in rows if r['status'] != 'NOT_APPLICABLE']
    total = len(counted)
    trained = sum(1 for r in counted if r['status'] in ('COMPLIANT', 'DUE_SOON'))
    outstanding = total - trained
    return {
        'total': total,
        'trained': trained,
        'outstanding': outstanding,
        'percentage': round(trained * 100 / total, 1) if total else 100.0,
    }


def expiry_date(months):
    return (date.today() + timedelta(days=int(months) * 30)).isoformat() if months else None


@bp.app_context_processor
def context():
    return {'me': user(), 'signature_statement': SIGNATURE_STATEMENT}


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        u = get_db().execute('SELECT * FROM users WHERE username=? AND active=1', (username,)).fetchone()
        if u and check_password_hash(u['password_hash'], password):
            session.clear()
            session['user_id'] = u['id']
            db = get_db()
            db.execute('UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?', (u['id'],))
            db.commit()
            audit('LOGIN', 'user', u['id'], 'Successful login')
            return redirect(url_for('main.change_password') if u['must_change_password'] else url_for('main.home'))
        flash('Invalid username or password.')
    return render_template('login.html')


@bp.route('/logout')
def logout():
    if session.get('user_id'):
        audit('LOGOUT', 'user', session['user_id'], 'Logout')
    session.clear()
    return redirect(url_for('main.login'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    u = user()
    if request.method == 'POST':
        old = request.form.get('old_password', '')
        new = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not check_password_hash(u['password_hash'], old):
            flash('Current password is incorrect.')
        elif len(new) < 12 or new != confirm:
            flash('New password must match and be at least 12 characters.')
        else:
            db = get_db()
            db.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?',
                       (generate_password_hash(new), u['id']))
            db.commit()
            audit('CHANGE_PASSWORD', 'user', u['id'], 'Password changed')
            return redirect(url_for('main.home'))
    return render_template('change_password.html')


@bp.route('/')
@login_required
def home():
    u = user()
    return redirect(url_for('main.my_training') if u['access_role'] == 'staff' else url_for('main.dashboard'))


@bp.route('/my-training')
@login_required
def my_training():
    u = user()
    if not u['employee_id']:
        return render_template('my_training.html', employee=None, rows=[], comp=None)
    emp = get_db().execute('SELECT * FROM employees WHERE id=?', (u['employee_id'],)).fetchone()
    return render_template('my_training.html', employee=emp,
                           rows=assignment_rows(emp['id']), comp=compliance(emp['id']))


@bp.route('/training/<int:sop_id>')
@login_required
def training_detail(sop_id):
    u = user()
    if u['access_role'] != 'staff' or not u['employee_id']:
        abort(403)
    db = get_db()
    assignment = db.execute(
        '''SELECT ea.*,s.reference,s.title,s.current_revision,s.validity_months,
                  COALESCE(tr.status,'OUTSTANDING') status
           FROM employee_assignments ea JOIN sops s ON s.id=ea.sop_id
           LEFT JOIN training_records tr ON tr.employee_id=ea.employee_id AND tr.sop_id=s.id
           WHERE ea.employee_id=? AND ea.sop_id=? AND ea.active=1 AND s.active=1''',
        (u['employee_id'], sop_id),
    ).fetchone()
    if not assignment:
        abort(404)
    versions = db.execute(
        '''SELECT v.*,CASE WHEN mr.id IS NULL THEN 0 ELSE 1 END has_read
           FROM sop_versions v LEFT JOIN material_reads mr ON mr.version_id=v.id AND mr.user_id=?
           WHERE v.sop_id=? AND v.status='ACTIVE' ORDER BY v.uploaded_at DESC''',
        (u['id'], sop_id),
    ).fetchall()
    signatures = db.execute(
        '''SELECT sig.*,v.original_name FROM signatures sig
           JOIN sop_versions v ON v.id=sig.version_id
           WHERE sig.employee_id=? AND sig.sop_id=? ORDER BY sig.signed_at DESC''',
        (u['employee_id'], sop_id),
    ).fetchall()
    return render_template('training_detail.html', assignment=assignment,
                           versions=versions, signatures=signatures)


@bp.route('/materials/<int:version_id>')
@login_required
def material(version_id):
    u = user()
    db = get_db()
    v = db.execute(
        '''SELECT v.*,s.id sop_id FROM sop_versions v JOIN sops s ON s.id=v.sop_id
           WHERE v.id=? AND v.status='ACTIVE' AND s.active=1''', (version_id,)
    ).fetchone()
    if not v:
        abort(404)
    if u['access_role'] == 'staff':
        assigned = db.execute(
            'SELECT 1 FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1',
            (u['employee_id'], v['sop_id']),
        ).fetchone()
        if not assigned:
            abort(403)
        db.execute(
            '''INSERT INTO material_reads(user_id,employee_id,version_id) VALUES(?,?,?)
               ON CONFLICT(user_id,version_id) DO UPDATE SET last_opened_at=CURRENT_TIMESTAMP''',
            (u['id'], u['employee_id'], version_id),
        )
        db.commit()
    audit('OPEN_MATERIAL', 'sop_version', version_id, 'Material opened')
    upload_dir = Path(current_app.instance_path) / current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, v['stored_name'], as_attachment=False,
                               download_name=v['original_name'])


@bp.post('/training/<int:sop_id>/sign')
@login_required
def sign_training(sop_id):
    u = user()
    if u['access_role'] != 'staff' or not u['employee_id']:
        abort(403)
    signed_name = request.form.get('signed_name', '').strip()
    password = request.form.get('password', '')
    version_id = request.form.get('version_id', type=int)
    accepted = request.form.get('accept') == 'yes'
    if not accepted or signed_name.casefold() != (u['employee_name'] or '').strip().casefold():
        flash('Your typed name must match your staff record and you must accept the statement.')
        return redirect(url_for('main.training_detail', sop_id=sop_id))
    if not check_password_hash(u['password_hash'], password):
        flash('Password confirmation failed.')
        return redirect(url_for('main.training_detail', sop_id=sop_id))
    db = get_db()
    v = db.execute(
        '''SELECT v.*,s.validity_months FROM sop_versions v JOIN sops s ON s.id=v.sop_id
           WHERE v.id=? AND v.sop_id=? AND v.status='ACTIVE' AND s.active=1''',
        (version_id, sop_id),
    ).fetchone()
    read = db.execute('SELECT 1 FROM material_reads WHERE user_id=? AND version_id=?',
                      (u['id'], version_id)).fetchone()
    if not v or not read:
        flash('Open the current material before electronically signing it.')
        return redirect(url_for('main.training_detail', sop_id=sop_id))
    exp = expiry_date(v['validity_months'])
    db.execute(
        '''INSERT INTO signatures(user_id,employee_id,sop_id,version_id,signed_name,statement,revision,ip_address)
           VALUES(?,?,?,?,?,?,?,?)''',
        (u['id'], u['employee_id'], sop_id, version_id, signed_name,
         SIGNATURE_STATEMENT, v['revision'], request.remote_addr),
    )
    db.execute(
        '''INSERT INTO training_records(employee_id,sop_id,status,completion_date,expiry_date,revision_completed)
           VALUES(?,?,'COMPLIANT',?,?,?)
           ON CONFLICT(employee_id,sop_id) DO UPDATE SET status='COMPLIANT',
             completion_date=excluded.completion_date, expiry_date=excluded.expiry_date,
             revision_completed=excluded.revision_completed, updated_at=CURRENT_TIMESTAMP''',
        (u['employee_id'], sop_id, date.today().isoformat(), exp, v['revision']),
    )
    db.commit()
    audit('ELECTRONIC_SIGNATURE', 'sop', sop_id, f"revision={v['revision']}")
    flash('Training completed and electronically signed.')
    return redirect(url_for('main.my_training'))


@bp.route('/dashboard')
@role_required('manager', 'admin')
def dashboard():
    u = user()
    db = get_db()
    if u['access_role'] == 'admin':
        employees = db.execute('SELECT * FROM employees WHERE active=1 ORDER BY department,name').fetchall()
    else:
        employees = db.execute('SELECT * FROM employees WHERE active=1 AND department=? ORDER BY name',
                               (manager_department(u),)).fetchall()
    team = []
    for emp in employees:
        team.append({**dict(emp), **compliance(emp['id'])})
    average = round(sum(x['percentage'] for x in team) / len(team), 1) if team else 100.0
    return render_template('dashboard.html', team=team, average=average)


@bp.route('/sops', methods=['GET', 'POST'])
@role_required('manager', 'admin')
def sops():
    db = get_db()
    if request.method == 'POST':
        reference = request.form.get('reference', '').strip()
        title = request.form.get('title', '').strip()
        if not reference or not title:
            flash('Reference and title are required.')
        else:
            try:
                cur = db.execute(
                    '''INSERT INTO sops(reference,title,category,sop_type,owner,current_revision,validity_months)
                       VALUES(?,?,?,?,?,?,?)''',
                    (reference, title, request.form.get('category', '').strip(),
                     request.form.get('sop_type', '').strip(), request.form.get('owner', '').strip(),
                     request.form.get('revision', '').strip(), request.form.get('validity_months', type=int)),
                )
                db.commit()
                audit('CREATE_SOP', 'sop', cur.lastrowid, f'{reference} - {title}')
                flash('SOP created.')
                return redirect(url_for('main.sop_detail', sop_id=cur.lastrowid))
            except Exception:
                flash('That SOP already exists or the data was invalid.')
    show = request.args.get('show', 'active')
    active = 0 if show == 'retired' else 1
    rows = db.execute(
        '''SELECT s.*,COUNT(DISTINCT rr.id) role_count,COUNT(DISTINCT v.id) version_count
           FROM sops s LEFT JOIN role_requirements rr ON rr.sop_id=s.id
           LEFT JOIN sop_versions v ON v.sop_id=s.id WHERE s.active=?
           GROUP BY s.id ORDER BY s.reference,s.title''', (active,)
    ).fetchall()
    return render_template('sops.html', sops=rows, show=show)


@bp.route('/sops/<int:sop_id>')
@role_required('manager', 'admin')
def sop_detail(sop_id):
    db = get_db()
    sop = db.execute('SELECT * FROM sops WHERE id=?', (sop_id,)).fetchone()
    if not sop:
        abort(404)
    versions = db.execute('SELECT * FROM sop_versions WHERE sop_id=? ORDER BY uploaded_at DESC',
                          (sop_id,)).fetchall()
    reqs = db.execute('SELECT * FROM role_requirements WHERE sop_id=? ORDER BY job_role',
                      (sop_id,)).fetchall()
    assigned = db.execute(
        '''SELECT e.name,e.department,e.job_role,COALESCE(tr.status,'OUTSTANDING') status,
                  tr.completion_date,tr.revision_completed
           FROM employee_assignments ea JOIN employees e ON e.id=ea.employee_id
           LEFT JOIN training_records tr ON tr.employee_id=e.id AND tr.sop_id=ea.sop_id
           WHERE ea.sop_id=? AND ea.active=1 ORDER BY e.department,e.name''', (sop_id,)
    ).fetchall()
    roles = [r['job_role'] for r in db.execute(
        "SELECT DISTINCT job_role FROM employees WHERE job_role IS NOT NULL AND job_role<>'' ORDER BY job_role"
    )]
    return render_template('sop_detail.html', sop=sop, versions=versions,
                           reqs=reqs, assigned=assigned, roles=roles)


@bp.post('/sops/<int:sop_id>/upload')
@role_required('manager', 'admin')
def sop_upload(sop_id):
    f = request.files.get('file')
    revision = request.form.get('revision', '').strip()
    if not f or not f.filename or not revision:
        flash('A revision and file are required.')
        return redirect(url_for('main.sop_detail', sop_id=sop_id))
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        flash('Allowed formats: PDF, TXT, DOCX and PPTX.')
        return redirect(url_for('main.sop_detail', sop_id=sop_id))
    db = get_db()
    sop = db.execute('SELECT * FROM sops WHERE id=? AND active=1', (sop_id,)).fetchone()
    if not sop:
        abort(404)
    stored = f'{uuid.uuid4().hex}.{ext}'
    upload_dir = Path(current_app.instance_path) / current_app.config['UPLOAD_FOLDER']
    upload_dir.mkdir(parents=True, exist_ok=True)
    f.save(upload_dir / stored)
    size = (upload_dir / stored).stat().st_size
    db.execute("UPDATE sop_versions SET status='SUPERSEDED' WHERE sop_id=? AND status='ACTIVE'", (sop_id,))
    cur = db.execute(
        '''INSERT INTO sop_versions(sop_id,revision,original_name,stored_name,content_type,file_size,status,uploaded_by)
           VALUES(?,?,?,?,?,?,'ACTIVE',?)''',
        (sop_id, revision, secure_filename(f.filename), stored, f.mimetype, size, user()['id']),
    )
    db.execute('UPDATE sops SET current_revision=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
               (revision, sop_id))
    for row in db.execute('SELECT employee_id FROM employee_assignments WHERE sop_id=? AND active=1',
                          (sop_id,)).fetchall():
        db.execute(
            '''INSERT INTO training_records(employee_id,sop_id,status)
               VALUES(?,?,'OUTSTANDING')
               ON CONFLICT(employee_id,sop_id) DO UPDATE SET status='OUTSTANDING',
                 completion_date=NULL,expiry_date=NULL,revision_completed=NULL,updated_at=CURRENT_TIMESTAMP''',
            (row['employee_id'], sop_id),
        )
    db.commit()
    audit('UPLOAD_REVISION', 'sop_version', cur.lastrowid, f'sop={sop_id}, revision={revision}')
    flash('Revision uploaded. Assigned staff have been reset to outstanding.')
    return redirect(url_for('main.sop_detail', sop_id=sop_id))


@bp.post('/sops/<int:sop_id>/role')
@role_required('manager', 'admin')
def sop_add_role(sop_id):
    job_role = request.form.get('job_role', '').strip()
    if not job_role:
        flash('Enter a job role.')
        return redirect(url_for('main.sop_detail', sop_id=sop_id))
    db = get_db()
    db.execute(
        '''INSERT INTO role_requirements(job_role,sop_id,required) VALUES(?,?,1)
           ON CONFLICT(job_role,sop_id) DO UPDATE SET required=1''', (job_role, sop_id)
    )
    for emp in db.execute('SELECT id FROM employees WHERE active=1 AND job_role=?', (job_role,)).fetchall():
        db.execute(
            '''INSERT INTO employee_assignments(employee_id,sop_id,source,assigned_by,active)
               VALUES(?,?,'ROLE',?,1) ON CONFLICT(employee_id,sop_id) DO UPDATE SET active=1''',
            (emp['id'], sop_id, user()['id']),
        )
        db.execute(
            '''INSERT INTO training_records(employee_id,sop_id,status) VALUES(?,?,'OUTSTANDING')
               ON CONFLICT(employee_id,sop_id) DO NOTHING''', (emp['id'], sop_id)
        )
    db.commit()
    audit('ADD_ROLE_REQUIREMENT', 'sop', sop_id, f'job_role={job_role}')
    flash('Role requirement added.')
    return redirect(url_for('main.sop_detail', sop_id=sop_id))


@bp.post('/sops/<int:sop_id>/retire')
@role_required('admin')
def sop_retire(sop_id):
    db = get_db()
    db.execute('UPDATE sops SET active=0,retired_at=CURRENT_TIMESTAMP,retired_by=? WHERE id=?',
               (user()['id'], sop_id))
    db.execute("UPDATE sop_versions SET status='RETIRED' WHERE sop_id=? AND status='ACTIVE'", (sop_id,))
    db.execute('UPDATE employee_assignments SET active=0 WHERE sop_id=?', (sop_id,))
    db.commit()
    audit('RETIRE_SOP', 'sop', sop_id, 'SOP retired; history preserved')
    flash('SOP retired. Historical training and signatures were preserved.')
    return redirect(url_for('main.sops', show='retired'))


@bp.route('/staff', methods=['GET', 'POST'])
@role_required('manager', 'admin')
def staff():
    u = user()
    db = get_db()
    if request.method == 'POST':
        dept = request.form.get('department', '').strip() or 'Unassigned'
        if u['access_role'] == 'manager':
            dept = manager_department(u)
        cur = db.execute(
            '''INSERT INTO employees(employee_number,name,email,site,department,job_role)
               VALUES(?,?,?,?,?,?)''',
            (request.form.get('employee_number', '').strip(), request.form.get('name', '').strip(),
             request.form.get('email', '').strip(), request.form.get('site', 'Preston').strip(),
             dept, request.form.get('job_role', '').strip()),
        )
        db.commit()
        ensure_role_assignments(cur.lastrowid)
        audit('CREATE_EMPLOYEE', 'employee', cur.lastrowid, 'Staff record created')
        flash('Staff member created.')
    if u['access_role'] == 'admin':
        rows = db.execute('SELECT * FROM employees WHERE active=1 ORDER BY department,name').fetchall()
    else:
        rows = db.execute('SELECT * FROM employees WHERE active=1 AND department=? ORDER BY name',
                          (manager_department(u),)).fetchall()
    return render_template('staff.html', employees=rows)


@bp.route('/users', methods=['GET', 'POST'])
@role_required('manager', 'admin')
def users():
    u = user()
    db = get_db()
    if request.method == 'POST':
        employee_id = request.form.get('employee_id', type=int)
        emp = db.execute('SELECT * FROM employees WHERE id=?', (employee_id,)).fetchone() if employee_id else None
        access_role = request.form.get('access_role', 'staff')
        if u['access_role'] == 'manager' and (
            not emp or emp['department'] != manager_department(u) or access_role != 'staff'
        ):
            abort(403)
        temp = request.form.get('temp_password', '')
        if len(temp) < 12:
            flash('Temporary password must be at least 12 characters.')
        else:
            try:
                db.execute(
                    '''INSERT INTO users(username,email,password_hash,access_role,employee_id,department,must_change_password)
                       VALUES(?,?,?,?,?,?,1)''',
                    (request.form.get('username', '').strip(), request.form.get('email', '').strip(),
                     generate_password_hash(temp), access_role, employee_id,
                     emp['department'] if emp else request.form.get('department', '').strip()),
                )
                db.commit()
                audit('CREATE_USER', 'user', None, f"username={request.form.get('username','').strip()}")
                flash('Login created.')
            except Exception:
                flash('Username already exists or login data was invalid.')
    if u['access_role'] == 'admin':
        login_rows = db.execute(
            '''SELECT u.*,e.name employee_name,e.department employee_department
               FROM users u LEFT JOIN employees e ON e.id=u.employee_id ORDER BY u.username'''
        ).fetchall()
        employees = db.execute('SELECT * FROM employees WHERE active=1 ORDER BY department,name').fetchall()
    else:
        d = manager_department(u)
        login_rows = db.execute(
            '''SELECT u.*,e.name employee_name,e.department employee_department
               FROM users u LEFT JOIN employees e ON e.id=u.employee_id
               WHERE e.department=? OR u.department=? ORDER BY u.username''', (d, d)
        ).fetchall()
        employees = db.execute('SELECT * FROM employees WHERE active=1 AND department=? ORDER BY name', (d,)).fetchall()
    return render_template('users.html', users=login_rows, employees=employees)


@bp.route('/audit')
@role_required('admin')
def audit_view():
    rows = get_db().execute(
        '''SELECT a.*,u.username FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
           ORDER BY a.id DESC LIMIT 1000'''
    ).fetchall()
    return render_template('audit.html', rows=rows)
