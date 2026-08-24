from flask import Blueprint, request

from .alerts import send_or_queue
from .routes import user

bp = Blueprint('hooks', __name__)


@bp.before_app_request
def check_staff_compliance_on_dashboard():
    """Create/send the below-threshold alert when staff enter My Training.

    The alert engine de-duplicates alerts for 24 hours, so refreshing the page
    does not continuously email the same employee.
    """
    if request.endpoint != 'main.my_training':
        return
    current = user()
    if current and current['access_role'] == 'staff' and current['employee_id']:
        send_or_queue(current['employee_id'])
