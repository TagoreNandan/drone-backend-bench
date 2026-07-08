"""aiohttp GCS candidate application entry point."""

from __future__ import annotations

import os
import time
import threading
import asyncio
from aiohttp import web
from pymavlink import mavutil
import msgpack
from dotenv import load_dotenv
from pydantic import ValidationError

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


@web.middleware
async def metrics_middleware(request: web.Request, handler) -> web.StreamResponse:
    started_ns = time.perf_counter_ns()
    status_code = 200
    try:
        response = await handler(request)
        status_code = response.status
        return response
    except web.HTTPException as ex:
        status_code = ex.status
        raise
    except Exception:
        status_code = 500
        raise
    finally:
        duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        route_path = request.path
        if request.match_info.route.resource:
            # Reconstruct template path if available
            route_path = request.match_info.route.resource.canonical
        metrics.record_http_request(
            route=route_path,
            method=request.method,
            status=str(status_code),
            duration_ms=duration_ms,
        )


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def get_metrics(request: web.Request) -> web.Response:
    return web.Response(
        text=metrics.render(),
        content_type="text/plain",
        charset="utf-8",
        headers={"version": "0.0.4"},
    )


async def ws_telemetry(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    conn_id = await ws_manager.connect(ws)
    try:
        async for _ in ws:
            pass
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(conn_id)
    return ws


async def startup_task(app: web.Application) -> None:
    port = int(os.getenv("MAVLINK_PORT", "14550"))
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=start_mavlink_listener,
        args=(port, ws_manager, metrics, loop),
        daemon=True
    )
    thread.start()


async def on_shutdown(app: web.Application) -> None:
    await ws_manager.shutdown()


def create_app() -> web.Application:
    app = web.Application(middlewares=[metrics_middleware])
    app.router.add_get("/api/v1/health", health)
    app.router.add_get("/metrics", get_metrics)
    app.router.add_get("/ws/telemetry", ws_telemetry)
    app.router.add_get("/api/v1/ws/telemetry", ws_telemetry)
    app.on_startup.append(startup_task)
    app.on_shutdown.append(on_shutdown)
    return app


app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    web.run_app(app, host=host, port=port, print=None)
