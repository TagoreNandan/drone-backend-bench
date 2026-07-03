#!/bin/bash
set -e

# Workload E2E Pipeline Verification Script
echo "=== Starting Workload E2E pipeline verification ==="

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$DIR/../.."

# Paths
PYTHON="$ROOT_DIR/.venv/bin/python3"
RECORDER="$DIR/recorder.py"
GENERATOR="$DIR/generator.py"
REPLAY="$DIR/replay.py"
VALIDATOR="$DIR/validate_workload.py"

# Files
REC1="$DIR/recording_1.jsonl"
REC2="$DIR/recording_2.jsonl"

# Cleanup any previous files
rm -f "$REC1" "$REC2"

# 1. Run Generation & Recording 1
echo "--> Starting run 1: Generate & Record circular_orbit (3 drones, 5s)"
$PYTHON "$RECORDER" --output "$REC1" --run-id run-pipeline-test &
REC_PID=$!
sleep 1 # wait for recorder to bind UDP port

$PYTHON "$GENERATOR" --drones 3 --duration 5 --rate 10 --scenario circular_orbit
sleep 1
kill $REC_PID || true
wait $REC_PID || true

# 2. Run Generation & Recording 2 (Deterministic Reproducibility Check)
echo "--> Starting run 2: Generate & Record circular_orbit (3 drones, 5s, identical seed)"
$PYTHON "$RECORDER" --output "$REC2" --run-id run-pipeline-test &
REC_PID=$!
sleep 1

$PYTHON "$GENERATOR" --drones 3 --duration 5 --rate 10 --scenario circular_orbit
sleep 1
kill $REC_PID || true
wait $REC_PID || true

# 3. Run Validation checks
echo "--> Running contract & monotonicity validation on recording 1"
$PYTHON "$VALIDATOR" --mode validate --file1 "$REC1"

echo "--> Running contract & monotonicity validation on recording 2"
$PYTHON "$VALIDATOR" --mode validate --file1 "$REC2"

echo "--> Running payload equivalence comparison between run 1 and run 2"
$PYTHON "$VALIDATOR" --mode compare --file1 "$REC1" --file2 "$REC2"

# 4. Start net/http server to test Replay
echo "--> Booting local Go/nethttp-bridge candidate server"
cd "$ROOT_DIR/candidates/go/nethttp-bridge"
go build -o server cmd/server/main.go
./server &
SERVER_PID=$!
cd "$DIR"
sleep 1 # wait for server to start on port 8000

echo "--> Replaying recording 1 to candidate server at speed=2.0x"
$PYTHON "$REPLAY" --input "$REC1" --base-url http://localhost:8000 --speed 2.0

echo "--> Verifying active drones list on candidate server"
DRONES_RESP=$(curl -s http://localhost:8000/api/v1/drones)
echo "Active drones response: $DRONES_RESP"

if [[ "$DRONES_RESP" == *"drone-0001"* && "$DRONES_RESP" == *"drone-0002"* && "$DRONES_RESP" == *"drone-0003"* ]]; then
  echo "PASS: Active drones list verified on server!"
else
  echo "FAIL: Expected active drones list not found. Response: $DRONES_RESP"
  kill $SERVER_PID || true
  exit 1
fi

# Shutdown server
kill $SERVER_PID || true
wait $SERVER_PID || true

# Cleanup test files
rm -f "$REC1" "$REC2"

echo "=== ALL E2E WORKLOAD VALIDATION CHECKS PASSED SUCCESSFULLY! ==="
