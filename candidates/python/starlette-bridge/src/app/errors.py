from __future__ import annotations

from app.models import ErrorObject, ErrorResponse


def error_response(code: str, message: str) -> ErrorResponse:
    """Helper to construct a standardized error response."""
    return ErrorResponse(error=ErrorObject(code=code, message=message))
