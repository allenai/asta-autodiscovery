from flask import Blueprint, current_app, jsonify, request
from utils.auth import AuthConfigError, get_auth_provider


def create() -> Blueprint:
    """Auth endpoints shared across providers.

    - GET  /api/auth/config : non-secret descriptor the UI uses to pick its login UI
    - POST /api/auth/login  : password login (password_file provider only)
    """
    api = Blueprint("auth_api", __name__)

    @api.route("/config")
    def config():  # pyright: ignore reportUnusedFunction
        try:
            return jsonify(get_auth_provider().public_config())
        except Exception as e:
            current_app.logger.error(f"Failed to build auth config: {str(e)}")
            return jsonify({"error": "Auth provider misconfigured"}), 500

    @api.route("/login", methods=["POST"])
    def login():  # pyright: ignore reportUnusedFunction
        body = request.get_json(silent=True) or {}
        username = body.get("username")
        password = body.get("password")
        if not username or not password:
            return jsonify({"error": "username and password are required"}), 400

        provider = get_auth_provider()
        try:
            result = provider.login_with_password(username, password)
        except NotImplementedError:
            return jsonify({"error": "Password login is not enabled"}), 404
        except AuthConfigError as e:
            # e.g. AUTH_PASSWORD_FILE / AUTH_SESSION_SECRET not configured.
            current_app.logger.error(f"Auth misconfigured during login: {e}")
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            current_app.logger.error(f"Login failed unexpectedly: {e}", exc_info=True)
            return jsonify({"error": "Login failed due to a server error"}), 500

        if result is None:
            return jsonify({"error": "Invalid username or password"}), 401
        return jsonify(result), 200

    return api
