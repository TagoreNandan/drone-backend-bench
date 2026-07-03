"""MAVLink Synthetic Telemetry Generator."""

import argparse
import math
import os
import time
from pymavlink import mavutil
from typing import List, Tuple

from scenarios import generate_payload, _get_noise, M_TO_LAT, M_TO_LON, ORIGIN_ALT

# Standard flight modes list
FLIGHT_MODES = ["STABILIZE", "AUTO", "GUIDED", "RTL", "LAND", "HOVER", "LOITER"]

def get_mode_index(mode_str: str) -> int:
    """Map string mode to standard ArduPilot custom_mode integer."""
    try:
        return FLIGHT_MODES.index(mode_str.upper())
    except ValueError:
        return 0


def generate_events(
    num_drones: int, duration: float, rate: float, seed: int, jitter: float, loss: float
) -> List[Tuple[float, int, float]]:
    """Pre-compute and sort all send events to ensure perfect determinism with jitter and loss."""
    events: List[Tuple[float, int, float]] = []
    dt = 1.0 / rate
    steps = int(duration * rate) + 1

    for step in range(steps):
        t_base = step * dt
        for i in range(num_drones):
            # Deterministic packet loss check
            # Generate deterministic float between 0.0 and 1.0
            loss_noise = abs(_get_noise(seed + 99, i, t_base, scale=1.0)) % 1.0
            if loss_noise < loss:
                continue  # drop packet

            # Deterministic jitter offset
            offset = 0.0
            if jitter > 0:
                offset = _get_noise(seed + 100, i, t_base, scale=jitter)

            scheduled_t = max(0.0, t_base + offset)
            events.append((scheduled_t, i, t_base))

    # Sort events by scheduled transmission time
    events.sort(key=lambda x: x[0])
    return events


def main():
    parser = argparse.ArgumentParser(description="MAVLink Telemetry Generator")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--drones", type=int, default=1, help="Number of drones")
    parser.add_argument("--rate", type=float, default=10.0, help="Update frequency in Hz")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration in seconds")
    parser.add_argument("--scenario", type=str, default="hover", help="Flight scenario")
    parser.add_argument("--jitter", type=float, default=0.0, help="Max timing jitter in seconds")
    parser.add_argument("--loss", type=float, default=0.0, help="Packet loss rate (0.0 to 1.0)")
    parser.add_argument("--target-host", type=str, default="127.0.0.1", help="Target UDP host")
    parser.add_argument("--target-port", type=int, default=14550, help="Target UDP port")
    args = parser.parse_args()

    print(f"Starting Generator: seed={args.seed}, drones={args.drones}, rate={args.rate}Hz, scenario={args.scenario}")
    print(f"Targeting: {args.target_host}:{args.target_port}")

    # Create MAVLink connection
    # udpout creates a socket to send packets to the target address/port
    conn = mavutil.mavlink_connection(
        f"udpout:{args.target_host}:{args.target_port}",
        source_system=1,
        source_component=1
    )

    # Pre-generate and sort events
    events = generate_events(
        num_drones=args.drones,
        duration=args.duration,
        rate=args.rate,
        seed=args.seed,
        jitter=args.jitter,
        loss=args.loss
    )

    # Track sequence numbers per system/component
    # Standard MAVLink packet header handles sequence numbers automatically.
    # But we can track our own telemetry envelope sequence count in the generator/recorder.

    # Burst behavior for "telemetry_burst" scenario
    # Under burst scenario, we queue all messages for 500ms and send them together.
    # To implement this deterministically, if scenario is burst, we quantize scheduled_t to 500ms intervals!
    is_burst = args.scenario.lower() == "telemetry_burst"
    if is_burst:
        quantized_events = []
        for scheduled_t, drone_idx, t_base in events:
            # Group events into 500ms windows
            q_t = math.floor(scheduled_t * 2.0) / 2.0
            quantized_events.append((q_t, drone_idx, t_base))
        # Re-sort to preserve stable order
        quantized_events.sort(key=lambda x: (x[0], x[1], x[2]))
        events = quantized_events

    start_time = time.perf_counter()
    boot_time_ms = int(time.time() * 1000)

    for scheduled_t, drone_idx, t_base in events:
        # High precision real-time sleep
        target_real_time = start_time + scheduled_t
        while True:
            now = time.perf_counter()
            rem = target_real_time - now
            if rem <= 0:
                break
            if rem > 0.002:
                time.sleep(rem - 0.001)

        # Map drone_idx to MAVLink SysID and CompID
        sysid = (drone_idx % 250) + 1
        compid = (drone_idx // 250) + 1
        
        # Override connection's source IDs for this message
        conn.mav.srcSystem = sysid
        conn.mav.srcComponent = compid

        # Compute deterministic state
        payload, vx, vy, vz = generate_payload(
            args.scenario, drone_idx, args.drones, t_base, args.duration, args.seed
        )

        time_boot_ms = int(t_base * 1000)
        mode_idx = get_mode_index(payload["mode"])

        # 1. Send HEARTBEAT
        conn.mav.heartbeat_send(
            type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            custom_mode=mode_idx,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )

        # 2. Send ATTITUDE
        conn.mav.attitude_send(
            time_boot_ms=time_boot_ms & 0xFFFFFFFF,
            roll=payload["roll"],
            pitch=payload["pitch"],
            yaw=payload["yaw"],
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=0.0
        )

        # 3. Send GLOBAL_POSITION_INT
        hdg_val = int(math.degrees(payload["yaw"]) * 100) % 36000
        if hdg_val < 0:
            hdg_val += 36000
        conn.mav.global_position_int_send(
            time_boot_ms=time_boot_ms & 0xFFFFFFFF,
            lat=int(payload["lat"] * 1e7),
            lon=int(payload["lon"] * 1e7),
            alt=int(payload["alt"] * 1000),  # meters to mm
            relative_alt=int((payload["alt"] - ORIGIN_ALT) * 1000),  # mm above origin
            vx=int(vx * 100),  # m/s to cm/s
            vy=int(vy * 100),
            vz=int(vz * 100),
            hdg=hdg_val
        )

        # 4. Send SYS_STATUS (Battery)
        conn.mav.sys_status_send(
            onboard_control_sensors_present=0,
            onboard_control_sensors_enabled=0,
            onboard_control_sensors_health=0,
            load=0,
            voltage_battery=12000,  # mV
            current_battery=-1,
            battery_remaining=payload["battery"],
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=0,
            errors_count2=0,
            errors_count3=0,
            errors_count4=0
        )

    print("Generation complete.")

if __name__ == "__main__":
    main()
