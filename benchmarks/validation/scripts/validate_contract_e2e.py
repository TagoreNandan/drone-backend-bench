#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets


@dataclass(frozen=True)
class RuntimeConfig:
    base_url: str
    ws_url: str
    timeout_seconds: float
    contract_path: Path


def _normalize_base_url(base_url: str) -> str:
    return base_url[:-1] if base_url.endswith("/") else base_url


def _derive_ws_url(base_url: str) -> str:
    if base_url.startswith("https://"):
        return "wss://" + base_url.removeprefix("https://")
    if base_url.startswith("http://"):
        return "ws://" + base_url.removeprefix("http://")
    raise ValueError(f"Unsupported BASE_URL scheme: {base_url}")


def _load_contract(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_exact_keys(label: str, payload: dict[str, Any], required: list[str]) -> None:
    expected = set(required)
    actual = set(payload.keys())
    if expected != actual:
        missing = sorted(expected - actual)
        extras = sorted(actual - expected)
        raise AssertionError(f"{label} key mismatch. missing={missing}, extras={extras}")


def _http_json(method: str, url: str, body: dict[str, Any] | None, timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    encoded = None
    headers: dict[str, str] = {}
    if body is not None:
        encoded = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=encoded, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            status = response.status
            parsed = json.loads(response.read().decode("utf-8"))
            return status, parsed
    except urllib.error.HTTPError as err:
        payload = json.loads(err.read().decode("utf-8"))
        return err.code, payload


def _telemetry_event(run_id: str, drone_index: int, seq: int) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "drone_id": f"drone-{drone_index:04d}",
        "seq": seq,
        "timestamp": 1_710_000_000_000 + seq,
        "payload": {
            "lat": 37.4 + drone_index * 0.0001,
            "lon": -122.1 + drone_index * 0.0001,
            "alt": 10.0 + drone_index,
            "roll": 0.1,
            "pitch": 0.2,
            "yaw": float((drone_index * 7 + seq) % 360),
            "battery": max(0, 100 - seq),
            "mode": "AUTO",
        },
    }


async def _validate_websocket_and_e2e(config: RuntimeConfig, contract: dict[str, Any]) -> None:
    ws_message_required = contract["websocket"]["message_required"]
    ws_payload_required = contract["websocket"]["payload_required"]

    ws_target = f"{config.ws_url}/ws/telemetry"
    async with websockets.connect(ws_target, open_timeout=config.timeout_seconds) as socket:
        run_id = "validation-contract-e2e"
        sent = []
        for seq in range(1, 6):
            event = _telemetry_event(run_id=run_id, drone_index=1, seq=seq)
            status, payload = _http_json(
                "POST",
                f"{config.base_url}/api/v1/telemetry",
                event,
                timeout_seconds=config.timeout_seconds,
            )
            assert status == 200, f"telemetry ingest failed with status={status} payload={payload}"
            sent.append(event)

        for source in sent:
            raw = await asyncio.wait_for(socket.recv(), timeout=config.timeout_seconds)
            message = json.loads(raw)
            _assert_exact_keys("websocket.message", message, ws_message_required)
            _assert_exact_keys("websocket.payload", message["payload"], ws_payload_required)
            expected = {
                "drone_id": source["drone_id"],
                "seq": source["seq"],
                "timestamp": source["timestamp"],
                "payload": source["payload"],
            }
            if message != expected:
                raise AssertionError(f"websocket message mismatch expected={expected} actual={message}")


def validate_contract(config: RuntimeConfig, contract: dict[str, Any]) -> None:
    rest = contract["rest"]

    status, body = _http_json("GET", f"{config.base_url}/api/v1/health", None, config.timeout_seconds)
    assert status == 200, f"health status={status}"
    _assert_exact_keys("health.response", body, rest["health_response_required"])

    register_body = {"drone_id": "drone-0001", "model": "quad"}
    status, body = _http_json(
        "POST",
        f"{config.base_url}/api/v1/drones/register",
        register_body,
        config.timeout_seconds,
    )
    assert status == 200, f"register status={status}"
    _assert_exact_keys("register.response", body, rest["register_response_required"])
    if body["drone_id"] != register_body["drone_id"]:
        raise AssertionError("register response drone_id mismatch")

    invalid_register = {"drone_id": "drone-0001", "model": "quad", "extra": True}
    status, body = _http_json(
        "POST",
        f"{config.base_url}/api/v1/drones/register",
        invalid_register,
        config.timeout_seconds,
    )
    assert status == 400, f"invalid register should fail, status={status}"
    _assert_exact_keys("error.response", body, rest["error_response_required"])
    _assert_exact_keys("error.object", body["error"], rest["error_object_required"])

    telemetry = _telemetry_event(run_id="validation-contract", drone_index=1, seq=1)
    status, body = _http_json(
        "POST",
        f"{config.base_url}/api/v1/telemetry",
        telemetry,
        config.timeout_seconds,
    )
    assert status == 200, f"telemetry status={status}"
    _assert_exact_keys("telemetry.response", body, rest["status_ok_response_required"])

    invalid = dict(telemetry)
    invalid["extra"] = "forbidden"
    status, body = _http_json(
        "POST",
        f"{config.base_url}/api/v1/telemetry",
        invalid,
        config.timeout_seconds,
    )
    assert status == 400, f"invalid telemetry should fail, status={status}"
    _assert_exact_keys("error.response.telemetry", body, rest["error_response_required"])

    status, body = _http_json("GET", f"{config.base_url}/api/v1/drones", None, config.timeout_seconds)
    assert status == 200, f"drones list status={status}"
    _assert_exact_keys("drones.response", body, rest["drone_list_response_required"])
    if not isinstance(body["drones"], list) or not all(isinstance(item, str) for item in body["drones"]):
        raise AssertionError("drones list must be array<string>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Contract compliance + E2E flow validation gate")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument(
        "--contract-spec",
        default=str(Path(__file__).resolve().parent.parent / "config" / "contract_spec.json"),
    )
    args = parser.parse_args()

    base_url = _normalize_base_url(args.base_url)
    config = RuntimeConfig(
        base_url=base_url,
        ws_url=_derive_ws_url(base_url),
        timeout_seconds=args.timeout_seconds,
        contract_path=Path(args.contract_spec),
    )

    try:
        contract = _load_contract(config.contract_path)
        validate_contract(config, contract)
        asyncio.run(_validate_websocket_and_e2e(config, contract))
    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    print("PASS: contract compliance + end-to-end flow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
