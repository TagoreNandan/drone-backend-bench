# fastapi-bridge (Benchmark Reference Service)

Reference FastAPI implementation for the Drone GCS benchmark contract.

## Local run (without Docker)

```bash
uv sync --extra dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Containerized stack (FastAPI + Prometheus)

1. Copy env file:

```bash
cp .env.example .env
```

2. Build and run:

```bash
docker compose up --build -d
```

3. Check health:

```bash
docker compose ps
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:9090/-/healthy
```

4. Stop:

```bash
docker compose down
```

## Key paths

```text
fastapi-bridge/
├── Dockerfile
├── docker-compose.yml
├── prometheus.yml
├── .env.example
├── src/app/
└── tests/
```
