import time

from flask import Blueprint, current_app, redirect, request, url_for

from .alerts import send_or_queue
from .compliance_service import refresh_department, refresh_employee_statuses
from .document_sync import sync_approved_folder
from .experience import effective_role
from .routes import manager_department, user

bp = Blueprint('hooks', __name__)
_last_document_sync = 0.0


@bp.before_app_request
def portal_landing_page():
    """Every authenticated account lands on its own personal compliance overview."""
    if request.endpoint == 'main.home' and user():
        return redirect(url_for('experience.overview'))


@bp.before_app_request
def automatic_approved_document_sync():
    """Periodically compare the configured Approved SOPs folder with the application library.

    The deployed server must be able to read APPROVED_DOCS_ROOT. A changed approved file is
    copied into immutable application version storage, the previous version is superseded,
    and active assignees are reset to outstanding for the new revision.
    """
    global _last_document_sync
    root = current_app.config.get('APPROVED_DOCS_ROOT')
    if not root:
        return
    interval = int(current_app.config.get('APPROVED_DOCS_SYNC_SECONDS', 300))
    now = time.monotonic()
    if now - _last_document_sync < interval:
        return
    _last_document_sync = now
    try:
        sync_approved_folder(root=root, actor_user_id=None)
    except Exception:
        # A temporarily unavailable network drive must not prevent users logging in.
        current_app.logger.exception('Approved document folder sync failed')


@bp.before_app_request
def refresh_compliance_before_dashboards():
    """Keep compliance statuses and below-80% alerts current without spreadsheet checks."""
    endpoints = {
        'main.my_training', 'main.dashboard', 'experience.overview',
        'experience.controlled_documents', 'experience.document',
    }
    if request.endpoint not in endpoints:
        return
    current = user()
    if not current:
        return

    if current['employee_id'] and request.endpoint in {
        'main.my_training', 'experience.overview', 'experience.controlled_documents',
        'experience.document',
    }:
        refresh_employee_statuses(current['employee_id'])
        send_or_queue(current['employee_id'])

    if request.endpoint == 'main.dashboard':
        role = effective_role(current)
        if role in ('qa', 'admin'):
            refresh_department(None)
        elif role == 'manager':
            refresh_department(manager_department(current))
