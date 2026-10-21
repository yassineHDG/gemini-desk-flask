import traceback

from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from .extensions import db
from .models import ErrorLog


def _save_error(error, status_code):
    try:
        db.session.rollback()
        record = ErrorLog(
            level="ERROR" if status_code >= 500 else "WARNING",
            endpoint=request.path,
            error_type=type(error).__name__,
            message=str(error),
            traceback_text="".join(traceback.format_exception(error)),
        )
        db.session.add(record)
        db.session.commit()
    except Exception:
        db.session.rollback()


def register_error_handlers(app):
    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_file(error):
        _save_error(error, 413)
        message = "Fichier trop volumineux. Vérifiez MAX_UPLOAD_MB dans .env."
        if request.path.startswith("/api/"):
            return jsonify({"error": message}), 413
        return render_template("error.html", status_code=413, message=message), 413

    @app.errorhandler(Exception)
    def handle_exception(error):
        status_code = error.code if isinstance(error, HTTPException) else 500
        _save_error(error, status_code)

        if isinstance(error, HTTPException):
            message = error.description
        else:
            message = "Une erreur interne est survenue. Consultez le journal pour le détail."

        if status_code >= 500:
            app.logger.exception("Erreur sur %s", request.path)
        else:
            app.logger.warning("Erreur HTTP %s sur %s: %s", status_code, request.path, message)

        if request.path.startswith("/api/"):
            return jsonify({"error": message}), status_code
        return render_template("error.html", status_code=status_code, message=message), status_code
