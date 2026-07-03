#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <scenario> <profile> <target-name> <base-url> [duration] [vus] [telemetry-rate]"
  echo "Example: $0 telemetry 100 fastapi http://localhost:8000 2m 20 2"
  exit 1
fi

SCENARIO="$1"
PROFILE="$2"
TARGET="$3"
BASE_URL="$4"

DURATION="${5:-}"
VUS="${6:-}"
TELEMETRY_RATE="${7:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO_SCRIPT="${ROOT_DIR}/scenarios/${SCENARIO}.js"
RESULTS_DIR="${ROOT_DIR}/results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [[ ! -f "${SCENARIO_SCRIPT}" ]]; then
  echo "Scenario script not found: ${SCENARIO_SCRIPT}"
  exit 1
fi

mkdir -p "${RESULTS_DIR}"

COMMON_ENV=(
  "-e" "PROFILE=${PROFILE}"
  "-e" "BASE_URL=${BASE_URL}"
)

if [[ -n "${DURATION}" ]]; then
  COMMON_ENV+=("-e" "DURATION=${DURATION}")
fi

if [[ -n "${VUS}" ]]; then
  COMMON_ENV+=("-e" "VUS=${VUS}")
fi

if [[ -n "${TELEMETRY_RATE}" ]]; then
  COMMON_ENV+=("-e" "TELEMETRY_RATE=${TELEMETRY_RATE}")
fi

JSON_OUT="${RESULTS_DIR}/${TARGET}_${SCENARIO}_${PROFILE}_${TIMESTAMP}.json"
CSV_OUT="${RESULTS_DIR}/${TARGET}_${SCENARIO}_${PROFILE}_${TIMESTAMP}.csv"

SIM_PID=""
if [[ "${SCENARIO}" == "websocket" ]]; then
  DRONES=100
  RATE=2
  DUR=120

  if [[ "${PROFILE}" == "100" ]]; then
    DRONES=100
    RATE=2
    DUR=120
  elif [[ "${PROFILE}" == "500" ]]; then
    DRONES=500
    RATE=2
    DUR=180
  elif [[ "${PROFILE}" == "1000" ]]; then
    DRONES=1000
    RATE=2
    DUR=240
  elif [[ "${PROFILE}" == "5000" ]]; then
    DRONES=5000
    RATE=1
    DUR=300
  fi

  echo "--> Starting telemetry generator for scenario ${SCENARIO} profile ${PROFILE} (${DRONES} drones @ ${RATE}Hz for ${DUR}s)"
  python3 /Users/somespecies/Downloads/mavlink_sim.py \
    --drones "${DRONES}" \
    --rate "${RATE}" \
    --duration "${DUR}" \
    --port 14550 > /dev/null 2>&1 &
  SIM_PID=$!
  sleep 1
fi

cleanup() {
  if [[ -n "${SIM_PID}" ]]; then
    echo "--> Killing telemetry generator process ${SIM_PID}"
    kill "${SIM_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

k6 run \
  "${COMMON_ENV[@]}" \
  --out "json=${JSON_OUT}" \
  --out "csv=${CSV_OUT}" \
  "${SCENARIO_SCRIPT}"

echo "Results written:"
echo "  JSON: ${JSON_OUT}"
echo "  CSV : ${CSV_OUT}"
