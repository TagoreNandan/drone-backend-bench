"""MAVLink Telemetry Recorder."""

import argparse
import json
import signal
import sys
import time
from pymavlink import mavutil
from typing import Dict, Any

FLIGHT_MODES = ["STABILIZE", "AUTO", "GUIDED", "RTL", "LAND", "HOVER", "LOITER"]


def main():
    parser = argparse.ArgumentParser(description="MAVLink Telemetry Recorder")
    parser.add_argument(
        "--listen-host", type=str, default="0.0.0.0", help="Host to bind UDP port"
    )
    parser.add_argument(
        "--listen-port", type=int, default=14550, help="UDP port to listen on"
    )
    parser.add_argument(
        "--output", type=str, default="recording.jsonl", help="Output JSON Lines file"
    )
    parser.add_argument(
        "--run-id", type=str, default="", help="Run ID for telemetry envelopes"
    )
    args = parser.parse_args()

    run_id = args.run_id if args.run_id else f"run-{int(time.time())}"
    print(
        f"Starting Recorder: listening on {args.listen_host}:{args.listen_port}, run_id={run_id}"
    )
    print(f"Writing to: {args.output}")

    # Open output file
    # Flush on every write to avoid buffering data loss
    out_file = open(args.output, "w", encoding="utf-8")

    # Connect to UDP socket
    conn = mavutil.mavlink_connection(f"udpin:{args.listen_host}:{args.listen_port}")

    # State cache and sequence numbers per drone ID
    state_cache: Dict[str, Dict[str, Any]] = {}
    seq_counter: Dict[str, int] = {}

    # Signal handlers for graceful shutdown
    running = True

    def sig_handler(signum, frame):
        nonlocal running
        print("\nShutdown signal received. Stopping recorder...")
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        while running:
            # Receive MAVLink packet with timeout to allow checking running flag
            msg = conn.recv_match(blocking=True, timeout=0.5)
            if not msg:
                continue

            msg_type = msg.get_type()
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()
            drone_id = f"drone-{sysid + (compid - 1) * 250:04d}"

            if msg_type == "HEARTBEAT":
                mode_idx = msg.custom_mode
                mode_str = (
                    FLIGHT_MODES[mode_idx] if mode_idx < len(FLIGHT_MODES) else "HOVER"
                )
                state_cache.setdefault(drone_id, {})["mode"] = mode_str

            elif msg_type == "SYS_STATUS":
                state_cache.setdefault(drone_id, {})["battery"] = msg.battery_remaining

            elif msg_type == "ATTITUDE":
                cache = state_cache.setdefault(drone_id, {})
                cache["roll"] = msg.roll
                cache["pitch"] = msg.pitch
                cache["yaw"] = msg.yaw

            elif msg_type == "GLOBAL_POSITION_INT":
                # Convert standard integer values to degrees and meters
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                alt = msg.alt / 1000.0  # mm to meters

                cache = state_cache.setdefault(drone_id, {})

                # Fetch cached attributes with safe defaults
                battery = cache.get("battery", 100)
                mode = cache.get("mode", "HOVER")
                roll = cache.get("roll", 0.0)
                pitch = cache.get("pitch", 0.0)
                yaw = cache.get("yaw", 0.0)

                # Monotonically increasing sequence per drone
                seq = seq_counter.get(drone_id, 0)
                seq_counter[drone_id] = seq + 1

                # Construct envelope exactly matching TelemetryEnvelope JSON contract
                envelope = {
                    "run_id": run_id,
                    "drone_id": drone_id,
                    "seq": seq,
                    "timestamp": int(time.time() * 1000),  # millisecond epoch
                    "payload": {
                        "lat": lat,
                        "lon": lon,
                        "alt": alt,
                        "roll": roll,
                        "pitch": pitch,
                        "yaw": yaw,
                        "battery": battery,
                        "mode": mode,
                    },
                }

                out_file.write(json.dumps(envelope) + "\n")
                out_file.flush()

    except Exception as e:
        print(f"Recorder error: {e}", file=sys.stderr)
    finally:
        out_file.close()
        print("Recorder stopped.")


if __name__ == "__main__":
    main()
