"""Domain exception hierarchy + handlers (design 8.12, 6.1).

Maps domain errors to Phase 6.1 codes/HTTP status. SSE-context errors are emitted
as ``event: error`` by the streaming layer (design 8.12.3).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 400


class Unauthenticated(AppError):
    code = "UNAUTHENTICATED"
    http_status = 401


class Forbidden(AppError):
    code = "FORBIDDEN"
    http_status = 403


class NotFound(AppError):
    code = "RESOURCE_NOT_FOUND"
    http_status = 404


class Conflict(AppError):
    code = "CONFLICT"
    http_status = 409


class ProviderRateLimited(AppError):
    code = "PROVIDER_RATE_LIMIT"
    http_status = 429


class ProviderError(AppError):
    code = "PROVIDER_ERROR"
    http_status = 502


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if isinstance(exc, ProviderRateLimited):
            headers["Retry-After"] = str(exc.details.get("retry_after", 5))
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body("UNPROCESSABLE", "Validation error", {"errors": exc.errors()}),
        )
