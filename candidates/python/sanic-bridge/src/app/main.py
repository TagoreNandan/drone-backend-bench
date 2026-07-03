"""Sanic GCS candidate application entry point."""

from __future__ import annotations

import os
import time
import threading
import asyncio
from pymavlink import mavutil
import msgpack
from dotenv import load_dotenv
from pydantic import ValidationError
from sanic import Sanic
from sanic.response import json as json_response, text as text_response

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

app = Sanic("sanic-bridge")


@app.middleware("request")
async def store_start_time(request):
    request.ctx.start_time = time.perf_counter_ns()


@app.middleware("response")
async def record_metrics(request, response):
    start_time = getattr(request.ctx, "start_time", None)
    if start_time is not None:
        duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
        route_path = request.route.path if request.route else request.path
        metrics.record_http_request(
            route=route_path,
            method=request.method,
            status=str(response.status),
            duration_ms=duration_ms,
        )


async def health_handler(request):
    return json_response({"status": "ok"})


async def get_metrics_handler(request):
    return text_response(
        metrics.render(),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )


async def ws_telemetry_handler(request, ws):
    conn_id = await ws_manager.connect(ws)
    try:
        while True:
            await ws.recv()
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(conn_id)


@app.before_server_start
async def start_telemetry_listener(app_, loop):
    port = int(os.getenv("MAVLINK_PORT", "14550"))
    thread = threading.Thread(
        target=start_mavlink_listener,
        args=(port, ws_manager, metrics, loop),
        daemon=True
    )
    thread.start()


@app.after_server_stop
async def shutdown_ws(app_, loop):
    await ws_manager.shutdown()


app.add_route(health_handler, "/api/v1/health", methods=["GET"])
app.add_route(get_metrics_handler, "/metrics", methods=["GET"])
app.add_websocket_route(ws_telemetry_handler, "/ws/telemetry", name="ws_telemetry_1")
app.add_websocket_route(ws_telemetry_handler, "/api/v1/ws/telemetry", name="ws_telemetry_2")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    app.run(host=host, port=port, access_log=False)
