#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${ROOT_DIR}/scripts"

echo "[1/4] Contract + E2E validation"
python3 "${SCRIPTS_DIR}/validate_contract_e2e.py" --base-url "${BASE_URL}"

echo "[2/4] Determinism validation"
python3 "${SCRIPTS_DIR}/validate_determinism.py" --base-url "${BASE_URL}"

echo "[3/4] Metrics validation"
python3 "${SCRIPTS_DIR}/validate_metrics.py" --base-url "${BASE_URL}"

echo "[4/4] k6 load consistency validation"
python3 "${SCRIPTS_DIR}/validate_load_consistency.py" --base-url "${BASE_URL}"

echo "QUALITY GATE PASSED"
