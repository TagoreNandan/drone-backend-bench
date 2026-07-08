"""Strict contract models for the benchmark service."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DroneRegistrationRequest(StrictBaseModel):
    drone_id: Annotated[str, Field(min_length=1)]
    model: Annotated[str, Field(min_length=1)]


class DroneRegistrationResponse(StrictBaseModel):
    status: str = "ok"
    drone_id: str


class StatusOkResponse(StrictBaseModel):
    status: str = "ok"


class TelemetryPayload(StrictBaseModel):
    lat: float
    lon: float
    alt: float
    roll: float
    pitch: float
    yaw: float
    battery: Annotated[int, Field(ge=0, le=100)]
    mode: Annotated[str, Field(min_length=1)]


class TelemetryEnvelope(StrictBaseModel):
    run_id: Annotated[str, Field(min_length=1)]
    drone_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    timestamp: Annotated[int, Field(ge=0)]
    payload: TelemetryPayload


class TelemetryWebSocketMessage(StrictBaseModel):
    drone_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    timestamp: Annotated[int, Field(ge=0)]
    payload: TelemetryPayload


class DroneListResponse(StrictBaseModel):
    drones: list[str]


class HealthResponse(StrictBaseModel):
    status: str = "ok"


class ErrorObject(StrictBaseModel):
    code: Annotated[str, Field(min_length=1)]
    message: Annotated[str, Field(min_length=1)]


class ErrorResponse(StrictBaseModel):
    error: ErrorObject
