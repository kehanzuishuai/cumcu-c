from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from common_data import PROJECT_ROOT, load_attachment2, load_attachment3


EXP_ROOT = PROJECT_ROOT / "experiments" / "q3_alpha_calibration"
SUMMARY_PATH = EXP_ROOT / "results" / "alpha_calibration_summary.json"
LOCK_PATH = EXP_ROOT / "intermediate" / "selection_lock.json"
OUTPUT = EXP_ROOT / "validation" / "alpha_calibration_independent.json"
N = 144
LOOKBACK_DAYS = 28
RESIDUAL_WINDOW_DAYS = 56
ISSUE_HOURS = (0, 6, 12, 18)
VALIDATION_START = date(2025, 7, 1)
VALIDATION_END = date(2025, 9, 30)
TOL = 1e-6


def weighted(values: np.ndarray, dates: list[date], cutoff_idx: int, target_date: date) -> np.ndarray:
    candidates = [
        idx for idx in range(max(0, cutoff_idx - LOOKBACK_DAYS), cutoff_idx)
        if dates[idx].weekday() == target_date.weekday()
    ]
    if not candidates:
        candidates = [cutoff_idx - 1]
    weights = np.arange(1, len(candidates) + 1, dtype=float)
    return np.average(values[candidates], axis=0, weights=weights)


def load_forecast(alpha: float, load_kw: np.ndarray, dates: list[date], day_idx: int, issue_hour: int) -> np.ndarray:
    start = issue_hour * 6
    today = weighted(load_kw, dates, day_idx, dates[day_idx])
    tomorrow = weighted(load_kw, dates, day_idx, dates[day_idx] + timedelta(days=1))
    horizon = np.concatenate([today[start:], tomorrow[:start]])
    if start:
        ratio_raw = float(np.sum(load_kw[day_idx, :start]) / np.sum(today[:start]))
        ratio = 1.0 + alpha * (ratio_raw - 1.0)
        horizon[: N - start] *= ratio
    return horizon


def pv_forecast(leads: np.ndarray, boundary: float) -> np.ndarray:
    x = np.arange(1, 145, dtype=float) / 6.0
    return np.interp(x, np.arange(25, dtype=float), np.concatenate([[boundary], np.asarray(leads, dtype=float)]))


def actual_horizon(values: np.ndarray, day_idx: int, issue_hour: int) -> np.ndarray:
    start = issue_hour * 6
    return np.concatenate([values[day_idx, start:], values[day_idx + 1, :start]])


def signature(alpha: float, load_kw: np.ndarray, pv_kw: np.ndarray, forecasts: np.ndarray, dates: list[date]) -> dict[str, Any]:
    val_start_idx = dates.index(VALIDATION_START)
    val_end_idx = dates.index(VALIDATION_END)
    residual = np.full((val_end_idx + 1, 4, N), np.nan, dtype=float)
    for day_idx in range(1, val_end_idx + 1):
        for issue_idx, issue_hour in enumerate(ISSUE_HOURS):
            start = issue_hour * 6
            boundary = float(pv_kw[day_idx - 1, -1] if issue_hour == 0 else pv_kw[day_idx, start - 1])
            f_load = load_forecast(alpha, load_kw, dates, day_idx, issue_hour)
            f_pv = pv_forecast(forecasts[day_idx, issue_idx], boundary)
            residual[day_idx, issue_idx] = (
                actual_horizon(load_kw, day_idx, issue_hour)
                - actual_horizon(pv_kw, day_idx, issue_hour)
                - (f_load - f_pv)
            )
    digest = hashlib.sha256()
    values = []
    for day_idx in range(val_start_idx, val_end_idx + 1):
        first = max(1, day_idx - RESIDUAL_WINDOW_DAYS)
        for issue_idx in range(4):
            candidates = np.arange(first, day_idx, dtype=int)
            valid = candidates[np.isfinite(residual[candidates, issue_idx]).all(axis=1)]
            uplift = np.quantile(residual[valid, issue_idx], 0.8, axis=0)
            digest.update(np.asarray(uplift, dtype="<f8").tobytes())
            values.append(uplift)
    merged = np.concatenate(values)
    return {"q80_sha256": digest.hexdigest(), "q80_mean_kw": float(np.mean(merged))}


def close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_formal_hashes() -> dict[str, str]:
    paths = [p for folder in (PROJECT_ROOT / "results", PROJECT_ROOT / "validation") for p in folder.rglob("*") if p.is_file()]
    for name in ("final_promotion_alpha05_manifest.json", "documentation_freeze_manifest.json"):
        path = PROJECT_ROOT / "intermediate" / name
        if path.exists():
            paths.append(path)
    return {str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"): file_sha256(p) for p in sorted(paths)}


def validate_rows(rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    errors = []
    by_alpha = {f"{row['alpha']:.2f}": row for row in rows}
    base = by_alpha["0.00"]["period"]
    current = by_alpha["0.50"]["period"]
    for row in rows:
        p = row["period"]
        alpha = row["alpha"]
        checks = {
            "normal_identity": close(p["normal_settlement_cost_yuan"], p["base_plan_cost_yuan"] - p["downward_credit_yuan"] + p["upward_adjustment_cost_yuan"]),
            "total_identity": close(p["total_cost_yuan"], p["normal_settlement_cost_yuan"] + p["emergency_cost_yuan"]),
            "delta0": close(row["delta_vs_alpha0_yuan"], p["total_cost_yuan"] - base["total_cost_yuan"]),
            "delta05": close(row["delta_vs_alpha05_yuan"], p["total_cost_yuan"] - current["total_cost_yuan"]),
            "inventory": close(p["inventory_adjusted_cost_yuan"], p["total_cost_yuan"] + p["inventory_value_price_yuan_per_kwh"] * (p["soc_open_kwh"] - p["soc_final_kwh"])),
            "native_checks": row["checks"]["status"] == "PASS" and all(row["checks"]["pass_flags"].values()),
        }
        for name, flag in checks.items():
            if not flag:
                errors.append(f"alpha={alpha:.2f}:{name}")
    return not errors, errors


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    annual = load_attachment2()
    forecasts = load_attachment3()
    rows = summary["validation_rows"]
    coarse_expected = [round(i / 10, 10) for i in range(11)]
    alpha_set = {round(row["alpha"], 10) for row in rows}
    row_checks = {}
    row_errors = {}
    for name, group in (
        ("validation", rows),
        ("q3_holdout", summary["q3_holdout_rows"]),
        ("q4_3_holdout", summary["q4_3_holdout_rows"]),
    ):
        row_checks[name], row_errors[name] = validate_rows(group)

    independent_signatures = {}
    signature_matches = {}
    for row in rows:
        key = f"{row['alpha']:.2f}"
        rebuilt = signature(row["alpha"], annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], annual["dates"])
        independent_signatures[key] = rebuilt
        expected = row["risk_recomputation"]
        signature_matches[key] = rebuilt["q80_sha256"] == expected["q80_sha256"] and close(rebuilt["q80_mean_kw"], expected["q80_mean_kw"], 1e-10)

    fine_rows = [row for row in rows if round(row["alpha"], 10) in {round(x, 10) for x in summary["fine_grid"]}]
    fine_min = min(row["period"]["total_cost_yuan"] for row in fine_rows)
    tied = [row for row in fine_rows if row["period"]["total_cost_yuan"] <= fine_min + 1.0]
    reproduced = min(tied, key=lambda row: (row["period"]["emergency_purchase_kwh"], row["monthly_delta_std_yuan"], row["alpha"]))["alpha"]
    selected = summary["selected_alpha"]
    allowed_holdout = {0.0, 0.5, round(selected, 10)}
    formal_now = current_formal_hashes()
    flags = {
        "lock_precedes_summary": LOCK_PATH.stat().st_mtime_ns <= SUMMARY_PATH.stat().st_mtime_ns,
        "lock_status": lock["status"] == "LOCKED_BEFORE_HOLDOUT",
        "lock_equals_summary": close(lock["selected_alpha"], selected, 1e-12),
        "coarse_grid_exact": summary["coarse_grid"] == coarse_expected and set(coarse_expected).issubset(alpha_set),
        "fine_grid_present": {round(x, 10) for x in summary["fine_grid"]}.issubset(alpha_set),
        "selection_reproduced": close(reproduced, selected, 1e-12),
        "holdout_alpha_scope_q3": {round(row["alpha"], 10) for row in summary["q3_holdout_rows"]} == allowed_holdout,
        "holdout_alpha_scope_q4_3": {round(row["alpha"], 10) for row in summary["q4_3_holdout_rows"]} == allowed_holdout,
        "q4_price_rule": summary["q4_3_price_model"] == "weekday_mean_28d; intraday scale OFF; AR(1) OFF",
        "validation_numeric_identities": row_checks["validation"],
        "q3_holdout_numeric_identities": row_checks["q3_holdout"],
        "q4_3_holdout_numeric_identities": row_checks["q4_3_holdout"],
        "all_q80_recomputed_independently": all(signature_matches.values()),
        "formal_results_unchanged": summary["formal_results_unchanged"] and summary["formal_hashes_before"] == summary["formal_hashes_after"] == formal_now,
        "no_promotion": summary["promotion"] == "NOT_AUTHORIZED",
    }
    report = {
        "schema_version": 1,
        "status": "PASS" if all(flags.values()) else "FAIL",
        "pass_flags": flags,
        "selected_alpha": selected,
        "row_errors": row_errors,
        "q80_signature_matches": signature_matches,
        "independent_q80_signatures": independent_signatures,
        "formal_hashes_recomputed": formal_now,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "selected_alpha": selected, "checks": flags}, ensure_ascii=False))
    if report["status"] != "PASS":
        raise RuntimeError("independent alpha calibration validation failed")


if __name__ == "__main__":
    main()
