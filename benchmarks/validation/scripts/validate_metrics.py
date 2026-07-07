#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

SERIES_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([^}]*)\})?\s+(.+)$")


def _fetch_metrics(base_url: str, timeout_seconds: float) -> str:
    url = f"{base_url.rstrip('/')}/metrics"
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise RuntimeError(f"/metrics returned status={response.status}")
        return response.read().decode("utf-8")


def _parse_labels(raw: str | None) -> set[str]:
    if not raw:
        return set()
    labels = set()
    for token in raw.split(","):
        key, _, _ = token.partition("=")
        labels.add(key.strip())
    return labels


def _parse_metrics(text: str) -> tuple[set[str], list[tuple[str, set[str]]]]:
    families: set[str] = set()
    series: list[tuple[str, set[str]]] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# HELP"):
            _, _, family, *_ = stripped.split(" ")
            families.add(family)
            continue
        if stripped.startswith("# TYPE"):
            continue

        match = SERIES_RE.match(stripped)
        if not match:
            raise RuntimeError(f"Unable to parse metric line: {stripped}")
        name = match.group(1)
        labels = _parse_labels(match.group(3))
        series.append((name, labels))

    return families, series


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Prometheus metric families, labels, and extra series"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument(
        "--contract-spec",
        default=str(
            Path(__file__).resolve().parent.parent / "config" / "contract_spec.json"
        ),
    )
    args = parser.parse_args()

    spec = json.loads(Path(args.contract_spec).read_text(encoding="utf-8"))["metrics"]
    required_families = set(spec["required_families"])
    allowed_series = set(spec["allowed_series"])
    label_rules: dict[str, list[str]] = spec["label_rules"]

    try:
        raw_metrics = _fetch_metrics(args.base_url, args.timeout_seconds)
        families, series = _parse_metrics(raw_metrics)

        missing_families = sorted(required_families - families)
        if missing_families:
            raise AssertionError(f"Missing metric families: {missing_families}")

        seen_series = {name for name, _ in series}
        extra_series = sorted(seen_series - allowed_series)
        if extra_series:
            raise AssertionError(f"Extra metric series detected: {extra_series}")

        missing_series = sorted(
            (allowed_series - seen_series) - {"ws_messages_dropped_total"}
        )
        if missing_series:
            raise AssertionError(
                f"Missing metric series: {missing_series}. "
                "If this is expected for zero-valued counters, generate traffic first."
            )

        for name, labels in series:
            expected_labels = set(label_rules.get(name, []))
            if labels != expected_labels:
                raise AssertionError(
                    f"Label mismatch for metric {name}. "
                    f"expected={sorted(expected_labels)} actual={sorted(labels)}"
                )
    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    print("PASS: metrics families/labels/series contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
