import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import text


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .config import Config
from .extensions import db
from .markdown_utils import render_markdown


def _configure_logging(app):
    app.config["LOG_FOLDER"].mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        app.config["LOG_FOLDER"] / "app.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _initialize_database(app):
    last_error = None
    for attempt in range(1, 11):
        try:
            with app.app_context():
                db.session.execute(text("SELECT 1"))
                db.create_all()
                _upgrade_mysql_columns()
                db.session.commit()
            app.logger.info("Base de données prête.")
            return
        except Exception as exc:
            last_error = exc
            try:
                db.session.rollback()
            except Exception:
                pass
            if attempt < 10:
                time.sleep(2)
    app.logger.error("Base de données indisponible au démarrage: %s", last_error)


def _upgrade_mysql_columns():
    """Apply small, idempotent schema upgrades for existing Docker volumes."""
    if db.engine.dialect.name != "mysql":
        return
    attachment_type = db.session.execute(
        text(
            "SELECT DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'messages' "
            "AND COLUMN_NAME = 'attachment_text'"
        )
    ).scalar()
    if attachment_type != "mediumtext":
        db.session.execute(
            text("ALTER TABLE messages MODIFY COLUMN attachment_text MEDIUMTEXT NULL")
        )

    confidence_column = db.session.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'messages' "
            "AND COLUMN_NAME = 'confidence_segments'"
        )
    ).scalar()
    if not confidence_column:
        db.session.execute(
            text("ALTER TABLE messages ADD COLUMN confidence_segments JSON NULL")
        )


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    _configure_logging(app)
    app.jinja_env.filters["markdown"] = render_markdown

    from .routes import bp
    from .errors import register_error_handlers

    app.register_blueprint(bp)
    register_error_handlers(app)

    if not app.config.get("TESTING"):
        _initialize_database(app)
    else:
        with app.app_context():
            db.create_all()

    return app
