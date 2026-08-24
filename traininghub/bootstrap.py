import os

from werkzeug.security import generate_password_hash

from .db import get_db


def ensure_admin():
    db = get_db()
    if db.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']:
        return
    username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME', 'admin')
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', 'ChangeMeNow!2026')
    email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', 'admin@example.local')
    db.execute(
        '''INSERT INTO users(username,email,password_hash,access_role,must_change_password)
           VALUES(?,?,?,?,1)''',
        (username, email, generate_password_hash(password), 'admin'),
    )
    db.commit()
