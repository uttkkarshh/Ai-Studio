import logging
import logging.config
import os

from app.core.request_context import request_id_context


class RequestIdLogRecordFactory:
    def __init__(self, original_factory):
        self.original_factory = original_factory

    def __call__(self, *args, **kwargs):
        record = self.original_factory(*args, **kwargs)
        record.request_id = request_id_context.get()
        return record


def configure_logging() -> None:
    if not getattr(logging.getLogRecordFactory(), "_has_request_id", False):
        factory = RequestIdLogRecordFactory(logging.getLogRecordFactory())
        factory._has_request_id = True
        logging.setLogRecordFactory(factory)

    configured_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelNamesMapping().get(configured_level, logging.INFO)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "app": {
                "format": "%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "app",
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],
        },
    })
