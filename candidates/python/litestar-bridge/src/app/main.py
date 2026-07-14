"""Litestar application entry point."""

from __future__ import annotations

from typing import Annotated

import os
import time
import threading
import asyncio
from pymavlink import mavutil
import msgpack
from dotenv import load_dotenv

from litestar import Litestar, Request, Response, get, post, websocket
from litestar.config.cors import CORSConfig
from litestar.connection import WebSocket
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide
from litestar.exceptions import HTTPException, ValidationException
from litestar.types import ASGIApp, Receive, Scope, Send
from pydantic import ValidationError

from app.errors import error_response
from app.metrics import MetricsRegistry
from app.models import (
    DroneListResponse,
    DroneRegistrationRequest,
    DroneRegistrationResponse,
    HealthResponse,
    StatusOkResponse,
    TelemetryEnvelope,
)
from app.service import BenchmarkService
from app.store import InMemoryTelemetryStore
from app.websocket_manager import WebSocketManager

load_dotenv()


def start_mavlink_listener(conn, ws_manager: WebSocketManager, metrics: MetricsRegistry, loop: asyncio.AbstractEventLoop, shutdown_event: threading.Event):
    print("Starting MAVLink UDP listener loop", flush=True)
    while not shutdown_event.is_set():
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
            if shutdown_event.is_set():
                break
            print(f"Error decoding MAVLink: {e}", flush=True)
            time.sleep(1)


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_ns = time.perf_counter_ns()
        status_code = 500

        async def send_wrapper(message: Send) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            route_handler = scope.get("route_handler")
            if route_handler and hasattr(route_handler, "paths") and route_handler.paths:
                paths = list(route_handler.paths)
                route_path = paths[0] if paths else scope.get("path", "")
            else:
                route_path = scope.get("path", "")

            app_instance = scope.get("app")
            if app_instance and hasattr(app_instance, "state") and hasattr(app_instance.state, "metrics"):
                app_instance.state.metrics.record_http_request(
                    route=route_path,
                    method=scope["method"],
                    status=str(status_code),
                    duration_ms=duration_ms,
                )


def get_service(state: State) -> BenchmarkService:
    return state.service


@get("/api/v1/health")
async def health(service: NamedDependency[BenchmarkService]) -> HealthResponse:
    return service.health()


@post("/api/v1/drones/register", status_code=200)
async def register_drone(
    data: DroneRegistrationRequest,
    service: NamedDependency[BenchmarkService],
) -> DroneRegistrationResponse:
    return await service.register_drone(data)


@post("/api/v1/telemetry", status_code=200)
async def ingest_telemetry(
    data: TelemetryEnvelope,
    service: NamedDependency[BenchmarkService],
) -> StatusOkResponse:
    return await service.ingest_telemetry(data)


@get("/api/v1/drones")
async def list_drones(
    service: NamedDependency[BenchmarkService],
) -> DroneListResponse:
    return await service.list_drones()


@websocket("/ws/telemetry")
async def telemetry_socket(
    socket: WebSocket,
    service: NamedDependency[BenchmarkService],
) -> None:
    await service.handle_websocket(socket)


@websocket("/api/v1/ws/telemetry")
async def telemetry_socket_v1(
    socket: WebSocket,
    service: NamedDependency[BenchmarkService],
) -> None:
    await service.handle_websocket(socket)


@get("/metrics", include_in_schema=False)
async def metrics_handler(state: State) -> Response[str]:
    return Response(
        state.metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def validation_exception_handler(request: Request, exc: Exception) -> Response:
    return Response(
        content=error_response("INVALID_REQUEST", str(exc)).model_dump(),
        status_code=400,
        media_type="application/json",
    )


def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> Response:
    return Response(
        content=error_response("INVALID_REQUEST", str(exc)).model_dump(),
        status_code=400,
        media_type="application/json",
    )


def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    return Response(
        content=error_response("HTTP_ERROR", exc.detail).model_dump(),
        status_code=exc.status_code,
        media_type="application/json",
    )


def generic_exception_handler(request: Request, exc: Exception) -> Response:
    return Response(
        content=error_response("INTERNAL_ERROR", "Internal error").model_dump(),
        status_code=500,
        media_type="application/json",
    )


async def on_startup(app: Litestar) -> None:
    metrics = MetricsRegistry()
    store = InMemoryTelemetryStore()
    ws_manager = WebSocketManager(metrics)
    service = BenchmarkService(store=store, ws_manager=ws_manager, metrics=metrics)

    app.state.metrics = metrics
    app.state.store = store
    app.state.ws_manager = ws_manager
    app.state.service = service

    port = int(os.getenv("MAVLINK_PORT", "14550"))
    shutdown_event = threading.Event()
    app.state.shutdown_event = shutdown_event
    try:
        conn = mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}")
        conn.mav.heartbeat_send(0, 0, 0, 0, 0)
        app.state.mavlink_conn = conn
    except Exception as e:
        print(f"Error starting MAVLink UDP listener: {e}", flush=True)
        conn = None

    if conn:
        loop = asyncio.get_running_loop()
        thread = threading.Thread(
            target=start_mavlink_listener,
            args=(conn, ws_manager, metrics, loop, shutdown_event),
            daemon=True
        )
        thread.start()


async def on_shutdown(app: Litestar) -> None:
    if hasattr(app.state, "shutdown_event") and app.state.shutdown_event:
        app.state.shutdown_event.set()
    if hasattr(app.state, "mavlink_conn") and app.state.mavlink_conn:
        try:
            app.state.mavlink_conn.close()
        except Exception:
            pass
    if hasattr(app.state, "ws_manager"):
        await app.state.ws_manager.shutdown()


def create_app() -> Litestar:
    cors_config = CORSConfig(allow_origins=["*"])
    return Litestar(
        route_handlers=[
            health,
            register_drone,
            ingest_telemetry,
            list_drones,
            telemetry_socket,
            telemetry_socket_v1,
            metrics_handler,
        ],
        cors_config=cors_config,
        dependencies={"service": Provide(get_service, sync_to_thread=False)},
        middleware=[MetricsMiddleware],
        exception_handlers={
            ValidationException: validation_exception_handler,
            ValidationError: pydantic_validation_exception_handler,
            HTTPException: http_exception_handler,
            Exception: generic_exception_handler,
        },
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
        openapi_config=None,
    )


app = create_app()

if __name__ == "__main__":
    import uvicorn

    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
    )
