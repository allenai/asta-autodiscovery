import os
import random

import requests
from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest

from demo.auth import requires_auth


def create() -> Blueprint:
    """This function is called by Skiff to create your application's API. You can
    code to initialize things at startup here.
    """
    api = Blueprint("api", __name__)

    # This tells the machinery that powers Skiff (Kubernetes) that your application
    # is ready to receive traffic. Returning a non 200 response code will prevent the
    # application from receiving live requests.
    @api.route("/")
    def index() -> tuple[str, int]:  # pyright: ignore reportUnusedFunction
        return "", 204

    # The route below is an example API route. You can delete it and add your own.
    @api.route("/api/solve", methods=["POST"])
    def solve():  # pyright: ignore reportUnusedFunction
        data = request.json
        if data is None:
            raise BadRequest("No request body")

        question = data.get("question")
        if question is None or len(question.strip()) == 0:
            raise BadRequest("Please enter a question.")

        choices = data.get("choices", [])
        if len(choices) == 0:
            raise BadRequest("Please enter at least one choice.")

        random.seed()
        selected = random.choice(choices)
        score = random.random()

        # Logs are persisted by 30 days. If you need to persist logs for longer, see:
        # https://***REMOVED***/logging.html
        answer = {"answer": selected, "score": score}
        entry = {"message": "Returning Answer", "event": "answer", "answer": answer}
        current_app.logger.info(entry)

        return jsonify(answer)

    # Example protected endpoint - requires special permission
    @api.route("/api/enrollment-status")
    @requires_auth(
        required_permission=os.environ.get("AUTH0_REQUIRED_PERMISSION", "enroll:autodiscovery_v0")
    )
    def enrollment_status():  # pyright: ignore reportUnusedFunction
        """
        Example endpoint that requires the enroll:autodiscovery_v0 permission.
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

    # API endpoint - returns user info if authenticated
    @api.route("/api/user")
    @requires_auth(
        required_permission=os.environ.get("AUTH0_REQUIRED_PERMISSION", "enroll:autodiscovery_v0")
    )
    def api_user():  # pyright: ignore reportUnusedFunction
        auth0_domain = os.environ.get("AUTH0_DOMAIN")

        # The access token only has basic claims, so fetch full user info from /userinfo endpoint
        token = request.headers.get("Authorization").split()[1]

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

    return api
