#!/usr/bin/env python3
"""Verify eval results CSV against locked thresholds or a previous run.

Usage:
    python scripts/score_eval.py <csv_path>
    python scripts/score_eval.py <csv_path> --baseline <previous_results.csv>

Two modes:

Threshold mode (no --baseline): compares each metric against the locked targets
in docs/EVAL.md. Those targets are aspirational and several currently fail, so
this mode is for manual review, not CI. See eval/BASELINE_NOTES.md for the
documented justifications.

Ratchet mode (--baseline given): compares each metric against the same metric
computed from the baseline CSV, allowing a 1.5 percentage point buffer for
run-to-run variance. Fails only on regression, so it stays green while the
aspirational targets remain unmet. This is what CI runs.

The buffer is 1.5pp because intent accuracy is scored over 100 rows, making one
query worth 1.0pp; anything narrower would fail on a single query flipping. Note
that escalation precision and recall are scored over roughly 14 rows and have been
observed to swing about 7pp between identical runs, which this buffer does not
absorb; see eval/BASELINE_NOTES.md for that variance.

The results CSV must be named explicitly. There is no default, because the most
recent file is not necessarily the run you want scored: the committed results
include runs measured against prompts that were later reverted, and picking the
newest silently scores one of those. Reads precomputed per-row scores; no Azure
credentials required. Latency p95 never affects the exit code in either mode,
though ratchet mode reports a regression.
"""

import argparse
import csv
import math
import sys
from pathlib import Path

# 1.5 percentage points. Intent accuracy is scored over 100 rows, so a single
# query is worth 1.0pp; a narrower buffer could not absorb even one query flipping.
RATCHET_BUFFER = 0.015

THRESHOLDS: dict[str, tuple[str, float]] = {
    "intent_accuracy":      (">=", 0.90),
    "tool_selection":       (">=", 0.85),
    "escalation_precision": (">=", 0.85),
    "escalation_recall":    (">=", 0.80),
}

DISPLAY: dict[str, tuple[str, str, str]] = {
    "intent_accuracy":      ("Intent accuracy",      "{:.1%}",   ">= 90%"),
    "tool_selection":       ("Tool selection",       "{:.1%}",   ">= 85%"),
    "escalation_precision": ("Escalation precision", "{:.1%}",   ">= 85%"),
    "escalation_recall":    ("Escalation recall",    "{:.1%}",   ">= 80%"),
}


def _float(value: str) -> float | None:
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def _bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in ("true", "1"):
        return True
    if v in ("false", "0"):
        return False
    return None


def _p95(data: list[float]) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


def compute_metrics(path: Path) -> dict[str, float]:
    intent_scores: list[float] = []
    tool_scores: list[float] = []
    latencies: list[float] = []
    expected_esc: list[bool] = []
    actual_esc: list[bool] = []

    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ic = _float(row.get("intent_correct", ""))
            if ic is not None:
                intent_scores.append(ic)

            ts = _float(row.get("tool_score", ""))
            if ts is not None:
                tool_scores.append(ts)

            lat = _float(row.get("latency_ms", ""))
            if lat is not None:
                latencies.append(lat)

            exp = _bool(row.get("expected_escalation", ""))
            act = _bool(row.get("actual_escalation", ""))
            if exp is not None and act is not None:
                expected_esc.append(exp)
                actual_esc.append(act)

    tp = sum(1 for e, a in zip(expected_esc, actual_esc) if e and a)
    fp = sum(1 for e, a in zip(expected_esc, actual_esc) if not e and a)
    fn = sum(1 for e, a in zip(expected_esc, actual_esc) if e and not a)

    return {
        "intent_accuracy":      sum(intent_scores) / len(intent_scores) if intent_scores else 0.0,
        "tool_selection":       sum(tool_scores) / len(tool_scores) if tool_scores else 0.0,
        "escalation_precision": tp / (tp + fp) if (tp + fp) > 0 else 0.0,
        "escalation_recall":    tp / (tp + fn) if (tp + fn) > 0 else 0.0,
        "latency_p95_ms":       _p95(latencies),
    }


def _passes(value: float, op: str, threshold: float) -> bool:
    return value >= threshold if op == ">=" else value <= threshold


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify eval results against EVAL.md thresholds or a baseline run."
    )
    parser.add_argument(
        "csv_path",
        help="Results CSV to score, e.g. eval/results_YYYYMMDD_HHMM.csv",
    )
    parser.add_argument(
        "--baseline", default=None,
        help="Previous results CSV; enables ratchet mode (fail only on regression)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found", file=sys.stderr)
        return 1

    metrics = compute_metrics(csv_path)

    baseline_metrics: dict[str, float] | None = None
    if args.baseline is not None:
        baseline_path = Path(args.baseline)
        if not baseline_path.exists():
            print(f"ERROR: {baseline_path} not found", file=sys.stderr)
            return 1
        baseline_metrics = compute_metrics(baseline_path)
        print(f"Scoring: {csv_path}")
        print(f"Ratchet baseline: {baseline_path} (buffer {RATCHET_BUFFER:.1%})\n")
    else:
        print(f"Scoring: {csv_path}\n")

    print(f"{'Metric':<25} {'Value':>10}  {'Threshold':>12}  Result")
    print("-" * 58)

    all_pass = True
    for key, (op, threshold) in THRESHOLDS.items():
        value = metrics[key]
        label, fmt, thr_str = DISPLAY[key]
        if baseline_metrics is not None:
            floor = baseline_metrics[key] - RATCHET_BUFFER
            passed = value >= floor
            thr_str = f">= {floor:.1%}"
        else:
            passed = _passes(value, op, threshold)
        if not passed:
            all_pass = False
        print(f"{label:<25} {fmt.format(value):>10}  {thr_str:>12}  {'PASS' if passed else 'FAIL'}")

    lat = metrics["latency_p95_ms"]
    lat_note = "INFO (architectural constraint)"
    if baseline_metrics is not None and lat > baseline_metrics["latency_p95_ms"]:
        delta = lat - baseline_metrics["latency_p95_ms"]
        lat_note = f"INFO (regressed {delta:.0f}ms vs baseline, not blocking)"
    print(f"{'Latency p95':<25} {f'{lat:.0f}ms':>10}  {'<= 5000ms':>12}  {lat_note}")

    print()
    mode = "ratchet" if baseline_metrics is not None else "threshold"
    if all_pass:
        print(f"Result: all metrics PASS ({mode} mode)")
        return 0
    print(f"Result: one or more metrics FAIL ({mode} mode)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
