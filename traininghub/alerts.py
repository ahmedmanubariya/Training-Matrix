import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import Blueprint, flash, render_template, redirect, url_for

from .db import get_db
from .routes import compliance, manager_department, role_required, user, audit

bp = Blueprint('alerts', __name__, url_prefix='/alerts')


def send_or_queue(employee_id):
    db = get_db()
    emp = db.execute('SELECT * FROM employees WHERE id=? AND active=1', (employee_id,)).fetchone()
    if not emp or not emp['email']:
        return False

    result = compliance(employee_id)
    threshold = 80
    if result['percentage'] >= threshold:
        return False

    recent = db.execute(
        '''SELECT 1 FROM compliance_alerts
           WHERE employee_id=? AND created_at >= datetime('now','-1 day') LIMIT 1''',
        (employee_id,),
    ).fetchone()
    if recent:
        return False

    status = 'QUEUED'
    sent_at = None
    host = os.environ.get('SMTP_HOST')
    if host:
        try:
            msg = EmailMessage()
            msg['Subject'] = f"Training compliance alert: {result['percentage']}%"
            msg['From'] = os.environ.get('SMTP_FROM', 'training@example.local')
            msg['To'] = emp['email']
            msg.set_content(
                f"Hello {emp['name']},\n\n"
                f"Your mandatory training compliance is {result['percentage']}%, below the {threshold}% threshold.\n"
                "Please log in to TrainingHub and complete your outstanding assigned training.\n"
            )
            with smtplib.SMTP(host, int(os.environ.get('SMTP_PORT', '25')), timeout=10) as server:
                if os.environ.get('SMTP_STARTTLS') == '1':
                    server.starttls()
                if os.environ.get('SMTP_USERNAME'):
                    server.login(os.environ['SMTP_USERNAME'], os.environ.get('SMTP_PASSWORD', ''))
                server.send_message(msg)
            status = 'SENT'
            sent_at = datetime.utcnow().isoformat(timespec='seconds')
        except Exception:
            status = 'FAILED'

    db.execute(
        '''INSERT INTO compliance_alerts(employee_id,recipient,percentage,status,sent_at)
           VALUES(?,?,?,?,?)''',
        (employee_id, emp['email'], result['percentage'], status, sent_at),
    )
    db.commit()
    return True


@bp.route('/')
@role_required('manager', 'admin')
def index():
    u = user()
    db = get_db()
    if u['access_role'] == 'admin':
        rows = db.execute(
            '''SELECT a.*,e.name,e.department FROM compliance_alerts a
               JOIN employees e ON e.id=a.employee_id ORDER BY a.id DESC LIMIT 500'''
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT a.*,e.name,e.department FROM compliance_alerts a
               JOIN employees e ON e.id=a.employee_id
               WHERE e.department=? ORDER BY a.id DESC LIMIT 500''',
            (manager_department(u),),
        ).fetchall()
    return render_template('alerts.html', rows=rows)


@bp.post('/run')
@role_required('manager', 'admin')
def run_check():
    u = user()
    db = get_db()
    if u['access_role'] == 'admin':
        employees = db.execute('SELECT id FROM employees WHERE active=1').fetchall()
    else:
        employees = db.execute('SELECT id FROM employees WHERE active=1 AND department=?',
                               (manager_department(u),)).fetchall()
    created = 0
    for emp in employees:
        created += 1 if send_or_queue(emp['id']) else 0
    audit('RUN_ALERT_CHECK', 'system', None, f'checked={len(employees)}, alerts={created}')
    flash(f'Compliance check complete. {created} new alert(s) created.')
    return redirect(url_for('alerts.index'))
