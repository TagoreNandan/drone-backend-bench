"""Starlette application entry point."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
import threading
import asyncio
from pymavlink import mavutil
import msgpack
from dotenv import load_dotenv
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute

from app.errors import error_response
from app.metrics import MetricsRegistry
from app.models import DroneRegistrationRequest, TelemetryEnvelope
from app.store import InMemoryTelemetryStore
from app.websocket_manager import WebSocketManager

load_dotenv()

metrics = MetricsRegistry()
store = InMemoryTelemetryStore()
ws_manager = WebSocketManager(metrics)


def start_mavlink_listener(port: int, ws_manager: WebSocketManager, metrics: MetricsRegistry, loop: asyncio.AbstractEventLoop):
    print(f"Starting MAVLink UDP listener on port {port}", flush=True)
    try:
        conn = mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}")
    except Exception as e:
        print(f"Error starting MAVLink UDP listener: {e}", flush=True)
        return

    while True:
        try:
            msg = conn.recv_match(blocking=True, timeout=1.0)
            if msg is None:
                continue
            
            msg_type = msg.get_type()
            if msg_type not in ("HEARTBEAT", "ATTITUDE", "GLOBAL_POSITION_INT", "SYS_STATUS"):
                continue

            started_ns = time.perf_counter_ns()
            
            data = {
                "message_type": msg_type,
                "sysid": msg.get_srcSystem(),
                "compid": msg.get_srcComponent()
            }

            if msg_type == "HEARTBEAT":
                data.update({
                    "type": msg.type,
                    "autopilot": msg.autopilot,
                    "system_status": msg.system_status
                })
            elif msg_type == "ATTITUDE":
                data.update({
                    "time_boot_ms": msg.time_boot_ms,
                    "roll": msg.roll,
                    "pitch": msg.pitch,
                    "yaw": msg.yaw
                })
            elif msg_type == "GLOBAL_POSITION_INT":
                data.update({
                    "lat": msg.lat,
                    "lon": msg.lon,
                    "alt": msg.alt,
                    "relative_alt": msg.relative_alt
                })
            elif msg_type == "SYS_STATUS":
                data.update({
                    "battery_remaining": msg.battery_remaining,
                    "voltage_battery": msg.voltage_battery,
                    "current_battery": msg.current_battery
                })

            payload = msgpack.packb(data)
            elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            metrics.record_telemetry_decode(elapsed_ms)

            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast(payload),
                loop
            )
        except Exception as e:
            print(f"Error decoding MAVLink: {e}", flush=True)
            time.sleep(1)

load_dotenv()

metrics = MetricsRegistry()
store = InMemoryTelemetryStore()
ws_manager = WebSocketManager(metrics)


class ASGIMetricsMiddleware:
    def __init__(self, app, metrics_registry: MetricsRegistry) -> None:
        self.app = app
        self.metrics = metrics_registry

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_ns = time.perf_counter_ns()
        status_code = [200]

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        self.metrics.record_http_request(
            route=scope.get("path", ""),
            method=scope.get("method", "GET"),
            status=str(status_code[0]),
            duration_ms=duration_ms,
        )


async def health(request):
    return JSONResponse({"status": "ok"})


async def get_metrics(request):
    return Response(
        metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


async def ws_telemetry(websocket):
    conn_id = await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_bytes()
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(conn_id)


@asynccontextmanager
async def lifespan(app: Starlette):
    port = int(os.getenv("MAVLINK_PORT", "14550"))
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=start_mavlink_listener,
        args=(port, ws_manager, metrics, loop),
        daemon=True
    )
    thread.start()
    try:
        yield
    finally:
        await ws_manager.shutdown()


routes = [
    Route("/api/v1/health", health, methods=["GET"]),
    Route("/metrics", get_metrics, methods=["GET"]),
    WebSocketRoute("/ws/telemetry", ws_telemetry),
    WebSocketRoute("/api/v1/ws/telemetry", ws_telemetry),
]

app = Starlette(
    routes=routes,
    middleware=[Middleware(ASGIMetricsMiddleware, metrics_registry=metrics)],
    lifespan=lifespan,
)

if __name__ == "__main__":
    import uvicorn

    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
    )
