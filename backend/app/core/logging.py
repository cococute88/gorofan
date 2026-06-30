"""Structured JSON logging (design 8.11).

Every line includes request_id. Secrets/plaintext keys/prompt bodies are never
logged (Property 8 / SEC-3).
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("user_id", "duration_ms", "meta"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def init_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str = "app") -> logging.Logger:
    return logging.getLogger(name)
