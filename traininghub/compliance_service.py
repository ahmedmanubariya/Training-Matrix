from datetime import date, timedelta

from .db import get_db


def refresh_employee_statuses(employee_id, due_soon_days=60):
    """Recalculate current/due-soon/overdue status from stored completion/expiry dates."""
    db = get_db()
    records = db.execute(
        '''SELECT * FROM training_records WHERE employee_id=?''',
        (employee_id,),
    ).fetchall()
    today = date.today()
    due_cutoff = today + timedelta(days=due_soon_days)

    for record in records:
        if record['status'] == 'NOT_APPLICABLE':
            continue
        if not record['completion_date']:
            new_status = 'OUTSTANDING'
        elif not record['expiry_date']:
            new_status = 'COMPLIANT'
        else:
            expiry = date.fromisoformat(record['expiry_date'])
            if expiry < today:
                new_status = 'OVERDUE'
            elif expiry <= due_cutoff:
                new_status = 'DUE_SOON'
            else:
                new_status = 'COMPLIANT'
        if new_status != record['status']:
            db.execute(
                'UPDATE training_records SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (new_status, record['id']),
            )
    db.commit()


def refresh_department(department=None):
    db = get_db()
    if department is None:
        employees = db.execute('SELECT id FROM employees WHERE active=1').fetchall()
    else:
        employees = db.execute(
            'SELECT id FROM employees WHERE active=1 AND department=?', (department,)
        ).fetchall()
    for employee in employees:
        refresh_employee_statuses(employee['id'])
    return len(employees)
