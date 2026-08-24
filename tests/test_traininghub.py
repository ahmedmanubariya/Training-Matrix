import os
import tempfile
import unittest

from traininghub import create_app
from traininghub.db import get_db


class TrainingHubTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.unlink(self.db_path)
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'SECRET_KEY': 'test-secret',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_login_page_and_bootstrap_admin(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'TrainingHub', response.data)
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM users WHERE access_role='admin'").fetchone()
            self.assertIsNotNone(row)

    def test_admin_can_create_sop(self):
        with self.app.app_context():
            admin_id = get_db().execute("SELECT id FROM users WHERE access_role='admin'").fetchone()['id']
        with self.client.session_transaction() as session:
            session['user_id'] = admin_id
        response = self.client.post('/sops', data={
            'reference': 'TEST.QM.001',
            'title': 'Test SOP',
            'revision': '001',
            'validity_months': '12',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            sop = get_db().execute("SELECT * FROM sops WHERE reference='TEST.QM.001'").fetchone()
            self.assertIsNotNone(sop)
            self.assertEqual(sop['current_revision'], '001')

    def test_role_assignment_updates_employee_training(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO employees(name,department,job_role) VALUES('Test User','Production','Operator')")
            employee_id = db.execute("SELECT id FROM employees WHERE name='Test User'").fetchone()['id']
            db.execute("INSERT INTO sops(reference,title,current_revision) VALUES('TEST.SOP.002','Role SOP','001')")
            sop_id = db.execute("SELECT id FROM sops WHERE reference='TEST.SOP.002'").fetchone()['id']
            db.execute("INSERT INTO role_requirements(job_role,sop_id,required) VALUES('Operator',?,1)", (sop_id,))
            db.commit()
            from traininghub.assignment_service import sync_role_assignments
            sync_role_assignments(employee_id)
            assignment = db.execute(
                "SELECT * FROM employee_assignments WHERE employee_id=? AND sop_id=? AND active=1",
                (employee_id, sop_id),
            ).fetchone()
            self.assertIsNotNone(assignment)
            record = db.execute(
                "SELECT * FROM training_records WHERE employee_id=? AND sop_id=?",
                (employee_id, sop_id),
            ).fetchone()
            self.assertEqual(record['status'], 'OUTSTANDING')


if __name__ == '__main__':
    unittest.main()
