from flask import Blueprint, abort, flash, redirect, request, url_for

from .db import get_db
from .routes import audit, role_required, user

bp = Blueprint('sop_admin', __name__, url_prefix='/sops')


@bp.post('/<int:sop_id>/edit')
@role_required('manager', 'admin')
def edit(sop_id):
    db = get_db()
    sop = db.execute('SELECT * FROM sops WHERE id=?', (sop_id,)).fetchone()
    if not sop:
        abort(404)
    title = request.form.get('title', '').strip()
    if not title:
        flash('SOP title is required.')
        return redirect(url_for('main.sop_detail', sop_id=sop_id))
    db.execute(
        '''UPDATE sops SET title=?,category=?,sop_type=?,owner=?,validity_months=?,updated_at=CURRENT_TIMESTAMP
           WHERE id=?''',
        (title, request.form.get('category', '').strip(),
         request.form.get('sop_type', '').strip(), request.form.get('owner', '').strip(),
         request.form.get('validity_months', type=int), sop_id),
    )
    db.commit()
    audit('EDIT_SOP', 'sop', sop_id, 'SOP metadata updated')
    flash('SOP details updated.')
    return redirect(url_for('main.sop_detail', sop_id=sop_id))


@bp.post('/<int:sop_id>/restore')
@role_required('admin')
def restore(sop_id):
    db = get_db()
    sop = db.execute('SELECT * FROM sops WHERE id=?', (sop_id,)).fetchone()
    if not sop:
        abort(404)
    db.execute(
        '''UPDATE sops SET active=1,retired_at=NULL,retired_by=NULL,updated_at=CURRENT_TIMESTAMP
           WHERE id=?''', (sop_id,)
    )
    db.commit()
    audit('RESTORE_SOP', 'sop', sop_id, 'SOP restored; requirements must be reviewed')
    flash('SOP restored. Review its active revision and role assignments before use.')
    return redirect(url_for('main.sop_detail', sop_id=sop_id))


@bp.post('/<int:sop_id>/role/remove')
@role_required('manager', 'admin')
def remove_role(sop_id):
    job_role = request.form.get('job_role', '').strip()
    if not job_role:
        return redirect(url_for('main.sop_detail', sop_id=sop_id))
    db = get_db()
    db.execute('DELETE FROM role_requirements WHERE sop_id=? AND job_role=?', (sop_id, job_role))
    employees = db.execute('SELECT id FROM employees WHERE active=1 AND job_role=?', (job_role,)).fetchall()
    for emp in employees:
        assignment = db.execute(
            'SELECT source FROM employee_assignments WHERE employee_id=? AND sop_id=?',
            (emp['id'], sop_id),
        ).fetchone()
        if assignment and assignment['source'] == 'ROLE':
            db.execute('UPDATE employee_assignments SET active=0 WHERE employee_id=? AND sop_id=?',
                       (emp['id'], sop_id))
    db.commit()
    audit('REMOVE_ROLE_REQUIREMENT', 'sop', sop_id, f'job_role={job_role}')
    flash('Role requirement removed. Historical training records were preserved.')
    return redirect(url_for('main.sop_detail', sop_id=sop_id))
