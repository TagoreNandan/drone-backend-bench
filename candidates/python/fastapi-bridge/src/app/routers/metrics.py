"""Metrics route."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> PlainTextResponse:
    return PlainTextResponse(
        request.app.state.metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
