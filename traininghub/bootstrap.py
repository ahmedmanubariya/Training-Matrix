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


def ensure_development_catalog():
    """Seed safe metadata for the two supplied Eaststone SOP examples.

    The controlled PDF binaries deliberately remain outside source control. Once an approved
    drive is configured, document_sync attaches the live approved files and their revisions.
    """
    if os.environ.get('DEV_SEED_EASTSTONE_EXAMPLES', '0') != '1':
        return

    examples = [
        ('ES.SOP.001', 'Writing of Standard Operating Procedures & Forms', 'V10', 'QA'),
        ('ES.SOP.003', 'Eaststone Site Induction', 'V07', 'All'),
    ]
    db = get_db()
    for reference, title, revision, owner in examples:
        db.execute(
            '''INSERT INTO sops(reference,title,category,sop_type,owner,current_revision,active)
               VALUES(?,?,'Approved SOPs','SOP',?,?,1)
               ON CONFLICT(reference,title) DO UPDATE SET
                 current_revision=excluded.current_revision,
                 owner=excluded.owner,
                 active=1,
                 updated_at=CURRENT_TIMESTAMP''',
            (reference, title, owner, revision),
        )
    db.commit()
