"""Admin UI blueprint for serving the admin interface."""

import os

from flask import Blueprint, send_from_directory


def create() -> Blueprint:
    """Create the admin UI blueprint."""
    ui = Blueprint("admin_ui", __name__)

    # Get the directory where this file is located, then go to parent/static
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

    @ui.route("/api/admin")
    @ui.route("/api/admin/")
    def admin_page():
        """Serve the admin HTML page."""
        return send_from_directory(static_dir, "admin.html")

    return ui
