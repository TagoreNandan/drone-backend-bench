#!/usr/bin/env python3
"""
mavlink_sim.py — Synthetic multi-drone MAVLink traffic generator.

Simulates N virtual drones, each emitting MAVLink telemetry over UDP, so a
backend framework can be load-tested at a controlled, repeatable rate —
without needing N real drones or N SITL instances running physics.

Each virtual drone sends:
  - HEARTBEAT + SYS_STATUS at 1Hz (standard MAVLink convention)
  - ATTITUDE + GLOBAL_POSITION_INT at the configured high rate (10-50Hz)

Usage:
    python mavlink_sim.py --drones 100 --rate 25 --duration 60 \
        --host 127.0.0.1 --port 14550

Scaling tiers for the fleet benchmark (run one at a time):
    python mavlink_sim.py --drones 1    --rate 25 --duration 30
    python mavlink_sim.py --drones 10   --rate 25 --duration 30
    python mavlink_sim.py --drones 100  --rate 25 --duration 30
    python mavlink_sim.py --drones 1000 --rate 25 --duration 30

Note: at high drone counts, watch this script's own CPU usage (Task
Manager / htop). If the generator itself can't keep up with the target
rate, your latency numbers will be measuring the generator, not the
framework under test. If that happens, split drones across multiple
processes (e.g. 4 x 250) or multiple machines instead of one process.
"""

import argparse
import math
import socket
import time

from pymavlink.dialects.v20 import common as mavlink2
from pymavlink import mavutil


def build_drone(system_id: int) -> mavlink2.MAVLink:
    """One lightweight MAVLink message-builder per virtual drone, each with its own system_id
    so the receiving bridge can tell drones apart on a single UDP port."""
    mav = mavlink2.MAVLink(None, srcSystem=system_id, srcComponent=1)
    mav.robust_parsing = True
    return mav


def make_heartbeat(mav):
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_PX4,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED,
        custom_mode=0,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def make_attitude(mav, t):
    return mav.attitude_encode(
        time_boot_ms=int(t * 1000) & 0xFFFFFFFF,
        roll=0.05 * math.sin(t),
        pitch=0.03 * math.cos(t),
        yaw=t % (2 * math.pi),
        rollspeed=0.0,
        pitchspeed=0.0,
        yawspeed=0.0,
    )


def make_global_position(mav, t, drone_id):
    # Spread drones out spatially so simulated telemetry looks like a real fleet,
    # not 1000 drones stacked on one point.
    base_lat = 17.385044 + (drone_id % 50) * 0.001
    base_lon = 78.486671 + (drone_id // 50) * 0.001
    return mav.global_position_int_encode(
        time_boot_ms=int(t * 1000) & 0xFFFFFFFF,
        lat=int(base_lat * 1e7),
        lon=int(base_lon * 1e7),
        alt=int(50000 + 1000 * (drone_id % 10)),
        relative_alt=50000,
        vx=0,
        vy=0,
        vz=0,
        hdg=0,
    )


def make_sys_status(mav, drone_id):
    battery_pct = max(20, 100 - (drone_id % 80))
    return mav.sys_status_encode(
        onboard_control_sensors_present=0,
        onboard_control_sensors_enabled=0,
        onboard_control_sensors_health=0,
        load=500,
        voltage_battery=12000,
        current_battery=1500,
        battery_remaining=battery_pct,
        drop_rate_comm=0,
        errors_comm=0,
        errors_count1=0,
        errors_count2=0,
        errors_count3=0,
        errors_count4=0,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic multi-drone MAVLink generator"
    )
    parser.add_argument(
        "--drones", type=int, default=10, help="Number of virtual drones"
    )
    parser.add_argument(
        "--rate", type=float, default=25.0, help="High-rate msg Hz (attitude/position)"
    )
    parser.add_argument(
        "--duration", type=float, default=30.0, help="Test duration, seconds"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Target bridge host")
    parser.add_argument(
        "--port", type=int, default=14550, help="Target bridge UDP port"
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (args.host, args.port)

    drones = [build_drone(system_id=i + 1) for i in range(args.drones)]
    interval = 1.0 / args.rate
    heartbeat_interval = 1.0

    next_high_rate = [0.0] * args.drones
    next_heartbeat = [0.0] * args.drones

    start = time.monotonic()
    sent_count = 0
    print(
        f"[mavlink_sim] {args.drones} drones -> {args.host}:{args.port} "
        f"@ {args.rate}Hz for {args.duration}s"
    )

    try:
        while True:
            now = time.monotonic() - start
            if now >= args.duration:
                break

            for i, mav in enumerate(drones):
                if now >= next_high_rate[i]:
                    sock.sendto(make_attitude(mav, now).pack(mav), target)
                    sock.sendto(make_global_position(mav, now, i).pack(mav), target)
                    sent_count += 2
                    next_high_rate[i] = now + interval

                if now >= next_heartbeat[i]:
                    sock.sendto(make_heartbeat(mav).pack(mav), target)
                    sock.sendto(make_sys_status(mav, i).pack(mav), target)
                    sent_count += 2
                    next_heartbeat[i] = now + heartbeat_interval

            time.sleep(0.001)  # yield so this doesn't peg one core at 100%

    except KeyboardInterrupt:
        print("\n[mavlink_sim] interrupted")

    elapsed = time.monotonic() - start
    achieved_rate = sent_count / elapsed if elapsed > 0 else 0
    target_rate = args.drones * (2 / interval + 2 / heartbeat_interval)
    print(
        f"[mavlink_sim] done: {sent_count} messages in {elapsed:.1f}s "
        f"({achieved_rate:.0f} msg/s achieved, {target_rate:.0f} msg/s target)"
    )
    if achieved_rate < target_rate * 0.9:
        print(
            "[mavlink_sim] WARNING: achieved rate is >10% below target — "
            "the generator itself may be the bottleneck, not the framework "
            "under test. Consider splitting drones across processes."
        )


if __name__ == "__main__":
    main()
