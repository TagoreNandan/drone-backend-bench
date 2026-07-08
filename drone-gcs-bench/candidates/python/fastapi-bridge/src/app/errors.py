"""Error helpers for strict benchmark responses."""

from __future__ import annotations

from app.models import ErrorObject, ErrorResponse


def error_response(code: str, message: str) -> ErrorResponse:
    return ErrorResponse(error=ErrorObject(code=code, message=message))
