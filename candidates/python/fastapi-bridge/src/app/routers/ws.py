"""WebSocket routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket

from app.dependencies import get_service
from app.service import BenchmarkService

router = APIRouter(tags=["ws"])


@router.websocket("/ws/telemetry")
@router.websocket("/api/v1/ws/telemetry")
async def telemetry_socket(
    websocket: WebSocket,
    service: BenchmarkService = Depends(get_service),
) -> None:
    await service.handle_websocket(websocket)
