"""REST API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_service
from app.models import (
    HealthResponse,
    DroneRegistrationRequest,
    DroneRegistrationResponse,
    TelemetryEnvelope,
    StatusOkResponse,
    DroneListResponse,
)
from app.service import BenchmarkService

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/health", response_model=HealthResponse)
async def health(service: BenchmarkService = Depends(get_service)) -> HealthResponse:
    return service.health()


@router.post("/drones/register", response_model=DroneRegistrationResponse)
async def register_drone(
    payload: DroneRegistrationRequest,
    service: BenchmarkService = Depends(get_service),
) -> DroneRegistrationResponse:
    return await service.register_drone(payload)


@router.post("/telemetry", response_model=StatusOkResponse)
async def ingest_telemetry(
    payload: TelemetryEnvelope,
    service: BenchmarkService = Depends(get_service),
) -> StatusOkResponse:
    return await service.ingest_telemetry(payload)


@router.get("/drones", response_model=DroneListResponse)
async def list_drones(
    service: BenchmarkService = Depends(get_service),
) -> DroneListResponse:
    return await service.list_drones()

