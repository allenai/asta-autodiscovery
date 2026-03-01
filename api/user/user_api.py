import os

import requests
from flask import Blueprint, current_app, jsonify, request
from utils.auth import requires_auth, requires_enrollment
from utils.credits import get_user_credits

# Import autodiscovery_jobs when available
try:
    from autodiscovery_jobs import JobConfig, JobManager

    JOBS_AVAILABLE = True
except ImportError:
    JOBS_AVAILABLE = False


def create() -> Blueprint:
    """This function is called by Skiff to create your application's API. You can
    code to initialize things at startup here.
    """
    api = Blueprint("user_api", __name__)

    def get_job_manager() -> JobManager:
        """Get a configured JobManager instance."""
        if not JOBS_AVAILABLE:
            raise RuntimeError("autodiscovery_jobs package not available")

        # Get config from environment or use defaults
        config = JobConfig.from_env()
        return JobManager(config)

    # This tells the machinery that powers Skiff (Kubernetes) that your application
    # is ready to receive traffic. Returning a non 200 response code will prevent the
    # application from receiving live requests.
    @api.route("/")
    def index() -> tuple[str, int]:  # pyright: ignore reportUnusedFunction
        return "", 204

    # API endpoint - returns user info if authenticated (no special permission required)
    @api.route("/me")
    @requires_auth()
    def api_user():  # pyright: ignore reportUnusedFunction
        auth0_domain = os.environ.get("AUTH0_DOMAIN")

        # The access token only has basic claims, so fetch full user info from /userinfo endpoint
        token = request.headers.get("Authorization", "").split()[1]

        try:
            userinfo_url = f"https://{auth0_domain}/userinfo"
            headers = {"Authorization": f"Bearer {token}"}
            userinfo_response = requests.get(userinfo_url, headers=headers)
            userinfo_response.raise_for_status()
            user = userinfo_response.json()

            return jsonify(
                {
                    "user": {
                        "sub": user.get("sub"),
                        "name": user.get("name"),
                        "email": user.get("email"),
                        "picture": user.get("picture"),
                        "email_verified": user.get("email_verified"),
                    },
                }
            )
        except Exception as e:
            current_app.logger.error(f"Failed to fetch user info: {str(e)}")
            return jsonify({"error": f"Failed to fetch user info: {str(e)}"}), 500

    @api.route("/me/credits", methods=["GET"])
    @requires_enrollment
    def get_viewer_credits():
        """Get the number of credits for the authenticated user."""
        user_id = request.user.get("sub")

        try:
            job_manager = get_job_manager()
            user_credits = get_user_credits(userid=user_id, config=job_manager.config)

            return jsonify(
                {
                    "credits": {
                        "granted": user_credits.granted,
                        "consumed": user_credits.consumed,
                        "pending": user_credits.pending,
                        "available": user_credits.available,
                    }
                }
            ), 200
        except Exception as e:
            current_app.logger.error(f"Failed to fetch credits for user {user_id}: {str(e)}")
            return jsonify({"error": f"Failed to fetch credits: {str(e)}"}), 500

    # Example protected endpoint - requires special permission
    @api.route("/me/enrollment-status")
    @requires_enrollment
    def enrollment_status():  # pyright: ignore reportUnusedFunction
        """Example endpoint that requires the enroll:autodiscovery_v0 permission.
        Returns enrollment status for the authenticated user.
        """
        user_id = request.user.get("sub")

        # Example data - in real implementation, this would query a database
        enrollment_data = {
            "enrolled": True,
            "enrollment_date": "2024-01-15",
            "status": "active",
            "experiments_count": 12,
            "user_id": user_id,
        }

        current_app.logger.info(f"Enrollment status requested by user: {user_id}")
        return jsonify(enrollment_data)

    return api
