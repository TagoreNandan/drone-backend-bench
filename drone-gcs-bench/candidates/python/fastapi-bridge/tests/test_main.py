"""Tests for the reference FastAPI benchmark implementation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


def telemetry_payload(seq: int = 1, drone_id: str = "drone-a") -> dict[str, object]:
    return {
        "run_id": "run-001",
        "drone_id": drone_id,
        "seq": seq,
        "timestamp": 1710000000000,
        "payload": {
            "lat": 37.422,
            "lon": -122.084,
            "alt": 12.5,
            "roll": 0.1,
            "pitch": 0.2,
            "yaw": 0.3,
            "battery": 99,
            "mode": "AUTO",
        },
    }


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_and_list_drones(client: TestClient) -> None:
    response = client.post(
        "/api/v1/drones/register", json={"drone_id": "drone-a", "model": "quad"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "drone_id": "drone-a"}

    response = client.get("/api/v1/drones")
    assert response.status_code == 200
    assert response.json() == {"drones": ["drone-a"]}


def test_telemetry_rejects_extra_fields(client: TestClient) -> None:
    payload = telemetry_payload()
    payload["extra"] = "nope"
    response = client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_telemetry_ingest_and_metrics(client: TestClient) -> None:
    response = client.post("/api/v1/telemetry", json=telemetry_payload())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    metrics = client.get("/metrics").text
    assert "http_requests_total" in metrics
    assert "http_request_duration_ms_bucket" in metrics
    assert "telemetry_ingest_total" in metrics
    assert "telemetry_ingest_latency_ms_bucket" in metrics
    assert "process_" not in metrics
    assert "python_" not in metrics


def test_websocket_broadcast_preserves_order(client: TestClient) -> None:
    with client.websocket_connect("/ws/telemetry") as websocket:
        assert (
            client.post("/api/v1/telemetry", json=telemetry_payload(seq=1)).status_code
            == 200
        )
        assert (
            client.post("/api/v1/telemetry", json=telemetry_payload(seq=2)).status_code
            == 200
        )

        first = websocket.receive_json(mode="binary")
        second = websocket.receive_json(mode="binary")

    assert first["drone_id"] == "drone-a"
    assert first["seq"] == 1
    assert first["timestamp"] == 1710000000000
    assert first["payload"]["mode"] == "AUTO"
    assert second["seq"] == 2
