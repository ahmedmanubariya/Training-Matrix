import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = r'''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_number TEXT,
  name TEXT NOT NULL,
  email TEXT,
  site TEXT NOT NULL DEFAULT 'Preston',
  department TEXT NOT NULL DEFAULT 'Unassigned',
  job_role TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  email TEXT,
  password_hash TEXT NOT NULL,
  access_role TEXT NOT NULL CHECK(access_role IN ('staff','manager','admin')),
  employee_id INTEGER,
  department TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT,
  FOREIGN KEY(employee_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS sops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reference TEXT NOT NULL,
  title TEXT NOT NULL,
  category TEXT,
  sop_type TEXT,
  owner TEXT,
  current_revision TEXT,
  validity_months INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  retired_at TEXT,
  retired_by INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(reference, title)
);

CREATE TABLE IF NOT EXISTS sop_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sop_id INTEGER NOT NULL,
  revision TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  content_type TEXT,
  file_size INTEGER,
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('DRAFT','ACTIVE','SUPERSEDED','RETIRED')),
  uploaded_by INTEGER,
  uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(sop_id) REFERENCES sops(id),
  FOREIGN KEY(uploaded_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS role_requirements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_role TEXT NOT NULL,
  sop_id INTEGER NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  UNIQUE(job_role, sop_id),
  FOREIGN KEY(sop_id) REFERENCES sops(id)
);

CREATE TABLE IF NOT EXISTS employee_assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id INTEGER NOT NULL,
  sop_id INTEGER NOT NULL,
  source TEXT NOT NULL DEFAULT 'ROLE',
  assigned_by INTEGER,
  assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  due_date TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(employee_id, sop_id),
  FOREIGN KEY(employee_id) REFERENCES employees(id),
  FOREIGN KEY(sop_id) REFERENCES sops(id),
  FOREIGN KEY(assigned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS material_reads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  employee_id INTEGER NOT NULL,
  version_id INTEGER NOT NULL,
  first_opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, version_id),
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(employee_id) REFERENCES employees(id),
  FOREIGN KEY(version_id) REFERENCES sop_versions(id)
);

CREATE TABLE IF NOT EXISTS training_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id INTEGER NOT NULL,
  sop_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'OUTSTANDING' CHECK(status IN ('COMPLIANT','DUE_SOON','OVERDUE','OUTSTANDING','NOT_APPLICABLE')),
  completion_date TEXT,
  expiry_date TEXT,
  revision_completed TEXT,
  notes TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(employee_id, sop_id),
  FOREIGN KEY(employee_id) REFERENCES employees(id),
  FOREIGN KEY(sop_id) REFERENCES sops(id)
);

CREATE TABLE IF NOT EXISTS signatures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  employee_id INTEGER NOT NULL,
  sop_id INTEGER NOT NULL,
  version_id INTEGER NOT NULL,
  signed_name TEXT NOT NULL,
  statement TEXT NOT NULL,
  revision TEXT NOT NULL,
  signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip_address TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(employee_id) REFERENCES employees(id),
  FOREIGN KEY(sop_id) REFERENCES sops(id),
  FOREIGN KEY(version_id) REFERENCES sop_versions(id)
);

CREATE TABLE IF NOT EXISTS compliance_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id INTEGER NOT NULL,
  recipient TEXT NOT NULL,
  percentage REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'QUEUED',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at TEXT,
  FOREIGN KEY(employee_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER,
  details TEXT,
  ip_address TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
'''


def get_db():
    if 'db' not in g:
        db_path = Path(current_app.instance_path) / current_app.config['DATABASE']
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(_exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def init_app(app):
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.instance_path, app.config.get('UPLOAD_FOLDER', 'uploads')).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
