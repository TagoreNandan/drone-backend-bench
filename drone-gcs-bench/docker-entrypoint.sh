#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "Starting GCS Benchmark Orchestration Environment"
echo "=================================================="

# 1. Build all candidate images
echo "--> Building candidate Docker images..."
for fw_dir in candidates/python/*-bridge candidates/typescript/*-gateway candidates/typescript/*-bridge candidates/go/*-bridge; do
  if [ -d "$fw_dir" ]; then
    img_name=$(basename "$fw_dir")
    echo "Building image $img_name..."
    docker build -t "$img_name:latest" "$fw_dir"
  fi
done

# 2. Execute the benchmark suite
echo "--> Executing the benchmark campaign..."
python3 benchmarks/run_campaign.py

# 3. Generate Markdown and HTML reports
echo "--> Generating benchmark reports..."
python3 benchmarks/generate_report.py

echo "=================================================="
echo "Benchmark Campaign Completed Successfully!"
echo "=================================================="
