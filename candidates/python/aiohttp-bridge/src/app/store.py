from __future__ import annotations

import asyncio
from app.models import TelemetryEnvelope


class InMemoryTelemetryStore:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.drone_models: dict[str, str] = {}
        self.latest_telemetry: dict[str, TelemetryEnvelope] = {}

    async def register_drone(self, drone_id: str, model: str) -> None:
        async with self._lock:
            self.drone_models[drone_id] = model

    async def record_telemetry(self, telemetry: TelemetryEnvelope) -> None:
        async with self._lock:
            self.latest_telemetry[telemetry.drone_id] = telemetry
            if telemetry.drone_id not in self.drone_models:
                self.drone_models[telemetry.drone_id] = ""

    async def list_active_drones(self) -> list[str]:
        async with self._lock:
            return sorted(list(self.drone_models.keys()))

    async def latest_telemetry_for_drone(self, drone_id: str) -> TelemetryEnvelope | None:
        async with self._lock:
            return self.latest_telemetry.get(drone_id)
