"""
User ID instrumentation for logging.

Injects the authenticated userid into every log record emitted during a request,
including logs from thread pool workers spawned during that request.

How it works:
- The auth decorators (requires_auth, optional_enrollment) call set_userid() after
  JWT verification and store the reset token in flask.g.
- A teardown_request hook calls clear_userid() to restore clean state on the thread,
  preventing leakage between requests on reused WSGI threads.
- UserIdFilter reads the ContextVar and stamps record.userid on every log record.
- glog.Formatter picks up record.userid and moves it to
  logging.googleapis.com/labels so it is filterable in GCP Logs Explorer as:
      labels.userid="google-oauth2|..."

Thread pool behaviour:
- Python copies the ContextVar snapshot into each submitted task at submit() time,
  so thread pool workers spawned during a request (credits.py, runs_api.py,
  experiments.py) inherit the userid automatically with no extra work.
- Each task gets an independent copy, so there is no cross-pollution between
  concurrent requests sharing the same pool.
- The background metrics aggregator thread runs outside of any request and will
  not have a userid in context, which is intentional.

Usage:
    # In app.py create_app(), after logging.basicConfig():
    from utils import userid_logging
    userid_logging.instrument(app, logging.root)
"""

import logging
from contextvars import ContextVar

_userid_context: ContextVar[str | None] = ContextVar("userid", default=None)


def set_userid(userid: str | None):
    """Set the userid for the current execution context.

    Returns a reset token that must be passed to clear_userid() when the
    context should be cleaned up (i.e. at request teardown).
    """
    return _userid_context.set(userid)


def clear_userid(token) -> None:
    """Restore the userid context to its value before the matching set_userid() call."""
    _userid_context.reset(token)


class UserIdFilter(logging.Filter):
    """Logging filter that stamps record.userid from the current ContextVar value."""

    def filter(self, record):
        userid = _userid_context.get()
        if userid:
            record.userid = userid
        return True


def instrument(app, logger: logging.Logger) -> None:
    """Wire userid logging into a Flask app and logger.

    Registers a teardown_request hook that clears the userid context after each
    request, and attaches a UserIdFilter to the logger so every log record emitted
    during a request carries the userid.

    The userid itself is set by the auth decorators in utils/auth.py after the JWT
    is verified. This function only handles the filter and cleanup wiring.
    """

    @app.teardown_request
    def _clear_userid_context(exc):
        from flask import g

        token = getattr(g, "_userid_logging_token", None)
        if token is not None:
            clear_userid(token)

    logger.addFilter(UserIdFilter())
