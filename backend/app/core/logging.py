"""Structured logging. Never log secrets, passwords, tokens or camera credentials."""
import logging
import re
import sys

_SECRET_PATTERNS = [
    (re.compile(r"(rtsps?://)([^:@/\s]+):([^@/\s]+)@", re.I), r"\1***:***@"),
    (re.compile(r"(password|token|secret|authorization)(\"?\s*[=:]\s*\"?)([^\s\",&]+)", re.I), r"\1\2***"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, repl in _SECRET_PATTERNS:
            msg = pattern.sub(repl, msg)
        record.msg, record.args = msg, ()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
