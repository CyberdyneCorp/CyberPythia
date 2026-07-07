"""Consistent JSON error model (spec: rest-api).

Every error response has the shape:
    {"error": {"code": "...", "message": "...", "correlation_id": "..."}}
"""

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class UnauthenticatedError(ApiError):
    status_code = 401
    code = "unauthenticated"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class UpstreamUnavailableError(ApiError):
    status_code = 503
    code = "upstream_unavailable"


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "correlation_id": uuid.uuid4().hex}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", str(exc.errors()[:3])),
        )
