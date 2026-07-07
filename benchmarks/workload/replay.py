"""Asynchronous Telemetry Replay Engine."""

import argparse
import asyncio
import json
import sys
import time
import httpx
from typing import List, Dict, Any


async def send_telemetry(
    client: httpx.AsyncClient, base_url: str, event: Dict[str, Any]
) -> None:
    url = f"{base_url.rstrip('/')}/api/v1/telemetry"
    # Re-pack envelope explicitly to enforce contract spec order and key set
    envelope = {
        "run_id": event["run_id"],
        "drone_id": event["drone_id"],
        "seq": event["seq"],
        "timestamp": event["timestamp"],
        "payload": {
            "lat": event["payload"]["lat"],
            "lon": event["payload"]["lon"],
            "alt": event["payload"]["alt"],
            "roll": event["payload"]["roll"],
            "pitch": event["payload"]["pitch"],
            "yaw": event["payload"]["yaw"],
            "battery": event["payload"]["battery"],
            "mode": event["payload"]["mode"],
        },
    }

    try:
        resp = await client.post(url, json=envelope)
        if resp.status_code != 200:
            print(
                f"Error response: status={resp.status_code} body={resp.text}",
                file=sys.stderr,
            )
    except Exception as e:
        print(f"HTTP post exception: {e}", file=sys.stderr)


async def replay_events(args) -> None:
    events: List[Dict[str, Any]] = []

    print(f"Loading recording: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                events.append(json.loads(stripped))

    if not events:
        print("Error: No events found in the recording file.")
        sys.exit(1)

    # Re-sort to guarantee strict timestamp ordering
    events.sort(key=lambda x: x["timestamp"])

    first_ts = events[0]["timestamp"]
    total_events = len(events)
    print(f"Replaying {total_events} events to {args.base_url} (speed={args.speed}x)")

    # Semaphore to bound concurrent sockets
    sem = asyncio.Semaphore(args.concurrency)
    limits = httpx.Limits(
        max_keepalive_connections=args.concurrency, max_connections=args.concurrency * 2
    )

    async with httpx.AsyncClient(limits=limits, timeout=5.0) as client:

        async def worker(event: Dict[str, Any], scheduled_time: float):
            async with sem:
                now = time.perf_counter() - start_time
                rem = scheduled_time - now
                if rem > 0:
                    await asyncio.sleep(rem)
                await send_telemetry(client, args.base_url, event)

        start_time = time.perf_counter()
        tasks = []

        for event in events:
            rel_ms = event["timestamp"] - first_ts
            if args.speed > 0.0:
                scheduled_time = (rel_ms / 1000.0) / args.speed
            else:
                scheduled_time = 0.0  # unlimited speed

            tasks.append(asyncio.create_task(worker(event, scheduled_time)))

        await asyncio.gather(*tasks)

    print("Replay completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Deterministic Workload Replay Engine")
    parser.add_argument(
        "--input",
        type=str,
        default="recording.jsonl",
        help="Path to recording JSON Lines file",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Target GCS base URL",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier (0.0 for unlimited)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=100, help="Max concurrent connections"
    )
    args = parser.parse_args()

    asyncio.run(replay_events(args))


if __name__ == "__main__":
    main()
