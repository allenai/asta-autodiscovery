
from flask import Blueprint


def create() -> Blueprint:
    """This function is called by Skiff to create your application's API. You can
    code to initialize things at startup here.
    """
    api = Blueprint("root_api", __name__)

    # This tells the machinery that powers Skiff (Kubernetes) that your application
    # is ready to receive traffic. Returning a non 200 response code will prevent the
    # application from receiving live requests.
    @api.route("/")
    @api.route("/api")
    def index() -> tuple[str, int]:  # pyright: ignore reportUnusedFunction
        return "", 204

    return api
