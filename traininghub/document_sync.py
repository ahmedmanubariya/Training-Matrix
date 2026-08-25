import hashlib
import mimetypes
import os
import re
import shutil
import uuid
from pathlib import Path

from flask import current_app

from .db import get_db

SUPPORTED = {'.pdf', '.docx', '.pptx', '.txt'}
REV_PATTERNS = [
    re.compile(r'(?i)^(?P<ref>.+?)[ _-]+(?:rev(?:ision)?|ver(?:sion)?|v)[ _-]?(?P<rev>[A-Za-z0-9.]+)$'),
    re.compile(r'(?i)^(?P<ref>[A-Za-z0-9._-]+?)[ _-]+(?P<rev>\d{2,4})$'),
]


def _hash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_filename(path):
    stem = path.stem.strip()
    for pattern in REV_PATTERNS:
        m = pattern.match(stem)
        if m:
            return m.group('ref').strip(' _-'), m.group('rev').strip()
    # Fallback: the complete filename becomes the reference and revision is based on mtime.
    return stem, str(int(path.stat().st_mtime))


def sync_approved_folder(root=None, actor_user_id=None):
    root = Path(root or current_app.config.get('APPROVED_DOCS_ROOT') or '')
    if not str(root) or not root.exists() or not root.is_dir():
        return {'configured': False, 'scanned': 0, 'created': 0, 'updated': 0, 'unchanged': 0, 'errors': []}

    db = get_db()
    upload_dir = Path(current_app.instance_path) / current_app.config['UPLOAD_FOLDER']
    upload_dir.mkdir(parents=True, exist_ok=True)
    result = {'configured': True, 'root': str(root), 'scanned': 0, 'created': 0, 'updated': 0, 'unchanged': 0, 'errors': []}

    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED):
        result['scanned'] += 1
        try:
            reference, revision = parse_filename(path)
            digest = _hash(path)
            stat = path.stat()
            source = db.execute('SELECT * FROM document_sources WHERE source_path=?', (str(path),)).fetchone()
            if source and source['source_hash'] == digest:
                db.execute('UPDATE document_sources SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?', (source['id'],))
                result['unchanged'] += 1
                continue

            sop = None
            if source:
                sop = db.execute('SELECT * FROM sops WHERE id=?', (source['sop_id'],)).fetchone()
            if not sop:
                sop = db.execute('SELECT * FROM sops WHERE reference=? AND active=1 ORDER BY id LIMIT 1', (reference,)).fetchone()

            is_new = sop is None
            if is_new:
                cur = db.execute(
                    '''INSERT INTO sops(reference,title,category,sop_type,current_revision,active)
                       VALUES(?,?,?,'Controlled Document',?,1)''',
                    (reference, reference, 'Approved SOPs', revision),
                )
                sop_id = cur.lastrowid
                result['created'] += 1
            else:
                sop_id = sop['id']
                result['updated'] += 1

            stored = f'{uuid.uuid4().hex}{path.suffix.lower()}'
            shutil.copy2(path, upload_dir / stored)
            db.execute("UPDATE sop_versions SET status='SUPERSEDED' WHERE sop_id=? AND status='ACTIVE'", (sop_id,))
            db.execute(
                '''INSERT INTO sop_versions(sop_id,revision,original_name,stored_name,content_type,file_size,status,uploaded_by)
                   VALUES(?,?,?,?,?,?, 'ACTIVE', ?)''',
                (sop_id, revision, path.name, stored, mimetypes.guess_type(path.name)[0], stat.st_size, actor_user_id),
            )
            db.execute('UPDATE sops SET current_revision=?,updated_at=CURRENT_TIMESTAMP,active=1 WHERE id=?', (revision, sop_id))
            db.execute(
                '''INSERT INTO document_sources(sop_id,source_path,source_mtime,source_size,source_hash,last_seen_at)
                   VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(sop_id) DO UPDATE SET source_path=excluded.source_path,
                     source_mtime=excluded.source_mtime,source_size=excluded.source_size,
                     source_hash=excluded.source_hash,last_seen_at=CURRENT_TIMESTAMP''',
                (sop_id, str(path), stat.st_mtime, stat.st_size, digest),
            )
            # Any approved revision change requires retraining for active assignees.
            for row in db.execute('SELECT employee_id FROM employee_assignments WHERE sop_id=? AND active=1', (sop_id,)).fetchall():
                db.execute(
                    '''INSERT INTO training_records(employee_id,sop_id,status)
                       VALUES(?,?,'OUTSTANDING')
                       ON CONFLICT(employee_id,sop_id) DO UPDATE SET status='OUTSTANDING',
                         completion_date=NULL,expiry_date=NULL,revision_completed=NULL,updated_at=CURRENT_TIMESTAMP''',
                    (row['employee_id'], sop_id),
                )
        except Exception as exc:
            result['errors'].append({'file': str(path), 'error': str(exc)})

    db.commit()
    return result
