#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProfileResult:
    profile: str
    requests_rate: float
    failure_rate: float
    p95_ms: float


def _summary_metric(
    summary: dict, metric: str, value: str, default: float = 0.0
) -> float:
    return float(summary.get("metrics", {}).get(metric, {}).get(value, default))


def _run_k6(
    k6_script: Path,
    base_url: str,
    profile: str,
    duration: str,
    report_path: Path,
) -> dict:
    command = [
        "k6",
        "run",
        "-e",
        f"BASE_URL={base_url}",
        "-e",
        f"PROFILE={profile}",
        "-e",
        f"DURATION={duration}",
        "--summary-export",
        str(report_path),
        str(k6_script),
    ]
    subprocess.run(command, check=True)
    return json.loads(report_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run k6 telemetry profiles and enforce load consistency rules"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--criteria",
        default=str(
            Path(__file__).resolve().parent.parent
            / "config"
            / "readiness_criteria.json"
        ),
    )
    parser.add_argument(
        "--k6-script",
        default=str(
            Path(__file__).resolve().parent.parent.parent
            / "k6"
            / "scenarios"
            / "telemetry.js"
        ),
    )
    parser.add_argument(
        "--reports-dir",
        default=str(Path(__file__).resolve().parent.parent / "reports"),
    )
    args = parser.parse_args()

    if shutil.which("k6") is None:
        print("VALIDATION FAILED: k6 binary not found in PATH", file=sys.stderr)
        return 1

    criteria = json.loads(Path(args.criteria).read_text(encoding="utf-8"))[
        "load_consistency"
    ]
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    profiles: list[str] = criteria["profiles"]
    duration = criteria["duration"]
    max_failure_rate = float(criteria["max_failure_rate"])
    min_rate_ratio = float(criteria["min_rate_ratio"])
    max_p95_growth_500_over_100 = float(criteria["max_p95_growth_500_over_100"])
    max_p95_growth_1000_over_500 = float(criteria["max_p95_growth_1000_over_500"])

    results: list[ProfileResult] = []
    script_path = Path(args.k6_script)

    try:
        for profile in profiles:
            report_path = reports_dir / f"k6_summary_profile_{profile}.json"
            summary = _run_k6(
                k6_script=script_path,
                base_url=args.base_url,
                profile=profile,
                duration=duration,
                report_path=report_path,
            )

            req_rate = _summary_metric(summary, "http_reqs", "rate")
            failed_rate = _summary_metric(summary, "http_req_failed", "rate")
            p95_ms = _summary_metric(summary, "http_req_duration", "p(95)")
            results.append(
                ProfileResult(
                    profile=profile,
                    requests_rate=req_rate,
                    failure_rate=failed_rate,
                    p95_ms=p95_ms,
                )
            )

        profile_index = {item.profile: item for item in results}

        for item in results:
            if item.failure_rate > max_failure_rate:
                raise AssertionError(
                    f"profile={item.profile} failure_rate={item.failure_rate:.4f} exceeds {max_failure_rate:.4f}"
                )

        telemetry_rate = 2
        for item in results:
            expected_rate = int(item.profile) * telemetry_rate
            rate_ratio = item.requests_rate / expected_rate
            if rate_ratio < min_rate_ratio:
                raise AssertionError(
                    f"profile={item.profile} req_rate={item.requests_rate:.2f} expected={expected_rate:.2f} "
                    f"ratio={rate_ratio:.3f} below {min_rate_ratio:.3f}"
                )

        p95_100 = profile_index["100"].p95_ms
        p95_500 = profile_index["500"].p95_ms
        p95_1000 = profile_index["1000"].p95_ms
        if p95_500 > p95_100 * max_p95_growth_500_over_100:
            raise AssertionError(
                f"p95 growth 500/100 too high: {p95_500:.2f}/{p95_100:.2f} > {max_p95_growth_500_over_100:.2f}"
            )
        if p95_1000 > p95_500 * max_p95_growth_1000_over_500:
            raise AssertionError(
                f"p95 growth 1000/500 too high: {p95_1000:.2f}/{p95_500:.2f} > {max_p95_growth_1000_over_500:.2f}"
            )

    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    print("PASS: load consistency gate")
    for result in results:
        print(
            f"profile={result.profile} req_rate={result.requests_rate:.2f} "
            f"failure_rate={result.failure_rate:.4f} p95_ms={result.p95_ms:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
