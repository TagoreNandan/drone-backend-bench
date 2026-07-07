"""Validation utilities for GCS benchmark workload correctness."""

import argparse
import json
import sys
from typing import Dict


def validate_file_contract(filename: str) -> bool:
    """Validate sequence preservation, monotonically increasing timestamps, and ordering."""
    print(f"Validating file contract: {filename}")

    seq_trackers: Dict[str, int] = {}
    last_timestamp = 0
    line_num = 0

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line_num += 1
            stripped = line.strip()
            if not stripped:
                continue

            try:
                event = json.loads(stripped)
            except Exception as e:
                print(f"ERROR: Line {line_num} has invalid JSON: {e}", file=sys.stderr)
                return False

            drone_id = event.get("drone_id")
            seq = event.get("seq")
            ts = event.get("timestamp")

            if not drone_id or seq is None or ts is None:
                print(
                    f"ERROR: Line {line_num} is missing required fields (drone_id, seq, timestamp)",
                    file=sys.stderr,
                )
                return False

            # 1. Timestamp monotonicity check
            if ts < last_timestamp:
                print(
                    f"ERROR: Line {line_num} has a non-monotonic timestamp: {ts} < {last_timestamp}",
                    file=sys.stderr,
                )
                return False
            last_timestamp = ts

            # 2. Sequence continuity check per drone
            expected_seq = seq_trackers.get(drone_id, 0)
            if seq != expected_seq:
                print(
                    f"ERROR: Drone {drone_id} sequence mismatch at line {line_num}. Expected {expected_seq}, got {seq}",
                    file=sys.stderr,
                )
                return False
            seq_trackers[drone_id] = expected_seq + 1

    print("PASS: Monotonic timestamps and strict sequence count validation.")
    return True


def compare_replays(file1: str, file2: str) -> bool:
    """Validate replay determinism by comparing two files for structural and payload equivalence."""
    print(f"Comparing replays: {file1} vs {file2}")

    events1 = []
    events2 = []

    with open(file1, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events1.append(json.loads(line.strip()))

    with open(file2, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events2.append(json.loads(line.strip()))

    if len(events1) != len(events2):
        print(
            f"ERROR: Message count mismatch. {file1} has {len(events1)} events, {file2} has {len(events2)}",
            file=sys.stderr,
        )
        return False

    # Sort both to allow structural compare independently of concurrent networking jitter
    # We sort by (drone_id, seq)
    events1.sort(key=lambda x: (x["drone_id"], x["seq"]))
    events2.sort(key=lambda x: (x["drone_id"], x["seq"]))

    for i, (e1, e2) in enumerate(zip(events1, events2)):
        if e1["drone_id"] != e2["drone_id"]:
            print(
                f"ERROR: Drone ID mismatch at sorted index {i}: {e1['drone_id']} vs {e2['drone_id']}",
                file=sys.stderr,
            )
            return False

        if e1["seq"] != e2["seq"]:
            print(
                f"ERROR: Sequence mismatch at sorted index {i}: {e1['seq']} vs {e2['seq']}",
                file=sys.stderr,
            )
            return False

        # Compare payload structures deterministically
        p1 = e1["payload"]
        p2 = e2["payload"]

        # Compare numerical properties within a float tolerance to avoid slight math precision changes
        for key in ["lat", "lon", "alt", "roll", "pitch", "yaw"]:
            val1 = p1[key]
            val2 = p2[key]
            if abs(val1 - val2) > 1e-6:
                print(
                    f"ERROR: Value drift detected for {key} at index {i}: {val1} vs {val2}",
                    file=sys.stderr,
                )
                return False

        if p1["battery"] != p2["battery"]:
            print(
                f"ERROR: Battery mismatch at index {i}: {p1['battery']} vs {p2['battery']}",
                file=sys.stderr,
            )
            return False

        if p1["mode"] != p2["mode"]:
            print(
                f"ERROR: Mode mismatch at index {i}: {p1['mode']} vs {p2['mode']}",
                file=sys.stderr,
            )
            return False

    print("PASS: Replay output is structurally and numerically identical.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Telemetry Workload Validator")
    parser.add_argument(
        "--mode", choices=["validate", "compare"], required=True, help="Validation mode"
    )
    parser.add_argument(
        "--file1", type=str, required=True, help="Primary JSON Lines file"
    )
    parser.add_argument(
        "--file2", type=str, help="Secondary JSON Lines file for comparison"
    )
    args = parser.parse_args()

    if args.mode == "validate":
        success = validate_file_contract(args.file1)
    elif args.mode == "compare":
        if not args.file2:
            print("ERROR: --file2 is required in compare mode.", file=sys.stderr)
            sys.exit(1)
        success = compare_replays(args.file1, args.file2)
    else:
        success = False

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
