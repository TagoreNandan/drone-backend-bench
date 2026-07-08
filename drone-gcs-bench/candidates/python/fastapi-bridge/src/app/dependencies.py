"""Dependency providers for FastAPI routes."""

from __future__ import annotations

from starlette.requests import HTTPConnection

from app.service import BenchmarkService


def get_service(connection: HTTPConnection) -> BenchmarkService:
    return connection.app.state.service
