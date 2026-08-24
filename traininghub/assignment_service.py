from .db import get_db


def sync_role_assignments(employee_id, assigned_by=None):
    """Synchronise ROLE-sourced assignments to the employee's current job role.

    Manual/migrated assignments are never removed. Historical training records and
    signatures are preserved even when a role assignment becomes inactive.
    """
    db = get_db()
    employee = db.execute('SELECT * FROM employees WHERE id=? AND active=1', (employee_id,)).fetchone()
    if not employee:
        return

    required = {
        row['sop_id'] for row in db.execute(
            '''SELECT rr.sop_id FROM role_requirements rr
               JOIN sops s ON s.id=rr.sop_id
               WHERE rr.job_role=? AND rr.required=1 AND s.active=1''',
            (employee['job_role'] or '',),
        ).fetchall()
    }

    current_role_assignments = db.execute(
        "SELECT sop_id FROM employee_assignments WHERE employee_id=? AND source='ROLE' AND active=1",
        (employee_id,),
    ).fetchall()
    current_ids = {row['sop_id'] for row in current_role_assignments}

    for sop_id in current_ids - required:
        db.execute(
            "UPDATE employee_assignments SET active=0 WHERE employee_id=? AND sop_id=? AND source='ROLE'",
            (employee_id, sop_id),
        )

    for sop_id in required:
        db.execute(
            '''INSERT INTO employee_assignments(employee_id,sop_id,source,assigned_by,active)
               VALUES(?,?,'ROLE',?,1)
               ON CONFLICT(employee_id,sop_id) DO UPDATE SET active=1, source='ROLE' ''',
            (employee_id, sop_id, assigned_by),
        )
        db.execute(
            '''INSERT INTO training_records(employee_id,sop_id,status)
               VALUES(?,?,'OUTSTANDING') ON CONFLICT(employee_id,sop_id) DO NOTHING''',
            (employee_id, sop_id),
        )

    db.commit()
