"""Scheduled TrainingHub maintenance job.

Run this from the production server scheduler (for example every 15 minutes).
It synchronises the approved document folder, recalculates staff training status,
and creates/sends below-threshold compliance alerts.
"""

from traininghub import create_app
from traininghub.alerts import send_or_queue
from traininghub.compliance_service import refresh_employee_statuses
from traininghub.db import get_db
from traininghub.document_sync import sync_approved_folder


def run():
    app = create_app()
    with app.app_context():
        sync_result = sync_approved_folder(actor_user_id=None)
        db = get_db()
        employees = db.execute('SELECT id FROM employees WHERE active=1').fetchall()
        alerts = 0
        for employee in employees:
            refresh_employee_statuses(employee['id'])
            alerts += 1 if send_or_queue(employee['id']) else 0
        print({
            'document_sync': sync_result,
            'employees_checked': len(employees),
            'alerts_created': alerts,
        })


if __name__ == '__main__':
    run()
