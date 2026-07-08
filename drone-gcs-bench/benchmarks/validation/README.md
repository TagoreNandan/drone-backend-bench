# Benchmark Validation and Correctness Gate

This directory is the mandatory quality gate before onboarding additional frameworks.

It validates:
1. Contract compliance (REST + WebSocket shape strictness)
2. End-to-end data flow
3. Determinism and ordering stability
4. Metrics contract correctness
5. Load consistency using k6 profiles

## Validation architecture

```text
Generator-like deterministic events
  -> FastAPI REST ingest (/api/v1/telemetry)
  -> FastAPI WebSocket broadcast (/ws/telemetry)
  -> Validation client / k6 consumers
  -> Prometheus exposition contract (/metrics)
  -> Readiness gate decision (PASS/FAIL)
```

Gate components:
- `scripts/validate_contract_e2e.py`
  - strict key-set checks (no extra fields)
  - REST + WebSocket contract enforcement
  - e2e message equivalence checks
- `scripts/validate_determinism.py`
  - repeated fixed-run validation (same `run_id`)
  - per-drone ordering and drift checks
- `scripts/validate_metrics.py`
  - required families/series
  - label-set validation
  - extra-metric detection
- `scripts/validate_load_consistency.py`
  - runs k6 telemetry scenario across 100/500/1000
  - checks failure, throughput ratio, and p95 growth rules
- `scripts/run_quality_gate.sh`
  - orchestrates all validators

## Contract enforcement approach

Contract rules are declared in `config/contract_spec.json` and consumed by validators:
- REST response/request required keys
- WebSocket payload required keys
- Metrics family + series allow-list
- Metrics label rules

Any missing or extra key/metric/label fails the gate.

## Failure detection rules

### Contract
- Non-200 for valid requests
- Missing/extra fields in valid REST responses
- Invalid payload not rejected with 400 + error shape
- WebSocket message mismatch vs ingested telemetry projection

### Determinism
- Same `run_id` produces different websocket payload fingerprint
- Sequence for a `drone_id` is non-monotonic
- Inter-message timing drift above configured tolerance

### Metrics
- Missing required metric families
- Extra metric series not in allow-list
- Label mismatch for constrained metrics

### Load consistency
- Failure rate above configured threshold
- Ingest request-rate ratio below threshold
- p95 growth exceeds allowed profile-to-profile ratio

## Pass/fail readiness criteria

Defined in `config/readiness_criteria.json`:
- Determinism:
  - two identical runs
  - fixed event count
  - timing drift tolerance
- Load consistency:
  - profiles: 100 / 500 / 1000
  - max failure rate
  - min expected ingest rate ratio
  - max p95 growth bounds

Any single failed validator is a benchmark-readiness FAIL.

## Run commands

From repository root:

```bash
# start FastAPI + Prometheus stack first
cd candidates/python/fastapi-bridge
docker compose up -d

# run full gate
cd ../../benchmarks/validation
BASE_URL=http://localhost:8000 ./scripts/run_quality_gate.sh
```

Run individual checks:

```bash
python3 scripts/validate_contract_e2e.py --base-url http://localhost:8000
python3 scripts/validate_determinism.py --base-url http://localhost:8000
python3 scripts/validate_metrics.py --base-url http://localhost:8000
python3 scripts/validate_load_consistency.py --base-url http://localhost:8000
```

> `validate_load_consistency.py` requires `k6` in PATH.
