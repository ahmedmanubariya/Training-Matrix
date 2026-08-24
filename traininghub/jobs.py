from traininghub import create_app
from traininghub.alerts import send_or_queue
from traininghub.compliance_service import refresh_employee_statuses
from traininghub.db import get_db


def run_daily_compliance_job():
    app = create_app()
    checked = 0
    alerts = 0
    with app.app_context():
        employees = get_db().execute('SELECT id FROM employees WHERE active=1').fetchall()
        for employee in employees:
            refresh_employee_statuses(employee['id'])
            checked += 1
            alerts += 1 if send_or_queue(employee['id']) else 0
    print(f'TrainingHub compliance job: checked={checked}, new_alerts={alerts}')


if __name__ == '__main__':
    run_daily_compliance_job()
