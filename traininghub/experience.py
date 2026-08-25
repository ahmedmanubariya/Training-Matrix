from datetime import date, timedelta
from pathlib import Path

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    send_from_directory, url_for,
)
from werkzeug.security import check_password_hash

from .db import get_db
from .routes import audit, login_required, user

bp = Blueprint('experience', __name__)

ACKNOWLEDGEMENT = (
    'I confirm that I have read and understood this controlled document and that this '
    'electronic acknowledgement is attributable to my authenticated account.'
)


def effective_role(u):
    if not u:
        return None
    try:
        return u['permission_role'] or u['access_role']
    except (KeyError, IndexError):
        return u['access_role']


def assigned_rows(employee_id):
    if not employee_id:
        return []
    return get_db().execute(
        '''SELECT ea.id assignment_id,ea.due_date,s.id sop_id,s.reference,s.title,s.category,
                  s.current_revision,COALESCE(tr.status,'OUTSTANDING') status,
                  tr.completion_date,tr.expiry_date,tr.revision_completed,
                  v.id version_id,v.original_name,v.revision version_revision,
                  CASE WHEN mr.id IS NULL THEN 0 ELSE 1 END has_read,
                  (SELECT MAX(sig.signed_at) FROM signatures sig
                     WHERE sig.employee_id=? AND sig.sop_id=s.id) signed_at
           FROM employee_assignments ea
           JOIN sops s ON s.id=ea.sop_id AND s.active=1
           LEFT JOIN training_records tr ON tr.employee_id=ea.employee_id AND tr.sop_id=s.id
           LEFT JOIN sop_versions v ON v.sop_id=s.id AND v.status='ACTIVE'
           LEFT JOIN users u ON u.employee_id=ea.employee_id AND u.active=1
           LEFT JOIN material_reads mr ON mr.user_id=u.id AND mr.version_id=v.id
           WHERE ea.employee_id=? AND ea.active=1
           GROUP BY ea.id ORDER BY s.reference,s.title''',
        (employee_id, employee_id),
    ).fetchall()


def personal_metrics(employee_id):
    rows = assigned_rows(employee_id)
    eligible = [r for r in rows if r['status'] != 'NOT_APPLICABLE']
    completed = sum(1 for r in eligible if r['status'] in ('COMPLIANT', 'DUE_SOON'))
    overdue = sum(1 for r in eligible if r['status'] == 'OVERDUE')
    outstanding = sum(1 for r in eligible if r['status'] == 'OUTSTANDING')
    total = len(eligible)
    return {
        'total': total,
        'completed': completed,
        'overdue': overdue,
        'outstanding': outstanding,
        'percentage': round(completed * 100 / total, 1) if total else 100.0,
    }


def library_rows(employee_id=None, search=''):
    """Return every active approved document plus the current user's training position.

    The library is reference material for every authorised login. Assignment-specific status
    and acknowledgement controls are layered on top for the employee linked to the account.
    """
    db = get_db()
    params = []
    if employee_id:
        sql = '''SELECT s.id sop_id,s.reference,s.title,s.category,s.current_revision,
                        v.id version_id,v.original_name,v.revision version_revision,
                        ea.id assignment_id,
                        CASE WHEN ea.id IS NULL THEN 'REFERENCE'
                             ELSE COALESCE(tr.status,'OUTSTANDING') END status,
                        CASE WHEN mr.id IS NULL THEN 0 ELSE 1 END has_read,
                        (SELECT MAX(sig.signed_at) FROM signatures sig
                           WHERE sig.employee_id=? AND sig.sop_id=s.id) signed_at,
                        tr.completion_date,tr.expiry_date
                 FROM sops s
                 LEFT JOIN sop_versions v ON v.sop_id=s.id AND v.status='ACTIVE'
                 LEFT JOIN employee_assignments ea
                   ON ea.sop_id=s.id AND ea.employee_id=? AND ea.active=1
                 LEFT JOIN training_records tr
                   ON tr.employee_id=? AND tr.sop_id=s.id
                 LEFT JOIN users u ON u.employee_id=? AND u.active=1
                 LEFT JOIN material_reads mr ON mr.user_id=u.id AND mr.version_id=v.id
                 WHERE s.active=1'''
        params.extend([employee_id, employee_id, employee_id, employee_id])
    else:
        sql = '''SELECT s.id sop_id,s.reference,s.title,s.category,s.current_revision,
                        v.id version_id,v.original_name,v.revision version_revision,
                        NULL assignment_id,'REFERENCE' status,0 has_read,NULL signed_at,
                        NULL completion_date,NULL expiry_date
                 FROM sops s
                 LEFT JOIN sop_versions v ON v.sop_id=s.id AND v.status='ACTIVE'
                 WHERE s.active=1'''
    if search:
        sql += ' AND (LOWER(s.reference) LIKE ? OR LOWER(s.title) LIKE ?)'
        like = f'%{search.lower()}%'
        params.extend([like, like])
    sql += ' ORDER BY s.reference,s.title'
    return db.execute(sql, params).fetchall()


@bp.route('/overview')
@login_required
def overview():
    u = user()
    metrics = personal_metrics(u['employee_id']) if u['employee_id'] else {
        'total': 0, 'completed': 0, 'overdue': 0, 'outstanding': 0, 'percentage': 100.0,
    }
    return render_template('overview.html', metrics=metrics, role=effective_role(u))


@bp.route('/controlled-documents')
@login_required
def controlled_documents():
    u = user()
    q = request.args.get('q', '').strip()
    rows = library_rows(u['employee_id'], q)
    return render_template('controlled_documents.html', rows=rows, q=q, role=effective_role(u))


@bp.route('/controlled-documents/<int:sop_id>')
@login_required
def document(sop_id):
    u = user()
    db = get_db()
    sop = db.execute('SELECT * FROM sops WHERE id=? AND active=1', (sop_id,)).fetchone()
    if not sop:
        abort(404)
    version = db.execute(
        "SELECT * FROM sop_versions WHERE sop_id=? AND status='ACTIVE' ORDER BY uploaded_at DESC LIMIT 1",
        (sop_id,),
    ).fetchone()
    assigned = False
    record = None
    if u['employee_id']:
        assigned = bool(db.execute(
            'SELECT 1 FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1',
            (u['employee_id'], sop_id),
        ).fetchone())
        record = db.execute(
            'SELECT * FROM training_records WHERE employee_id=? AND sop_id=?',
            (u['employee_id'], sop_id),
        ).fetchone()
    signatures = []
    if u['employee_id']:
        signatures = db.execute(
            '''SELECT sig.*,v.original_name FROM signatures sig
               JOIN sop_versions v ON v.id=sig.version_id
               WHERE sig.employee_id=? AND sig.sop_id=? ORDER BY sig.signed_at DESC''',
            (u['employee_id'], sop_id),
        ).fetchall()
    return render_template(
        'controlled_document_detail.html', sop=sop, version=version, assigned=assigned,
        record=record, signatures=signatures, acknowledgement=ACKNOWLEDGEMENT,
    )


@bp.route('/controlled-documents/material/<int:version_id>')
@login_required
def document_material(version_id):
    u = user()
    db = get_db()
    version = db.execute(
        '''SELECT v.*,s.id sop_id FROM sop_versions v JOIN sops s ON s.id=v.sop_id
           WHERE v.id=? AND v.status='ACTIVE' AND s.active=1''',
        (version_id,),
    ).fetchone()
    if not version:
        abort(404)

    # Every authorised user may open the active controlled document. If it is assigned to
    # their employee record, the read event becomes part of the training acknowledgement flow.
    if u['employee_id']:
        assigned = db.execute(
            'SELECT 1 FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1',
            (u['employee_id'], version['sop_id']),
        ).fetchone()
        if assigned:
            db.execute(
                '''INSERT INTO material_reads(user_id,employee_id,version_id) VALUES(?,?,?)
                   ON CONFLICT(user_id,version_id) DO UPDATE SET last_opened_at=CURRENT_TIMESTAMP''',
                (u['id'], u['employee_id'], version_id),
            )
            db.commit()

    audit('OPEN_CONTROLLED_DOCUMENT', 'sop_version', version_id, 'Controlled document opened')
    upload_dir = Path(current_app.instance_path) / current_app.config['UPLOAD_FOLDER']
    return send_from_directory(
        upload_dir, version['stored_name'], as_attachment=False,
        download_name=version['original_name'],
    )


@bp.post('/controlled-documents/<int:sop_id>/acknowledge')
@login_required
def acknowledge(sop_id):
    u = user()
    if not u['employee_id']:
        abort(403)
    db = get_db()
    assignment = db.execute(
        'SELECT 1 FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1',
        (u['employee_id'], sop_id),
    ).fetchone()
    if not assignment:
        abort(403)

    version_id = request.form.get('version_id', type=int)
    version = db.execute(
        '''SELECT v.*,s.validity_months FROM sop_versions v JOIN sops s ON s.id=v.sop_id
           WHERE v.id=? AND v.sop_id=? AND v.status='ACTIVE' AND s.active=1''',
        (version_id, sop_id),
    ).fetchone()
    read = db.execute(
        'SELECT 1 FROM material_reads WHERE user_id=? AND version_id=?',
        (u['id'], version_id),
    ).fetchone()
    if not version or not read:
        flash('Please open and read the current PDF before selecting Read & Understood.')
        return redirect(url_for('experience.document', sop_id=sop_id))

    signed_name = request.form.get('signed_name', '').strip()
    password = request.form.get('password', '')
    if signed_name.casefold() != (u['employee_name'] or '').strip().casefold():
        flash('The signature name must match your staff record.')
        return redirect(url_for('experience.document', sop_id=sop_id))
    if not check_password_hash(u['password_hash'], password):
        flash('Password confirmation failed. Nothing was signed.')
        return redirect(url_for('experience.document', sop_id=sop_id))

    months = version['validity_months']
    expiry = (date.today() + timedelta(days=int(months) * 30)).isoformat() if months else None
    db.execute(
        '''INSERT INTO signatures(user_id,employee_id,sop_id,version_id,signed_name,statement,
                                  revision,ip_address)
           VALUES(?,?,?,?,?,?,?,?)''',
        (u['id'], u['employee_id'], sop_id, version_id, signed_name, ACKNOWLEDGEMENT,
         version['revision'], request.remote_addr),
    )
    db.execute(
        '''INSERT INTO training_records(employee_id,sop_id,status,completion_date,expiry_date,
                                        revision_completed)
           VALUES(?,?,'COMPLIANT',?,?,?)
           ON CONFLICT(employee_id,sop_id) DO UPDATE SET status='COMPLIANT',
             completion_date=excluded.completion_date,expiry_date=excluded.expiry_date,
             revision_completed=excluded.revision_completed,updated_at=CURRENT_TIMESTAMP''',
        (u['employee_id'], sop_id, date.today().isoformat(), expiry, version['revision']),
    )
    db.commit()
    audit(
        'READ_AND_UNDERSTOOD', 'sop', sop_id,
        f"employee={u['employee_id']}, revision={version['revision']}, signed_name={signed_name}",
    )
    flash('Read & Understood recorded with your electronic signature and timestamp.')
    return redirect(url_for('experience.overview'))
