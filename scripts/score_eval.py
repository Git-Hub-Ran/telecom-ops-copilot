#!/usr/bin/env python3
"""Verify eval results CSV against locked metric thresholds from EVAL.md.

Usage:
    python scripts/score_eval.py [csv_path]

Auto-selects the most recent eval/results_*.csv when no path is given.
Reads precomputed per-row scores. No Azure credentials required.
Exits 0 if the four scored metrics pass, 1 if any fail.
Latency p95 is printed but excluded from the exit code (architectural constraint).

Run manually before merging to verify eval metrics have not regressed against
the committed results CSV. Not included in CI because current scores are below
threshold targets; see eval/BASELINE_NOTES.md for documented justifications.
"""

import csv
import glob
import math
import sys
from pathlib import Path

DEFAULT_CSV = max(glob.glob("eval/results_*.csv"), default="eval/results_20260811_1335.csv")

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
    csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV)

    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found", file=sys.stderr)
        return 1

    print(f"Scoring: {csv_path}\n")
    metrics = compute_metrics(csv_path)

    print(f"{'Metric':<25} {'Value':>10}  {'Threshold':>12}  Result")
    print("-" * 58)

    all_pass = True
    for key, (op, threshold) in THRESHOLDS.items():
        value = metrics[key]
        passed = _passes(value, op, threshold)
        if not passed:
            all_pass = False
        label, fmt, thr_str = DISPLAY[key]
        print(f"{label:<25} {fmt.format(value):>10}  {thr_str:>12}  {'PASS' if passed else 'FAIL'}")

    lat = metrics["latency_p95_ms"]
    print(f"{'Latency p95':<25} {f'{lat:.0f}ms':>10}  {'<= 5000ms':>12}  INFO (architectural constraint)")

    print()
    if all_pass:
        print("Result: all metrics PASS")
        return 0
    print("Result: one or more metrics FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
