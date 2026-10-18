"""
Logging: our code logs ids, decisions and timestamps only. As a second line
of defence a filter redacts anything that looks like an email address, and
uvicorn access logs have their query strings removed (search terms can be names).
"""

import logging
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        clean = _EMAIL.sub("[email]", msg)
        if clean != msg:
            record.msg, record.args = clean, ()
        return True


class StripQueryFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3 and isinstance(record.args[2], str):
            args = list(record.args)
            args[2] = args[2].split("?", 1)[0]
            record.args = tuple(args)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    redact = RedactFilter()
    for h in root.handlers:
        if not any(isinstance(f, RedactFilter) for f in h.filters):
            h.addFilter(redact)
    for name in ("lifeline", "app"):
        lg = logging.getLogger(name)
        if not any(isinstance(f, RedactFilter) for f in lg.filters):
            lg.addFilter(redact)
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, StripQueryFilter) for f in access.filters):
        access.addFilter(StripQueryFilter())
