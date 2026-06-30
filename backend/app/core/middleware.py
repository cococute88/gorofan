"""Middleware stack (design 8.1.3): request id + structured logging."""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, request_id_ctx

log = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.info(
                f"{request.method} {request.url.path}",
                extra={"duration_ms": duration_ms},
            )
            request_id_ctx.reset(token)
        response.headers["X-Request-Id"] = rid
        return response
