import logging

from pythonjsonlogger import jsonlogger


class Formatter(jsonlogger.JsonFormatter):
    """Custom log formatter that emits log messages as JSON, with the "severity" field
    which Google Cloud uses to differentiate message levels.
    """

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["severity"] = record.levelname
        userid = getattr(record, "userid", None)
        if userid:
            log_record.setdefault("logging.googleapis.com/labels", {})["userid"] = userid


class Handler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        self.setFormatter(Formatter())
