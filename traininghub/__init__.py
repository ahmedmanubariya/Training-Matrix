from flask import Flask

from .db import init_app
from .routes import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="development-only-change-me",
        DATABASE="traininghub.db",
        UPLOAD_FOLDER="uploads",
        ALERT_THRESHOLD=80,
    )
    if test_config:
        app.config.update(test_config)

    init_app(app)
    app.register_blueprint(bp)
    return app
