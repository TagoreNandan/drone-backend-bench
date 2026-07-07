#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import websockets


@dataclass(frozen=True)
class DeterminismConfig:
    base_url: str
    ws_url: str
    events_per_run: int
    interval_ms: int
    timing_drift_tolerance_ms: int
    timeout_seconds: float


def _normalize_base_url(base_url: str) -> str:
    return base_url[:-1] if base_url.endswith("/") else base_url


def _derive_ws_url(base_url: str) -> str:
    if base_url.startswith("https://"):
        return "wss://" + base_url.removeprefix("https://")
    if base_url.startswith("http://"):
        return "ws://" + base_url.removeprefix("http://")
    raise ValueError(f"Unsupported BASE_URL: {base_url}")


def _event_for(run_id: str, seq: int) -> dict:
    drone_index = seq % 3
    return {
        "run_id": run_id,
        "drone_id": f"det-drone-{drone_index:02d}",
        "seq": seq,
        "timestamp": 1_720_000_000_000 + seq * 10,
        "payload": {
            "lat": 37.0 + drone_index * 0.001 + seq * 0.00001,
            "lon": -122.0 + drone_index * 0.001 + seq * 0.00001,
            "alt": 10 + drone_index,
            "roll": (seq % 10) * 0.1,
            "pitch": ((seq + 3) % 10) * 0.1,
            "yaw": float((seq * 11) % 360),
            "battery": 100 - (seq % 100),
            "mode": "AUTO",
        },
    }


def _post_json(url: str, payload: dict, timeout_seconds: float) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise RuntimeError(f"POST {url} failed status={response.status}")


def _fingerprint(messages: list[dict]) -> str:
    canonical = json.dumps(messages, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


async def _capture_run(
    config: DeterminismConfig, run_id: str
) -> tuple[list[dict], list[float]]:
    target = f"{config.ws_url}/ws/telemetry"
    events = [_event_for(run_id, seq) for seq in range(1, config.events_per_run + 1)]
    received: list[dict] = []
    receive_timestamps: list[float] = []

    async with websockets.connect(
        target, open_timeout=config.timeout_seconds
    ) as socket:
        for event in events:
            _post_json(
                f"{config.base_url}/api/v1/telemetry", event, config.timeout_seconds
            )
            raw = await asyncio.wait_for(socket.recv(), timeout=config.timeout_seconds)
            receive_timestamps.append(time.perf_counter() * 1000.0)
            message = json.loads(raw)
            expected = {
                "drone_id": event["drone_id"],
                "seq": event["seq"],
                "timestamp": event["timestamp"],
                "payload": event["payload"],
            }
            if message != expected:
                raise AssertionError(
                    f"WS message mismatch expected={expected} actual={message}"
                )
            received.append(message)
            await asyncio.sleep(config.interval_ms / 1000.0)

    return received, receive_timestamps


def _validate_per_drone_order(messages: list[dict]) -> None:
    last_seq_by_drone: dict[str, int] = {}
    for message in messages:
        drone_id = message["drone_id"]
        seq = message["seq"]
        last = last_seq_by_drone.get(drone_id)
        if last is not None and seq <= last:
            raise AssertionError(
                f"Non-monotonic sequence for {drone_id}: prev={last} current={seq}"
            )
        last_seq_by_drone[drone_id] = seq


def _compute_intervals(receive_ts_ms: list[float]) -> list[float]:
    return [
        receive_ts_ms[idx] - receive_ts_ms[idx - 1]
        for idx in range(1, len(receive_ts_ms))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate deterministic telemetry and websocket ordering across repeated runs"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--criteria",
        default=str(
            Path(__file__).resolve().parent.parent
            / "config"
            / "readiness_criteria.json"
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()

    criteria = json.loads(Path(args.criteria).read_text(encoding="utf-8"))[
        "determinism"
    ]
    base_url = _normalize_base_url(args.base_url)
    config = DeterminismConfig(
        base_url=base_url,
        ws_url=_derive_ws_url(base_url),
        events_per_run=int(criteria["events_per_run"]),
        interval_ms=int(criteria["interval_ms"]),
        timing_drift_tolerance_ms=int(criteria["timing_drift_tolerance_ms"]),
        timeout_seconds=args.timeout_seconds,
    )

    try:
        run_a_messages, run_a_ts = asyncio.run(
            _capture_run(config, run_id="determinism-run-fixed")
        )
        run_b_messages, run_b_ts = asyncio.run(
            _capture_run(config, run_id="determinism-run-fixed")
        )

        _validate_per_drone_order(run_a_messages)
        _validate_per_drone_order(run_b_messages)

        fingerprint_a = _fingerprint(run_a_messages)
        fingerprint_b = _fingerprint(run_b_messages)
        if fingerprint_a != fingerprint_b:
            raise AssertionError(
                f"Determinism drift detected: {fingerprint_a} != {fingerprint_b}"
            )

        intervals_a = _compute_intervals(run_a_ts)
        intervals_b = _compute_intervals(run_b_ts)
        if len(intervals_a) != len(intervals_b):
            raise AssertionError("Mismatched interval lengths")

        for idx, (left, right) in enumerate(
            zip(intervals_a, intervals_b, strict=True), start=1
        ):
            if abs(left - right) > config.timing_drift_tolerance_ms:
                raise AssertionError(
                    f"Timing drift above tolerance at interval {idx}: "
                    f"run_a={left:.2f}ms run_b={right:.2f}ms tolerance={config.timing_drift_tolerance_ms}ms"
                )
    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    print("PASS: determinism and ordering gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
