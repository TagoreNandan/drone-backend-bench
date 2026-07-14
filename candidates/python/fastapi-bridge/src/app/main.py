"""FastAPI application entry point."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import threading
from pymavlink import mavutil
import msgpack
import asyncio

from app.errors import error_response
from app.metrics import MetricsRegistry
from app.routers.api import router as api_router
from app.routers.metrics import router as metrics_router
from app.routers.ws import router as ws_router
from app.service import BenchmarkService
from app.store import InMemoryTelemetryStore
from app.websocket_manager import WebSocketManager

load_dotenv()


def start_mavlink_listener(
    conn,
    ws_manager: WebSocketManager,
    metrics: MetricsRegistry,
    loop: asyncio.AbstractEventLoop,
    shutdown_event: threading.Event,
):
    print("Starting MAVLink UDP listener loop", flush=True)
    while not shutdown_event.is_set():
        try:
            msg = conn.recv_match(blocking=True, timeout=1.0)
            if msg is None:
                continue

            msg_type = msg.get_type()
            if msg_type not in (
                "HEARTBEAT",
                "ATTITUDE",
                "GLOBAL_POSITION_INT",
                "SYS_STATUS",
            ):
                continue

            started_ns = time.perf_counter_ns()

            data = {
                "message_type": msg_type,
                "sysid": msg.get_srcSystem(),
                "compid": msg.get_srcComponent(),
            }

            if msg_type == "HEARTBEAT":
                data.update(
                    {
                        "type": msg.type,
                        "autopilot": msg.autopilot,
                        "system_status": msg.system_status,
                    }
                )
            elif msg_type == "ATTITUDE":
                data.update(
                    {
                        "time_boot_ms": msg.time_boot_ms,
                        "roll": msg.roll,
                        "pitch": msg.pitch,
                        "yaw": msg.yaw,
                    }
                )
            elif msg_type == "GLOBAL_POSITION_INT":
                data.update(
                    {
                        "lat": msg.lat,
                        "lon": msg.lon,
                        "alt": msg.alt,
                        "relative_alt": msg.relative_alt,
                    }
                )
            elif msg_type == "SYS_STATUS":
                data.update(
                    {
                        "battery_remaining": msg.battery_remaining,
                        "voltage_battery": msg.voltage_battery,
                        "current_battery": msg.current_battery,
                    }
                )

            payload = msgpack.packb(data)
            elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            metrics.record_telemetry_decode(elapsed_ms)

            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), loop)
        except Exception as e:
            if shutdown_event.is_set():
                break
            print(f"Error decoding MAVLink: {e}", flush=True)
            time.sleep(1)


def create_app() -> FastAPI:
    metrics = MetricsRegistry()
    store = InMemoryTelemetryStore()
    ws_manager = WebSocketManager(metrics)
    service = BenchmarkService(store=store, ws_manager=ws_manager, metrics=metrics)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.metrics = metrics
        app.state.store = store
        app.state.ws_manager = ws_manager
        app.state.service = service

        port = int(os.getenv("MAVLINK_PORT", "14550"))
        shutdown_event = threading.Event()
        try:
            conn = mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}")
            conn.mav.heartbeat_send(0, 0, 0, 0, 0)
        except Exception as e:
            print(f"Error starting MAVLink UDP listener: {e}", flush=True)
            conn = None

        if conn:
            loop = asyncio.get_running_loop()
            thread = threading.Thread(
                target=start_mavlink_listener,
                args=(conn, ws_manager, metrics, loop, shutdown_event),
                daemon=True,
            )
            thread.start()

        try:
            yield
        finally:
            shutdown_event.set()
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            await ws_manager.shutdown()

    app = FastAPI(
        title="fastapi-bridge",
        description="Reference FastAPI implementation for the GCS benchmark contract.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        started_ns = time.perf_counter_ns()
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        metrics.record_http_request(
            route=route_path,
            method=request.method,
            status=str(response.status_code),
            duration_ms=duration_ms,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_REQUEST", str(exc)).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, __: Exception):
        return JSONResponse(
            status_code=500,
            content=error_response("INTERNAL_ERROR", "Internal error").model_dump(),
        )

    @app.get("/health")
    async def direct_health():
        return {"status": "ok"}

    app.include_router(api_router)
    app.include_router(ws_router)
    app.include_router(metrics_router)
    return app


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
