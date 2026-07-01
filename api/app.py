import logging
import os

from admin import admin_ui, jobs_api
from auth import auth_api
from flask import Flask
from metrics import metrics_api
from root import root_api
from runs import runs_api
from user import user_api
from utils import error, glog, userid_logging
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app() -> ProxyFix:
    # If LOG_FORMAT is "google:json" emit log message as JSON in a format Google Cloud can parse.
    fmt = os.getenv("LOG_FORMAT")
    handlers = [glog.Handler()] if fmt == "google:json" else []
    level = os.environ.get("LOG_LEVEL", default=logging.INFO)
    logging.basicConfig(level=level, handlers=handlers, force=True)
    logging.root.setLevel(level)

    app = Flask("api")
    userid_logging.instrument(app, logging.root)
    app.register_blueprint(root_api.create(), url_prefix="/")
    app.register_blueprint(auth_api.create(), url_prefix="/api/auth")
    app.register_blueprint(user_api.create(), url_prefix="/api/user")
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")
    app.register_blueprint(admin_ui.create(), url_prefix="/api/admin")
    app.register_blueprint(jobs_api.create(), url_prefix="/api/admin/jobs")
    app.register_blueprint(metrics_api.create(), url_prefix="/api/metrics")
    app.register_error_handler(HTTPException, error.handle)

    # Use the X-Forwarded-* headers to set the request IP, host and port. Technically there
    # are two reverse proxies in deployed environments, but we "hide" the reverse proxy deployed
    # as a sibling of the API by forwarding the X-Forwarded-* headers rather than chaining them.
    return ProxyFix(app, x_for=1, x_proto=1, x_host=1, x_port=1)
