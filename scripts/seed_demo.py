from werkzeug.security import generate_password_hash

from traininghub import create_app
from traininghub.assignment_service import sync_role_assignments
from traininghub.db import get_db


def seed():
    app = create_app()
    with app.app_context():
        db = get_db()
        if db.execute("SELECT 1 FROM employees WHERE name='Demo Operator'").fetchone():
            print('Demo data already present.')
            return

        db.execute("INSERT OR IGNORE INTO departments(name) VALUES('Production')")
        db.execute("INSERT OR IGNORE INTO departments(name) VALUES('Quality')")
        db.execute(
            "INSERT INTO employees(employee_number,name,email,site,department,job_role) VALUES('DEMO001','Demo Operator','demo.operator@example.local','Preston','Production','Operator')"
        )
        employee_id = db.execute("SELECT id FROM employees WHERE employee_number='DEMO001'").fetchone()['id']
        db.execute(
            "INSERT INTO sops(reference,title,category,sop_type,current_revision,validity_months) VALUES('DEMO.SOP.001','Site Induction','Safety','SOP','001',12)"
        )
        sop_id = db.execute("SELECT id FROM sops WHERE reference='DEMO.SOP.001'").fetchone()['id']
        db.execute(
            "INSERT INTO role_requirements(job_role,sop_id,required) VALUES('Operator',?,1)", (sop_id,)
        )
        db.execute(
            "INSERT INTO users(username,email,password_hash,access_role,employee_id,department,must_change_password) VALUES('demo.staff','demo.operator@example.local',?,'staff',?,'Production',0)",
            (generate_password_hash('DemoTraining!2026'), employee_id),
        )
        db.execute(
            "INSERT INTO users(username,email,password_hash,access_role,department,must_change_password) VALUES('demo.manager','demo.manager@example.local',?,'manager','Production',0)",
            (generate_password_hash('DemoManager!2026'),),
        )
        db.commit()
        sync_role_assignments(employee_id)
        print('Demo data created.')
        print('Staff: demo.staff / DemoTraining!2026')
        print('Manager: demo.manager / DemoManager!2026')


if __name__ == '__main__':
    seed()
