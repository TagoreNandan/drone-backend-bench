"""Async-safe in-memory telemetry store."""

from __future__ import annotations

import asyncio

from app.models import TelemetryEnvelope


class InMemoryTelemetryStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._drone_models: dict[str, str] = {}
        self._latest_telemetry: dict[str, TelemetryEnvelope] = {}

    async def register_drone(self, drone_id: str, model: str) -> None:
        async with self._lock:
            self._drone_models[drone_id] = model

    async def record_telemetry(self, telemetry: TelemetryEnvelope) -> None:
        async with self._lock:
            self._latest_telemetry[telemetry.drone_id] = telemetry
            self._drone_models.setdefault(telemetry.drone_id, "")

    async def list_active_drones(self) -> list[str]:
        async with self._lock:
            return sorted(self._drone_models.keys())

    async def latest_telemetry(self, drone_id: str) -> TelemetryEnvelope | None:
        async with self._lock:
            return self._latest_telemetry.get(drone_id)
