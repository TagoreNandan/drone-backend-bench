"""Service layer for benchmark business logic."""

from __future__ import annotations

import time

from fastapi import WebSocket, WebSocketDisconnect

from app.metrics import MetricsRegistry
from app.models import (
    DroneListResponse,
    DroneRegistrationRequest,
    DroneRegistrationResponse,
    HealthResponse,
    StatusOkResponse,
    TelemetryEnvelope,
    TelemetryWebSocketMessage,
)
from app.store import InMemoryTelemetryStore
from app.websocket_manager import WebSocketManager


class BenchmarkService:
    def __init__(
        self,
        store: InMemoryTelemetryStore,
        ws_manager: WebSocketManager,
        metrics: MetricsRegistry,
    ) -> None:
        self._store = store
        self._ws_manager = ws_manager
        self._metrics = metrics

    async def register_drone(
        self, payload: DroneRegistrationRequest
    ) -> DroneRegistrationResponse:
        await self._store.register_drone(payload.drone_id, payload.model)
        return DroneRegistrationResponse(drone_id=payload.drone_id)

    async def ingest_telemetry(self, payload: TelemetryEnvelope) -> StatusOkResponse:
        started_ns = time.perf_counter_ns()
        await self._store.record_telemetry(payload)
        message = TelemetryWebSocketMessage(
            drone_id=payload.drone_id,
            seq=payload.seq,
            timestamp=payload.timestamp,
            payload=payload.payload,
        )
        await self._ws_manager.broadcast(message.model_dump_json().encode("utf-8"))
        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        self._metrics.record_telemetry_ingest(elapsed_ms)
        return StatusOkResponse()

    async def list_drones(self) -> DroneListResponse:
        return DroneListResponse(drones=await self._store.list_active_drones())

    def health(self) -> HealthResponse:
        return HealthResponse()

    async def handle_websocket(self, websocket: WebSocket) -> None:
        connection_id = await self._ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive()
        except WebSocketDisconnect:
            pass
        finally:
            await self._ws_manager.disconnect(connection_id)
