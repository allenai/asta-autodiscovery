from flask import Blueprint, jsonify, request, current_app
from typing import Tuple
from werkzeug.exceptions import BadRequest

import random

def create() -> Blueprint:
    """
    This function is called by Skiff to create your application's API. You can
    code to initialize things at startup here.
    """
    api = Blueprint("api", __name__)

    # This tells the machinery that powers Skiff (Kubernetes) that your application
    # is ready to receive traffic. Returning a non 200 response code will prevent the
    # application from receiving live requests.
    @api.route("/")
    def index() -> Tuple[str, int]: # pyright: ignore reportUnusedFunction
        return "", 204

    # The route below is an example API route. You can delete it and add your own.
    @api.route("/api/solve", methods=["POST"])
    def solve(): # pyright: ignore reportUnusedFunction
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
        answer = { "answer": selected, "score": score }
        entry = { "message": "Returning Answer", "event": "answer", "answer": answer }
        current_app.logger.info(entry)

        return jsonify(answer)

    return api

