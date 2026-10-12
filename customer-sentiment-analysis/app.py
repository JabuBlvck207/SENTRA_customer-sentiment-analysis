"""
Customer Sentiment Analysis System
Main Flask application entry point.
"""

import os
import logging
from pathlib import Path

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.exceptions import RequestEntityTooLarge

from backend.database import init_db
from backend.routes import api

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(
        __name__,
        static_folder="frontend",
        static_url_path="",
    )

    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
    max_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    app.config["MAX_UPLOAD_SIZE_MB"] = max_mb
    app.config["MAX_CONTENT_LENGTH"] = max_mb * 1024 * 1024

    # Ensure folders exist
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path("instance").mkdir(parents=True, exist_ok=True)

    # CORS for local development (frontend served by same origin in production)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register API
    app.register_blueprint(api)

    # Initialise database
    init_db()
    logger.info("Database initialised.")

    # ---------- Frontend routes ----------

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def static_proxy(path):
        # Serve static assets; fall back to index for SPA-style navigation
        full = Path(app.static_folder) / path
        if full.is_file():
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    # ---------- Error handlers ----------

    @app.errorhandler(404)
    def not_found(e):
        if request_wants_json():
            return jsonify({"success": False, "error": "Not found"}), 404
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(413)
    @app.errorhandler(RequestEntityTooLarge)
    def too_large(e):
        return jsonify({
            "success": False,
            "error": f"File too large. Maximum size is {app.config['MAX_UPLOAD_SIZE_MB']} MB.",
        }), 413

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Unhandled server error")
        return jsonify({"success": False, "error": "Internal server error"}), 500

    def request_wants_json():
        from flask import request
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        return (
            best == "application/json"
            and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    logger.info("Starting Customer Sentiment Analysis on port %s (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
