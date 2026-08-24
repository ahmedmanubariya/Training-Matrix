import os

from flask import Flask

from .bootstrap import ensure_admin
from .db import init_app
from .routes import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'development-only-change-me'),
        DATABASE=os.environ.get('DATABASE', 'traininghub.db'),
        UPLOAD_FOLDER=os.environ.get('UPLOAD_FOLDER', 'uploads'),
        ALERT_THRESHOLD=int(os.environ.get('ALERT_THRESHOLD', '80')),
    )
    if test_config:
        app.config.update(test_config)

    init_app(app)
    with app.app_context():
        ensure_admin()
    app.register_blueprint(bp)
    return app
