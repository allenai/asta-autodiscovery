import os

import requests
from flask import Blueprint, current_app, jsonify, request
from utils.auth import requires_auth, requires_enrollment

# Import autodiscovery_jobs when available
try:
    from autodiscovery_jobs import JobConfig, JobManager
    from autodiscovery_jobs.exceptions import (
        CloudRunError,
        GCSError,
        JobAlreadyExistsError,
        JobNotFoundError,
    )
    from autodiscovery_jobs.gcs import calculate_job_credits

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
                    "sub": user.get("sub"),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "picture": user.get("picture"),
                    "email_verified": user.get("email_verified"),
                }
            )
        except Exception as e:
            current_app.logger.error(f"Failed to fetch user info: {str(e)}")
            return jsonify({"error": f"Failed to fetch user info: {str(e)}"}), 500

    @api.route("/me/credits", methods=["GET"])
    @requires_enrollment
    def get_viewer_credits():
        """Get the number of credits for the authenticated user."""
        user = request.user
        user_id = user.get("sub")

        job_manager = get_job_manager()

        total_credits_used = 0
        total_credits_pending = 0
        viewer_job_ids = job_manager.list_jobs(userid=user_id)

        # Calculate the total credits used by the user across all their jobs
        for job_id in viewer_job_ids:
            try:
                # Calculate credits for this job
                used, pending = calculate_job_credits(userid=user_id,
                                                      jobid=job_id,
                                                      config=job_manager.config)
                total_credits_used += used
                total_credits_pending += pending
                print(f"Job {job_id}: used={used}, pending={pending}")
            except Exception as e:
                current_app.logger.error(f"Failed to calculate credits for job {job_id}: {e}")
                # Continue processing other jobs

        credits_granted = 1000  # TODO: Pull this from some config or DB
        credits_available = max(0, credits_granted - total_credits_used - total_credits_pending)
        credits_remaining = max(0, credits_granted - total_credits_used)
        return jsonify(
            {
                "credits": {
                    "granted": credits_granted,
                    "used": total_credits_used,
                    "pending": total_credits_pending,
                    "available": credits_available,
                    "remaining": credits_remaining,
                }
            }
        ), 200

    # Example protected endpoint - requires special permission
    @api.route("/me/enrollment-status")
    @requires_enrollment
    def enrollment_status():  # pyright: ignore reportUnusedFunction
        """Example endpoint that requires the enroll:autodiscovery_v0 permission.
        Returns enrollment status for the authenticated user.
        """
        user = request.user

        # Example data - in real implementation, this would query a database
        enrollment_data = {
            "enrolled": True,
            "enrollment_date": "2024-01-15",
            "status": "active",
            "experiments_count": 12,
            "user_id": user.get("sub"),
        }

        current_app.logger.info(f"Enrollment status requested by user: {user.get('sub')}")
        return jsonify(enrollment_data)

    return api
