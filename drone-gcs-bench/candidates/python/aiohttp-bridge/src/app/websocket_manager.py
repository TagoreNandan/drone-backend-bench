"""Async WebSocket fanout for telemetry events in aiohttp."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field

from aiohttp.web import WebSocketResponse

from app.metrics import MetricsRegistry


@dataclass(slots=True)
class WebSocketConnection:
    websocket: WebSocketResponse
    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=2048))
    sender_task: asyncio.Task[None] | None = None


class WebSocketManager:
    def __init__(self, metrics: MetricsRegistry) -> None:
        self._metrics = metrics
        self._lock = asyncio.Lock()
        self._connections: dict[int, WebSocketConnection] = {}

    async def connect(self, websocket: WebSocketResponse) -> int:
        connection_id = id(websocket)
        connection = WebSocketConnection(websocket=websocket)
        async with self._lock:
            self._connections[connection_id] = connection
            self._metrics.ws_connections_active.inc()
        connection.sender_task = asyncio.create_task(self._sender(connection_id, connection))
        return connection_id

    async def disconnect(self, connection_id: int) -> None:
        await self._remove_connection(connection_id, cancel_sender_task=True)

    async def _remove_connection(self, connection_id: int, *, cancel_sender_task: bool) -> None:
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            if connection is None:
                return
            self._metrics.ws_connections_active.dec()
        if cancel_sender_task and connection.sender_task is not None:
            connection.sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connection.sender_task
        with contextlib.suppress(Exception):
            await connection.websocket.close()

    async def broadcast(self, message: bytes) -> None:
        async with self._lock:
            connections = list(self._connections.values())
        for connection in connections:
            try:
                connection.queue.put_nowait(message)
            except asyncio.QueueFull:
                self._metrics.record_ws_drop()

    async def shutdown(self) -> None:
        async with self._lock:
            connection_ids = list(self._connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id)

    async def _sender(self, connection_id: int, connection: WebSocketConnection) -> None:
        try:
            while True:
                message = await connection.queue.get()
                started_ns = time.perf_counter_ns()
                try:
                    await connection.websocket.send_bytes(message)
                except Exception:
                    self._metrics.record_ws_drop()
                    break
                else:
                    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
                    self._metrics.record_ws_send(elapsed_ms)
        finally:
            await self._remove_connection(connection_id, cancel_sender_task=False)
