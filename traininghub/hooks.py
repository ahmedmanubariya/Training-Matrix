from flask import Blueprint, request

from .alerts import send_or_queue
from .compliance_service import refresh_department, refresh_employee_statuses
from .routes import manager_department, user

bp = Blueprint('hooks', __name__)


@bp.before_app_request
def refresh_compliance_before_dashboards():
    """Keep compliance statuses current without relying on manual spreadsheet checks."""
    if request.endpoint not in {'main.my_training', 'main.dashboard'}:
        return
    current = user()
    if not current:
        return

    if request.endpoint == 'main.my_training' and current['access_role'] == 'staff' and current['employee_id']:
        refresh_employee_statuses(current['employee_id'])
        send_or_queue(current['employee_id'])
        return

    if request.endpoint == 'main.dashboard' and current['access_role'] == 'admin':
        refresh_department(None)
    elif request.endpoint == 'main.dashboard' and current['access_role'] == 'manager':
        refresh_department(manager_department(current))
