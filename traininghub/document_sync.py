import hashlib
import mimetypes
import re
import shutil
import uuid
from pathlib import Path

from flask import current_app

from .db import get_db

SUPPORTED = {'.pdf', '.docx', '.pptx', '.txt'}

# Eaststone controlled-document convention, e.g.
# ES.SOP.001.V10 - Writing of Standard Operating Procedures & Forms.pdf
# ES.SOP.003.V07 - Eaststone Site Induction.pdf
EASTSTONE_PATTERN = re.compile(
    r'(?i)^(?P<ref>ES\.[A-Z]+\.\d{3}(?:\.[A-Z]\d{2})?)\.(?P<rev>V\d{2,3})\s*-\s*(?P<title>.+)$'
)

REV_PATTERNS = [
    re.compile(r'(?i)^(?P<ref>.+?)[ _-]+(?:rev(?:ision)?|ver(?:sion)?|v)[ _-]?(?P<rev>[A-Za-z0-9.]+)$'),
    re.compile(r'(?i)^(?P<ref>[A-Za-z0-9._-]+?)[ _-]+(?P<rev>\d{2,4})$'),
]


def _hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _natural_revision_key(value):
    """Sort common revisions naturally: V01 < V02 < V10 and A1 < A2."""
    parts = re.split(r'(\d+)', str(value or ''))
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def parse_document_filename(path):
    """Return (reference, revision, title) from an approved document filename.

    Eaststone SOP filenames are parsed first so the master record is clean and stable.
    A safe generic fallback is retained for other controlled document types.
    """
    stem = path.stem.strip()

    match = EASTSTONE_PATTERN.match(stem)
    if match:
        return (
            match.group('ref').upper(),
            match.group('rev').upper(),
            match.group('title').strip(),
        )

    for pattern in REV_PATTERNS:
        match = pattern.match(stem)
        if match:
            reference = match.group('ref').strip(' _-')
            revision = match.group('rev').strip()
            return reference, revision, reference

    # If a filename does not contain an explicit revision, its modified time is used
    # as the ordering fallback. QA can correct metadata in Document Control.
    return stem, str(int(path.stat().st_mtime)), stem


def parse_filename(path):
    """Compatibility wrapper used by older callers/tests."""
    reference, revision, _title = parse_document_filename(path)
    return reference, revision


def _latest_candidates(root):
    """Return one latest file per parsed document reference.

    Approved folders often retain old revisions. We group by stable reference and choose the
    highest natural revision; modified time breaks ties. This prevents an older retained file
    from superseding the current revision on a later scan.
    """
    grouped = {}
    scanned = 0
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED):
        scanned += 1
        reference, revision, title = parse_document_filename(path)
        candidate = (path, revision, title)
        existing = grouped.get(reference)
        if existing is None:
            grouped[reference] = candidate
            continue
        old_path, old_revision, _old_title = existing
        new_key = (_natural_revision_key(revision), path.stat().st_mtime)
        old_key = (_natural_revision_key(old_revision), old_path.stat().st_mtime)
        if new_key > old_key:
            grouped[reference] = candidate
    return scanned, grouped


def _audit(db, actor_user_id, action, entity_type, entity_id, details):
    db.execute(
        '''INSERT INTO audit_log(user_id,action,entity_type,entity_id,details,ip_address)
           VALUES(?,?,?,?,?,NULL)''',
        (actor_user_id, action, entity_type, entity_id, details),
    )


def sync_approved_folder(root=None, actor_user_id=None):
    configured_root = root or current_app.config.get('APPROVED_DOCS_ROOT') or ''
    if not configured_root:
        return {'configured': False, 'scanned': 0, 'created': 0, 'updated': 0,
                'unchanged': 0, 'ignored_old_revisions': 0, 'errors': []}

    root = Path(configured_root)
    if not root.exists() or not root.is_dir():
        return {'configured': False, 'root': str(root), 'scanned': 0, 'created': 0,
                'updated': 0, 'unchanged': 0, 'ignored_old_revisions': 0, 'errors': []}

    db = get_db()
    upload_dir = Path(current_app.instance_path) / current_app.config['UPLOAD_FOLDER']
    upload_dir.mkdir(parents=True, exist_ok=True)

    scanned, candidates = _latest_candidates(root)
    result = {
        'configured': True,
        'root': str(root),
        'scanned': scanned,
        'selected_current_files': len(candidates),
        'ignored_old_revisions': max(0, scanned - len(candidates)),
        'created': 0,
        'updated': 0,
        'unchanged': 0,
        'errors': [],
    }

    for reference, (path, revision, title) in sorted(candidates.items()):
        try:
            digest = _hash(path)
            stat = path.stat()
            sop = db.execute(
                'SELECT * FROM sops WHERE reference=? ORDER BY active DESC,id LIMIT 1',
                (reference,),
            ).fetchone()
            source = db.execute(
                'SELECT * FROM document_sources WHERE sop_id=?', (sop['id'],)
            ).fetchone() if sop else None

            if source and source['source_hash'] == digest and sop['current_revision'] == revision:
                db.execute(
                    '''UPDATE document_sources SET source_path=?,source_mtime=?,source_size=?,
                       last_seen_at=CURRENT_TIMESTAMP WHERE id=?''',
                    (str(path), stat.st_mtime, stat.st_size, source['id']),
                )
                # Keep title aligned with the approved filename even when the file itself is unchanged.
                if title and sop['title'] != title:
                    db.execute(
                        'UPDATE sops SET title=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                        (title, sop['id']),
                    )
                result['unchanged'] += 1
                continue

            if sop is None:
                cur = db.execute(
                    '''INSERT INTO sops(reference,title,category,sop_type,current_revision,active)
                       VALUES(?,?,?,'Controlled Document',?,1)''',
                    (reference, title or reference, 'Approved SOPs', revision),
                )
                sop_id = cur.lastrowid
                result['created'] += 1
                action = 'SYNC_CREATE_CONTROLLED_DOCUMENT'
            else:
                sop_id = sop['id']
                result['updated'] += 1
                action = 'SYNC_NEW_APPROVED_REVISION'

            stored = f'{uuid.uuid4().hex}{path.suffix.lower()}'
            shutil.copy2(path, upload_dir / stored)

            db.execute(
                "UPDATE sop_versions SET status='SUPERSEDED' WHERE sop_id=? AND status='ACTIVE'",
                (sop_id,),
            )
            db.execute(
                '''INSERT INTO sop_versions(sop_id,revision,original_name,stored_name,content_type,
                           file_size,status,uploaded_by)
                   VALUES(?,?,?,?,?,?, 'ACTIVE', ?)''',
                (sop_id, revision, path.name, stored, mimetypes.guess_type(path.name)[0],
                 stat.st_size, actor_user_id),
            )
            db.execute(
                '''UPDATE sops SET title=?,current_revision=?,updated_at=CURRENT_TIMESTAMP,active=1
                   WHERE id=?''',
                (title or reference, revision, sop_id),
            )
            db.execute(
                '''INSERT INTO document_sources(sop_id,source_path,source_mtime,source_size,source_hash,last_seen_at)
                   VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(sop_id) DO UPDATE SET source_path=excluded.source_path,
                     source_mtime=excluded.source_mtime,source_size=excluded.source_size,
                     source_hash=excluded.source_hash,last_seen_at=CURRENT_TIMESTAMP''',
                (sop_id, str(path), stat.st_mtime, stat.st_size, digest),
            )

            # A newly effective approved revision requires retraining for all current assignees.
            assignees = db.execute(
                'SELECT employee_id FROM employee_assignments WHERE sop_id=? AND active=1',
                (sop_id,),
            ).fetchall()
            for row in assignees:
                db.execute(
                    '''INSERT INTO training_records(employee_id,sop_id,status)
                       VALUES(?,?,'OUTSTANDING')
                       ON CONFLICT(employee_id,sop_id) DO UPDATE SET status='OUTSTANDING',
                         completion_date=NULL,expiry_date=NULL,revision_completed=NULL,
                         updated_at=CURRENT_TIMESTAMP''',
                    (row['employee_id'], sop_id),
                )

            _audit(
                db, actor_user_id, action, 'sop', sop_id,
                f'reference={reference}; revision={revision}; title={title}; source={path}; '
                f'assignees_reset={len(assignees)}',
            )
        except Exception as exc:
            result['errors'].append({'file': str(path), 'error': str(exc)})

    db.commit()
    return result
