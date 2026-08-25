import os

from flask import Flask

from .account_admin import bp as account_admin_bp
from .alerts import bp as alerts_bp
from .bootstrap import ensure_admin
from .db import init_app
from .experience import bp as experience_bp
from .hooks import bp as hooks_bp
from .routes import bp
from .sop_admin import bp as sop_admin_bp
from .staff_admin import bp as staff_admin_bp
from .system_admin import bp as system_admin_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'development-only-change-me'),
        DATABASE=os.environ.get('DATABASE', 'traininghub.db'),
        UPLOAD_FOLDER=os.environ.get('UPLOAD_FOLDER', 'uploads'),
        ALERT_THRESHOLD=int(os.environ.get('ALERT_THRESHOLD', '80')),
        APPROVED_DOCS_ROOT=os.environ.get('APPROVED_DOCS_ROOT', ''),
    )
    if test_config:
        app.config.update(test_config)

    init_app(app)
    with app.app_context():
        ensure_admin()
    app.register_blueprint(bp)
    app.register_blueprint(experience_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(account_admin_bp)
    app.register_blueprint(sop_admin_bp)
    app.register_blueprint(staff_admin_bp)
    app.register_blueprint(system_admin_bp)
    app.register_blueprint(hooks_bp)
    return app
