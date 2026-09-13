from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, load_attachment3, load_attachment4
import q3_solve as q3
from q3_p1_load_feedback_ablation import make_issue_forecast


EXP_ROOT = PROJECT_ROOT / "experiments" / "q3_alpha_calibration"
RESULTS = EXP_ROOT / "results"
VALIDATION = EXP_ROOT / "validation"
INTERMEDIATE = EXP_ROOT / "intermediate"
LOCK = INTERMEDIATE / "selection_lock.json"

WARMUP_START = "2025-02-01"
WARMUP_END = "2025-06-30"
VALIDATION_START = "2025-07-01"
VALIDATION_END = "2025-09-30"
HOLDOUT_START = "2025-10-01"
HOLDOUT_END = "2025-12-31"
TIE_TOL_YUAN = 1.0


class DateView(Sequence[date]):
    """Keep full indexed history while exposing a shorter length to the rolling engine."""

    def __init__(self, values: list[date], visible_length: int):
        self.values = values
        self.visible_length = visible_length

    def __len__(self) -> int:
        return self.visible_length

    def __getitem__(self, key):
        return self.values[key]

    def __iter__(self) -> Iterator[date]:
        return iter(self.values[: self.visible_length])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def formal_hashes() -> dict[str, str]:
    paths = [p for folder in (PROJECT_ROOT / "results", PROJECT_ROOT / "validation") for p in folder.rglob("*") if p.is_file()]
    for name in ("final_promotion_alpha05_manifest.json", "documentation_freeze_manifest.json"):
        path = PROJECT_ROOT / "intermediate" / name
        if path.exists():
            paths.append(path)
    return {str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(p) for p in sorted(paths)}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def round_alpha(value: float) -> float:
    return round(float(value) + 0.0, 10)


def alpha_key(alpha: float) -> str:
    return f"{round_alpha(alpha):.2f}"


def date_index(dates: list[date], value: str) -> int:
    return dates.index(date.fromisoformat(value))


def cache_signature(residual: np.ndarray, day_indices: range) -> dict[str, Any]:
    digest = hashlib.sha256()
    uplift_values = []
    first_used = 10**9
    last_used = -1
    for day_idx in day_indices:
        for issue_idx in range(4):
            uplift, first, last = q3.risk_uplift(residual, day_idx, issue_idx)
            digest.update(np.asarray(uplift, dtype="<f8").tobytes())
            uplift_values.append(uplift)
            first_used = min(first_used, first)
            last_used = max(last_used, last)
    values = np.concatenate(uplift_values)
    return {
        "q80_sha256": digest.hexdigest(),
        "q80_mean_kw": float(np.mean(values)),
        "q80_min_kw": float(np.min(values)),
        "q80_max_kw": float(np.max(values)),
        "risk_first_history_index": int(first_used),
        "risk_last_history_index": int(last_used),
    }


def period_summary(run: dict[str, Any], start: str, end: str, mean_price: float) -> dict[str, Any]:
    rows = [row for row in run["daily"] if start <= row["date"] <= end]
    if not rows:
        raise ValueError(f"empty period {start}..{end}")
    additive = (
        "original_purchase_kwh", "effective_purchase_kwh", "upward_adjustment_kwh",
        "downward_adjustment_kwh", "emergency_purchase_kwh", "base_plan_cost_yuan",
        "downward_credit_yuan", "upward_adjustment_cost_yuan", "normal_settlement_cost_yuan",
        "emergency_cost_yuan", "total_cost_yuan", "charge_kwh", "discharge_kwh",
        "surplus_discard_kwh",
    )
    out = {key: float(sum(float(row[key]) for row in rows)) for key in additive}
    out.update({
        "start": start,
        "end": end,
        "days": len(rows),
        "soc_open_kwh": float(rows[0]["soc_open_kwh"]),
        "soc_final_kwh": float(rows[-1]["soc_close_kwh"]),
        "inventory_value_price_yuan_per_kwh": float(mean_price),
    })
    out["inventory_adjusted_cost_yuan"] = float(
        out["total_cost_yuan"] + mean_price * (out["soc_open_kwh"] - out["soc_final_kwh"])
    )
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"total_cost_yuan": 0.0, "emergency_purchase_kwh": 0.0})
    for row in rows:
        month = row["date"][:7]
        monthly[month]["total_cost_yuan"] += float(row["total_cost_yuan"])
        monthly[month]["emergency_purchase_kwh"] += float(row["emergency_purchase_kwh"])
    out["monthly"] = {month: values for month, values in sorted(monthly.items())}
    return out


def run_checks(run: dict[str, Any]) -> dict[str, Any]:
    agg = run["aggregate"]
    detail = run["detail"]
    daily = run["daily"]
    info = sum(row["train_end_date"] >= row["date"] or row["residual_history_end_date"] >= row["date"] for row in daily)
    simultaneous = sum(
        float(row["charge_bus_kwh"]) > q3.POSITIVE_TOL_KWH and float(row["discharge_bus_kwh"]) > q3.POSITIVE_TOL_KWH
        for row in detail
    )
    emergency_charge = sum(
        float(row["emergency_purchase_kwh"]) > q3.POSITIVE_TOL_KWH and float(row["charge_bus_kwh"]) > q3.POSITIVE_TOL_KWH
        for row in detail
    )
    max_charge = max(float(row["charge_bus_kwh"]) for row in detail)
    max_discharge = max(float(row["discharge_bus_kwh"]) for row in detail)
    cost_recompute = float(sum(float(row["total_cost_yuan"]) for row in daily))
    flags = {
        "information_cutoff": info == 0,
        "actual_balance": agg["max_actual_balance_residual_kwh"] <= q3.SOLVER_TOL_KWH,
        "actual_state": agg["max_actual_state_residual_kwh"] <= q3.SOLVER_TOL_KWH,
        "soc_bounds": agg["soc_min_kwh"] >= q3.SOC_MIN - q3.SOLVER_TOL_KWH and agg["soc_max_kwh"] <= q3.SOC_MAX + q3.SOLVER_TOL_KWH,
        "storage_power": max(max_charge, max_discharge) <= q3.FLOW_MAX_KWH + q3.SOLVER_TOL_KWH,
        "crossday_soc": agg["max_crossday_soc_gap_kwh"] <= q3.SOLVER_TOL_KWH,
        "mutual_exclusion": simultaneous == 0,
        "emergency_not_charging": emergency_charge == 0,
        "plan_balance": agg["max_plan_balance_residual_kwh"] <= q3.SOLVER_TOL_KWH,
        "plan_state": agg["max_plan_state_residual_kwh"] <= q3.SOLVER_TOL_KWH,
        "adjustment_link": agg["max_adjustment_link_residual_kwh"] <= q3.SOLVER_TOL_KWH,
        "plan_mutual_exclusion": agg["plan_simultaneous_positive_slots"] == 0,
        "cost_reconciliation": abs(cost_recompute - agg["total_cost_yuan"]) <= 1e-6,
    }
    return {
        "status": "PASS" if all(flags.values()) else "FAIL",
        "pass_flags": flags,
        "metrics": {
            "information_violations": int(info),
            "simultaneous_slots": int(simultaneous),
            "emergency_charge_overlap_slots": int(emergency_charge),
            "max_charge_kwh_per_slot": max_charge,
            "max_discharge_kwh_per_slot": max_discharge,
            "max_balance_residual_kwh": agg["max_actual_balance_residual_kwh"],
            "max_state_residual_kwh": agg["max_actual_state_residual_kwh"],
            "max_crossday_soc_gap_kwh": agg["max_crossday_soc_gap_kwh"],
            "cost_recompute_difference_yuan": cost_recompute - agg["total_cost_yuan"],
        },
    }


def q3_validation_run(alpha: float, annual: dict, forecasts: dict, fixed: dict, dates: list[date], val_end_idx: int) -> dict[str, Any]:
    native = q3.issue_forecast
    q3.issue_forecast = make_issue_forecast(alpha)
    try:
        cache_dates = DateView(dates, val_end_idx + 2)
        run_dates = DateView(dates, val_end_idx + 1)
        residual, _, _ = q3.build_forecast_caches(
            annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], cache_dates, "linear"
        )
        run = q3.run_strategy(
            name=f"alpha_validation_{alpha_key(alpha)}", update_hours=[6, 12, 18], interpolation="linear",
            load_kw=annual["load_kw"], pv_kw=annual["pv_kw"], forecast3_kw=forecasts["forecast_kw"],
            dates=run_dates, price=fixed["price_yuan_per_kwh"], residual_cache=residual,
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=True,
        )
    finally:
        q3.issue_forecast = native
    start_idx = date_index(dates, VALIDATION_START)
    period = period_summary(run, VALIDATION_START, VALIDATION_END, float(np.mean(fixed["price_yuan_per_kwh"])))
    return {
        "alpha": round_alpha(alpha),
        "period": period,
        "risk_recomputation": cache_signature(residual, range(start_idx, val_end_idx + 1)),
        "checks": run_checks(run),
    }


def full_run(alpha: float, annual: dict, forecasts: dict, fixed: dict, dates: list[date], realtime: dict | None) -> dict[str, Any]:
    native = q3.issue_forecast
    q3.issue_forecast = make_issue_forecast(alpha)
    try:
        residual, _, _ = q3.build_forecast_caches(
            annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], dates, "linear"
        )
        kwargs = {}
        if realtime is not None:
            kwargs = {
                "actual_price_by_date": realtime["price_yuan_per_kwh"],
                "planning_price_kind": "weekday_mean_28d",
            }
        run = q3.run_strategy(
            name=f"{'q4_3' if realtime is not None else 'q3'}_holdout_alpha_{alpha_key(alpha)}",
            update_hours=[6, 12, 18], interpolation="linear",
            load_kw=annual["load_kw"], pv_kw=annual["pv_kw"], forecast3_kw=forecasts["forecast_kw"],
            dates=dates, price=fixed["price_yuan_per_kwh"], residual_cache=residual,
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=True, **kwargs,
        )
    finally:
        q3.issue_forecast = native
    if realtime is None:
        mean_price = float(np.mean(fixed["price_yuan_per_kwh"]))
    else:
        left = date_index(dates, HOLDOUT_START)
        right = date_index(dates, HOLDOUT_END)
        mean_price = float(np.mean(realtime["price_yuan_per_kwh"][left : right + 1]))
    return {
        "alpha": round_alpha(alpha),
        "period": period_summary(run, HOLDOUT_START, HOLDOUT_END, mean_price),
        "checks": run_checks(run),
    }


def selection_key(row: dict[str, Any], base_monthly: dict[str, dict[str, float]]) -> tuple[float, float, float]:
    cost = row["period"]["total_cost_yuan"]
    emergency = row["period"]["emergency_purchase_kwh"]
    deltas = [
        row["period"]["monthly"][month]["total_cost_yuan"] - base_monthly[month]["total_cost_yuan"]
        for month in sorted(base_monthly)
    ]
    return cost, emergency, float(np.std(deltas))


def select_row(rows: list[dict[str, Any]], base_monthly: dict[str, dict[str, float]]) -> dict[str, Any]:
    min_cost = min(row["period"]["total_cost_yuan"] for row in rows)
    tied = [row for row in rows if row["period"]["total_cost_yuan"] <= min_cost + TIE_TOL_YUAN]
    return min(tied, key=lambda row: (selection_key(row, base_monthly)[1], selection_key(row, base_monthly)[2], row["alpha"]))


def decorate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_alpha = {alpha_key(row["alpha"]): row for row in rows}
    base = by_alpha["0.00"]["period"]
    current = by_alpha["0.50"]["period"]
    base_monthly = base["monthly"]
    output = []
    for row in sorted(rows, key=lambda x: x["alpha"]):
        period = row["period"]
        deltas = np.asarray([
            period["monthly"][month]["total_cost_yuan"] - base_monthly[month]["total_cost_yuan"]
            for month in sorted(base_monthly)
        ])
        output.append({
            **row,
            "delta_vs_alpha0_yuan": float(period["total_cost_yuan"] - base["total_cost_yuan"]),
            "delta_vs_alpha05_yuan": float(period["total_cost_yuan"] - current["total_cost_yuan"]),
            "months_lower_cost_vs_alpha0": int(np.sum(deltas < 0)),
            "months_higher_cost_vs_alpha0": int(np.sum(deltas > 0)),
            "monthly_delta_std_yuan": float(np.std(deltas)),
            "monthly_max_regret_yuan": float(np.max(deltas)),
        })
    return output


def markdown_table(rows: list[dict[str, Any]], selected: float | None = None) -> str:
    header = (
        "| α | 选定 | 总现金费用(元) | 相对α=0(元) | 相对α=0.5(元) | 正常结算费(元) | "
        "原计划费(元) | 下调退款(元) | 上调费(元) | 紧急购电费(元) | 紧急购电量(kWh) | "
        "期初SOC(kWh) | 期末SOC(kWh) | 库存校正费用(元) | 优于α=0月份 | 月度差标准差(元) | 验证 |\n"
        "|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|"
    )
    lines = [header]
    for row in rows:
        p = row["period"]
        mark = "是" if selected is not None and abs(row["alpha"] - selected) < 1e-9 else ""
        lines.append(
            f"| {row['alpha']:.2f} | {mark} | {p['total_cost_yuan']:.2f} | {row['delta_vs_alpha0_yuan']:.2f} | "
            f"{row['delta_vs_alpha05_yuan']:.2f} | {p['normal_settlement_cost_yuan']:.2f} | {p['base_plan_cost_yuan']:.2f} | "
            f"{p['downward_credit_yuan']:.2f} | {p['upward_adjustment_cost_yuan']:.2f} | {p['emergency_cost_yuan']:.2f} | "
            f"{p['emergency_purchase_kwh']:.4f} | {p['soc_open_kwh']:.4f} | {p['soc_final_kwh']:.4f} | "
            f"{p['inventory_adjusted_cost_yuan']:.2f} | {row['months_lower_cost_vs_alpha0']}/{p['days'] // 28 if False else len(p['monthly'])} | "
            f"{row['monthly_delta_std_yuan']:.2f} | {row['checks']['status']} |"
        )
    return "\n".join(lines)


def main() -> None:
    for folder in (RESULTS, VALIDATION, INTERMEDIATE):
        folder.mkdir(parents=True, exist_ok=True)
    before = formal_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    realtime = load_attachment4()
    dates = annual["dates"]
    if dates != forecasts["dates"] or dates != realtime["dates"]:
        raise ValueError("attachment date axes differ")
    val_end_idx = date_index(dates, VALIDATION_END)

    validation_runs: dict[str, dict[str, Any]] = {}
    coarse = [round_alpha(i / 10) for i in range(11)]
    for alpha in coarse:
        print(json.dumps({"event": "coarse_validation_start", "alpha": alpha}), flush=True)
        validation_runs[alpha_key(alpha)] = q3_validation_run(alpha, annual, forecasts, fixed, dates, val_end_idx)
        print(json.dumps({"event": "coarse_validation_done", "alpha": alpha, "cost": validation_runs[alpha_key(alpha)]["period"]["total_cost_yuan"]}), flush=True)

    coarse_rows = decorate(list(validation_runs.values()))
    coarse_best = select_row(coarse_rows, validation_runs["0.00"]["period"]["monthly"])["alpha"]
    fine_low = max(0.0, coarse_best - 0.1)
    fine_high = min(1.0, coarse_best + 0.1)
    fine = []
    value = fine_low
    while value <= fine_high + 1e-9:
        fine.append(round_alpha(value))
        value += 0.02
    for alpha in fine:
        if alpha_key(alpha) in validation_runs:
            continue
        print(json.dumps({"event": "fine_validation_start", "alpha": alpha}), flush=True)
        validation_runs[alpha_key(alpha)] = q3_validation_run(alpha, annual, forecasts, fixed, dates, val_end_idx)
        print(json.dumps({"event": "fine_validation_done", "alpha": alpha, "cost": validation_runs[alpha_key(alpha)]["period"]["total_cost_yuan"]}), flush=True)

    validation_rows = decorate(list(validation_runs.values()))
    selected_row = select_row(validation_rows, validation_runs["0.00"]["period"]["monthly"])
    selected_alpha = selected_row["alpha"]
    lock_payload = {
        "schema_version": 1,
        "status": "LOCKED_BEFORE_HOLDOUT",
        "selected_alpha": selected_alpha,
        "selection_source": "Q3 validation cash cost only; holdout and Q4 unavailable at lock time",
        "split": {
            "warmup": [WARMUP_START, WARMUP_END],
            "validation": [VALIDATION_START, VALIDATION_END],
            "holdout": [HOLDOUT_START, HOLDOUT_END],
        },
        "coarse_grid": coarse,
        "coarse_best_alpha": coarse_best,
        "fine_grid": fine,
        "tie_tolerance_yuan": TIE_TOL_YUAN,
        "tie_break_order": ["emergency_purchase_kwh", "monthly_delta_std_yuan", "alpha"],
        "selected_validation_metrics": selected_row,
        "formal_hashes_before": before,
    }
    if LOCK.exists():
        existing = json.loads(LOCK.read_text(encoding="utf-8"))
        if existing.get("selected_alpha") != selected_alpha or existing.get("status") != "LOCKED_BEFORE_HOLDOUT":
            raise RuntimeError("existing selection lock conflicts with new validation-only selection")
    else:
        write_json(LOCK, lock_payload)
    print(json.dumps({"event": "alpha_locked_before_holdout", "alpha": selected_alpha}), flush=True)

    compare_alphas = []
    for alpha in (0.0, 0.5, selected_alpha):
        if alpha_key(alpha) not in {alpha_key(x) for x in compare_alphas}:
            compare_alphas.append(alpha)
    q3_holdout_raw = {}
    q43_holdout_raw = {}
    for alpha in compare_alphas:
        print(json.dumps({"event": "q3_holdout_start", "alpha": alpha}), flush=True)
        q3_holdout_raw[alpha_key(alpha)] = full_run(alpha, annual, forecasts, fixed, dates, None)
        print(json.dumps({"event": "q3_holdout_done", "alpha": alpha}), flush=True)
        print(json.dumps({"event": "q4_3_holdout_start", "alpha": alpha}), flush=True)
        q43_holdout_raw[alpha_key(alpha)] = full_run(alpha, annual, forecasts, fixed, dates, realtime)
        print(json.dumps({"event": "q4_3_holdout_done", "alpha": alpha}), flush=True)
    q3_holdout = decorate(list(q3_holdout_raw.values()))
    q43_holdout = decorate(list(q43_holdout_raw.values()))

    after = formal_hashes()
    summary = {
        "schema_version": 1,
        "status": "PASS" if before == after and all(row["checks"]["status"] == "PASS" for row in validation_rows + q3_holdout + q43_holdout) else "FAIL",
        "promotion": "NOT_AUTHORIZED",
        "selected_alpha": selected_alpha,
        "selection_lock_file": str(LOCK.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "split": lock_payload["split"],
        "coarse_grid": coarse,
        "coarse_best_alpha": coarse_best,
        "fine_grid": fine,
        "validation_rows": validation_rows,
        "q3_holdout_rows": q3_holdout,
        "q4_3_holdout_rows": q43_holdout,
        "q4_3_price_model": "weekday_mean_28d; intraday scale OFF; AR(1) OFF",
        "formal_hashes_before": before,
        "formal_hashes_after": after,
        "formal_results_unchanged": before == after,
    }
    write_json(RESULTS / "alpha_calibration_summary.json", summary)
    report = [
        "# Q3 负载反馈系数 α 时间顺序标定数值表",
        "",
        "## Q3 验证期（2025-07-01—2025-09-30）",
        "",
        markdown_table(validation_rows, selected_alpha),
        "",
        "## Q3 留出期（2025-10-01—2025-12-31）",
        "",
        markdown_table(q3_holdout, selected_alpha),
        "",
        "## Q4-3 留出期（关闭日内价格缩放与 AR(1)）",
        "",
        markdown_table(q43_holdout, selected_alpha),
        "",
        "## 锁定数值",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 粗搜最优 α | {coarse_best:.2f} |",
        f"| 最终锁定 α | {selected_alpha:.2f} |",
        f"| 验证期最低现金费用（元） | {selected_row['period']['total_cost_yuan']:.2f} |",
        f"| 验证期紧急购电量（kWh） | {selected_row['period']['emergency_purchase_kwh']:.4f} |",
        f"| 验证期库存校正费用（元） | {selected_row['period']['inventory_adjusted_cost_yuan']:.2f} |",
        f"| 正式结果哈希保持不变 | {1 if before == after else 0} |",
        f"| 全部运行验证 PASS | {1 if summary['status'] == 'PASS' else 0} |",
    ]
    (RESULTS / "alpha标定数值表.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"event": "complete", "status": summary["status"], "selected_alpha": selected_alpha, "formal_unchanged": before == after}, ensure_ascii=False), flush=True)
    if summary["status"] != "PASS":
        raise RuntimeError("alpha calibration validation failed")


if __name__ == "__main__":
    main()
