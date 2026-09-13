from __future__ import annotations

import csv
import json
import platform
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, natural_slot_label, sha256
from dispatch_core import (
    ETA_CHARGE,
    ETA_DISCHARGE,
    FLOW_MAX_KWH,
    POSITIVE_TOL_KWH,
    SOC_INITIAL,
    SOC_MAX,
    SOC_MIN,
    SOLVER_TOL_KWH,
    execute_fixed_plan,
    maximal_positive_events,
    solve_deterministic_plan,
)


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"
N = 144
EVAL_START = 31  # 2025-02-01; January is historical warm-up with idle storage.
LOOKBACK_DAYS = 28
RESIDUAL_WINDOW_DAYS = 56
RISK_QUANTILE = 0.8
EMERGENCY_MULTIPLIER = 5.0


def json_default(value: Any):
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def weekday_mean_forecast(
    values_kw: np.ndarray,
    dates: list[date],
    cutoff_idx: int,
    target_date: date,
    lookback_days: int = LOOKBACK_DAYS,
) -> np.ndarray:
    known_start = max(0, cutoff_idx - lookback_days)
    candidates = [
        idx
        for idx in range(known_start, cutoff_idx)
        if dates[idx].weekday() == target_date.weekday()
    ]
    if not candidates:
        if cutoff_idx <= 0:
            raise ValueError("没有任何历史数据可生成预测")
        candidates = [cutoff_idx - 1]
    return np.mean(values_kw[candidates], axis=0)


def make_historical_weekday_cache(values_kw: np.ndarray, dates: list[date]) -> np.ndarray:
    cache = np.full_like(values_kw, np.nan, dtype=float)
    for idx in range(1, len(dates)):
        cache[idx] = weekday_mean_forecast(values_kw, dates, idx, dates[idx])
    return cache


def weekday_weighted_forecast(
    values_kw: np.ndarray,
    dates: list[date],
    cutoff_idx: int,
    target_date: date,
    weight_kind: str,
) -> np.ndarray:
    candidates = [
        idx for idx in range(max(0, cutoff_idx - LOOKBACK_DAYS), cutoff_idx)
        if dates[idx].weekday() == target_date.weekday()
    ]
    if not candidates:
        if cutoff_idx <= 0:
            raise ValueError("没有任何历史数据可生成同星期预测")
        candidates = [cutoff_idx - 1]
    if weight_kind == "equal":
        weights = np.ones(len(candidates), dtype=float)
    elif weight_kind == "linear":
        weights = np.arange(1, len(candidates) + 1, dtype=float)
    elif weight_kind == "exp2w":
        ages_weeks = (cutoff_idx - 1 - np.asarray(candidates, dtype=float)) / 7.0
        weights = np.power(0.5, ages_weeks / 2.0)
    else:
        raise ValueError(f"未知同星期权重: {weight_kind}")
    return np.average(values_kw[candidates], axis=0, weights=weights)


def candidate_kind(weight_kind: str, pv_window_days: int) -> str:
    if weight_kind not in {"equal", "linear", "exp2w"} or pv_window_days not in {3, 5}:
        raise ValueError("候选只允许equal/linear/exp2w与PV3/5日")
    return f"candidate_{weight_kind}_pv{pv_window_days}"


def make_point_forecast_cache(
    kind: str, load_kw: np.ndarray, pv_kw: np.ndarray, dates: list[date]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    load_cache = np.full_like(load_kw, np.nan, dtype=float)
    pv_cache = np.full_like(pv_kw, np.nan, dtype=float)
    for idx in range(1, len(dates)):
        forecast_load, forecast_pv = forecast_two_days(kind, load_kw, pv_kw, dates, idx)
        load_cache[idx] = forecast_load[0]
        pv_cache[idx] = forecast_pv[0]
    return load_cache, pv_cache, load_cache - pv_cache


def residual_quantile_kw(
    actual_net_kw: np.ndarray,
    weekday_net_cache_kw: np.ndarray,
    decision_idx: int,
    quantile: float,
) -> tuple[np.ndarray, int, int]:
    start = max(1, decision_idx - RESIDUAL_WINDOW_DAYS)
    historical_indices = np.arange(start, decision_idx, dtype=int)
    valid = historical_indices[np.isfinite(weekday_net_cache_kw[historical_indices]).all(axis=1)]
    if len(valid) == 0:
        raise ValueError(f"{decision_idx=} 前无可用历史残差")
    residuals = actual_net_kw[valid] - weekday_net_cache_kw[valid]
    return np.quantile(residuals, quantile, axis=0), int(valid[0]), int(valid[-1])


def forecast_two_days(
    kind: str,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    dates: list[date],
    decision_idx: int,
) -> tuple[np.ndarray, np.ndarray]:
    if kind == "persistence":
        if decision_idx <= 0:
            raise ValueError("持久性预测至少需要一天历史")
        return (
            np.vstack([load_kw[decision_idx - 1], load_kw[decision_idx - 1]]),
            np.vstack([pv_kw[decision_idx - 1], pv_kw[decision_idx - 1]]),
        )
    if kind == "weekday_mean_28d":
        target_dates = [dates[decision_idx], dates[decision_idx] + timedelta(days=1)]
        return (
            np.vstack([weekday_mean_forecast(load_kw, dates, decision_idx, target) for target in target_dates]),
            np.vstack([weekday_mean_forecast(pv_kw, dates, decision_idx, target) for target in target_dates]),
        )
    if kind == "weighted_weekday_load_pv3":
        kind = "candidate_linear_pv3"
    if kind.startswith("candidate_"):
        parts = kind.split("_")
        if len(parts) != 3 or not parts[2].startswith("pv"):
            raise ValueError(f"候选预测名称格式错误: {kind}")
        weight_kind = parts[1]
        pv_window = int(parts[2][2:])
        candidate_kind(weight_kind, pv_window)
        target_dates = [dates[decision_idx], dates[decision_idx] + timedelta(days=1)]
        load_forecast = np.vstack([
            weekday_weighted_forecast(load_kw, dates, decision_idx, target, weight_kind)
            for target in target_dates
        ])
        pv_start = max(0, decision_idx - pv_window)
        pv_candidates = np.arange(pv_start, decision_idx, dtype=int)
        if len(pv_candidates) == 0:
            raise ValueError("滚动光伏均值至少需要一个已完成日")
        pv_average = np.mean(pv_kw[pv_candidates], axis=0)
        return load_forecast, np.vstack([pv_average, pv_average])
    raise ValueError(f"未知预测类型: {kind}")


def forecast_metrics(actual: np.ndarray, forecast: np.ndarray) -> dict[str, float]:
    error = forecast - actual
    denominator = float(np.sum(np.abs(actual)))
    return {
        "mae_kw": float(np.mean(np.abs(error))),
        "rmse_kw": float(np.sqrt(np.mean(error**2))),
        "wape": float(np.sum(np.abs(error)) / denominator) if denominator > 0 else 0.0,
        "bias_kw": float(np.mean(error)),
    }


def run_strategy(
    *,
    name: str,
    forecast_kind: str,
    quantile: float | None,
    terminal_mode: str,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    dates: list[date],
    price: np.ndarray,
    actual_net_kw: np.ndarray,
    weekday_net_cache_kw: np.ndarray,
    raw_endpoint_labels: list[str],
    keep_detail: bool,
    actual_price_by_date: np.ndarray | None = None,
    planning_price_kind: str | None = None,
) -> dict[str, Any]:
    soc = SOC_INITIAL
    daily_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    storage_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    plan_rows: list[dict[str, Any]] = []
    max_plan_balance = 0.0
    max_plan_state = 0.0
    plan_simultaneous = 0
    secondary_days = 0
    max_actual_balance = 0.0
    max_actual_state = 0.0
    min_soc = soc
    max_soc = soc
    max_crossday_gap = 0.0
    previous_close: float | None = None

    for day_idx in range(EVAL_START, len(dates)):
        day = dates[day_idx]
        train_end = dates[day_idx - 1]
        if actual_price_by_date is None:
            plan_price_2d = np.tile(price, 2)
            settlement_price = price
        else:
            if planning_price_kind == "weekday_mean_28d":
                plan_price_2d = np.concatenate([
                    weekday_mean_forecast(actual_price_by_date, dates, day_idx, day),
                    weekday_mean_forecast(actual_price_by_date, dates, day_idx, day + timedelta(days=1)),
                ])
            elif planning_price_kind == "persistence":
                plan_price_2d = np.tile(actual_price_by_date[day_idx - 1], 2)
            else:
                raise ValueError("实时价格模式必须明确 planning_price_kind")
            settlement_price = actual_price_by_date[day_idx]
        forecast_load_2d, forecast_pv_2d = forecast_two_days(
            forecast_kind, load_kw, pv_kw, dates, day_idx
        )
        point_net_2d_kw = forecast_load_2d - forecast_pv_2d
        risk_uplift_kw = np.zeros(N, dtype=float)
        residual_first_idx = day_idx - 1
        residual_last_idx = day_idx - 1
        if quantile is not None:
            risk_uplift_kw, residual_first_idx, residual_last_idx = residual_quantile_kw(
                actual_net_kw, weekday_net_cache_kw, day_idx, quantile
            )
        effective_net_2d_kwh = (point_net_2d_kw + np.vstack([risk_uplift_kw, risk_uplift_kw])) / 6.0
        terminal_soc = SOC_INITIAL if terminal_mode == "fixed_6000_at_48h" else soc
        plan = solve_deterministic_plan(
            effective_net_2d_kwh.reshape(-1),
            plan_price_2d,
            soc,
            terminal_soc,
        )
        q = plan.q[:N].copy()
        max_plan_balance = max(max_plan_balance, plan.balance_max_abs_kwh)
        max_plan_state = max(max_plan_state, plan.state_max_abs_kwh)
        plan_simultaneous += plan.simultaneous_positive_slots
        secondary_days += int(plan.secondary_used)

        load_kwh = load_kw[day_idx] / 6.0
        pv_kwh = pv_kw[day_idx] / 6.0
        execution = execute_fixed_plan(load_kwh, pv_kwh, q, soc)
        if previous_close is not None:
            max_crossday_gap = max(max_crossday_gap, abs(soc - previous_close))

        balance = (
            q
            + pv_kwh
            + execution.discharge
            + execution.emergency
            - load_kwh
            - execution.charge
            - execution.surplus
        )
        state_residual = (
            execution.soc[1:]
            - execution.soc[:-1]
            - ETA_CHARGE * execution.charge
            + execution.discharge / ETA_DISCHARGE
        )
        max_actual_balance = max(max_actual_balance, float(np.max(np.abs(balance))))
        max_actual_state = max(max_actual_state, float(np.max(np.abs(state_residual))))
        min_soc = min(min_soc, float(np.min(execution.soc)))
        max_soc = max(max_soc, float(np.max(execution.soc)))

        normal_cost = float(np.dot(settlement_price, q))
        emergency_cost = float(np.dot(EMERGENCY_MULTIPLIER * settlement_price, execution.emergency))
        daily = {
            "date": day.isoformat(),
            "train_end_date": train_end.isoformat(),
            "residual_history_start_date": dates[residual_first_idx].isoformat(),
            "residual_history_end_date": dates[residual_last_idx].isoformat(),
            "soc_open_kwh": float(execution.soc[0]),
            "soc_close_kwh": float(execution.soc[-1]),
            "normal_purchase_kwh": float(np.sum(q)),
            "emergency_purchase_kwh": float(np.sum(execution.emergency)),
            "normal_cost_yuan": normal_cost,
            "emergency_cost_yuan": emergency_cost,
            "total_cost_yuan": normal_cost + emergency_cost,
            "charge_kwh": float(np.sum(execution.charge)),
            "discharge_kwh": float(np.sum(execution.discharge)),
            "surplus_discard_kwh": float(np.sum(execution.surplus)),
        }
        daily_rows.append(daily)

        if keep_detail:
            plan_rows.append({
                "date": day.isoformat(),
                "purchase_kwh": [float(value) for value in q],
                "total_purchase_kwh": daily["normal_purchase_kwh"],
                "total_cost_yuan": daily["total_cost_yuan"],
            })
            for slot in range(N):
                start, end, label = natural_slot_label(slot)
                detail_rows.append({
                    "date": day.isoformat(),
                    "slot": slot + 1,
                    "source_endpoint_label": raw_endpoint_labels[slot],
                    "interval_start": start,
                    "interval_end": end,
                    "interval_label": label,
                    "plan_created_at": day.isoformat() + "T00:00:00",
                    "train_end_date": train_end.isoformat(),
                    "forecast_load_kw": float(forecast_load_2d[0, slot]),
                    "forecast_pv_kw": float(forecast_pv_2d[0, slot]),
                    "forecast_point_net_kw": float(point_net_2d_kw[0, slot]),
                    "risk_uplift_kw": float(risk_uplift_kw[slot]),
                    "forecast_price_yuan_per_kwh": float(plan_price_2d[slot]),
                    "actual_price_yuan_per_kwh": float(settlement_price[slot]),
                    "effective_forecast_net_kwh": float(effective_net_2d_kwh[0, slot]),
                    "actual_load_kw": float(load_kw[day_idx, slot]),
                    "actual_pv_kw": float(pv_kw[day_idx, slot]),
                    "load_kwh": float(load_kwh[slot]),
                    "pv_kwh": float(pv_kwh[slot]),
                    "normal_purchase_kwh": float(q[slot]),
                    "charge_bus_kwh": float(execution.charge[slot]),
                    "discharge_bus_kwh": float(execution.discharge[slot]),
                    "emergency_purchase_kwh": float(execution.emergency[slot]),
                    "surplus_discard_kwh": float(execution.surplus[slot]),
                    "soc_open_kwh": float(execution.soc[slot]),
                    "soc_close_kwh": float(execution.soc[slot + 1]),
                    "normal_cost_yuan": float(settlement_price[slot] * q[slot]),
                    "emergency_cost_yuan": float(EMERGENCY_MULTIPLIER * settlement_price[slot] * execution.emergency[slot]),
                    "balance_residual_kwh": float(balance[slot]),
                    "state_residual_kwh": float(state_residual[slot]),
                })
            for block in range(6):
                left = block * 24
                right = (block + 1) * 24
                storage_rows.append({
                    "date": day.isoformat(),
                    "block": block + 1,
                    "interval": f"{block * 4}:00-{(block + 1) * 4}:00",
                    "charge_kwh": float(np.sum(execution.charge[left:right])),
                    "discharge_kwh": float(np.sum(execution.discharge[left:right])),
                    "soc_open_day_kwh": float(execution.soc[0]),
                    "soc_close_day_kwh": float(execution.soc[-1]),
                })
            for event_id, (start_slot, end_slot, amount) in enumerate(maximal_positive_events(execution.emergency), start=1):
                event_rows.append({
                    "date": day.isoformat(),
                    "event_id": event_id,
                    "start_slot": start_slot + 1,
                    "end_slot_exclusive": end_slot + 1,
                    "interval": f"{natural_slot_label(start_slot)[0]}-{natural_slot_label(end_slot - 1)[1]}",
                    "purchase_kwh": amount,
                })

        previous_close = float(execution.soc[-1])
        soc = previous_close

    aggregate = {
        "strategy": name,
        "forecast_kind": forecast_kind,
        "risk_quantile": quantile,
        "residual_window_days": RESIDUAL_WINDOW_DAYS if quantile is not None else None,
        "terminal_mode": terminal_mode,
        "days": len(daily_rows),
        "normal_purchase_kwh": float(sum(row["normal_purchase_kwh"] for row in daily_rows)),
        "emergency_purchase_kwh": float(sum(row["emergency_purchase_kwh"] for row in daily_rows)),
        "normal_cost_yuan": float(sum(row["normal_cost_yuan"] for row in daily_rows)),
        "emergency_cost_yuan": float(sum(row["emergency_cost_yuan"] for row in daily_rows)),
        "total_cost_yuan": float(sum(row["total_cost_yuan"] for row in daily_rows)),
        "charge_kwh": float(sum(row["charge_kwh"] for row in daily_rows)),
        "discharge_kwh": float(sum(row["discharge_kwh"] for row in daily_rows)),
        "surplus_discard_kwh": float(sum(row["surplus_discard_kwh"] for row in daily_rows)),
        "soc_initial_kwh": SOC_INITIAL,
        "soc_final_kwh": soc,
        "soc_min_kwh": min_soc,
        "soc_max_kwh": max_soc,
        "max_plan_balance_residual_kwh": max_plan_balance,
        "max_plan_state_residual_kwh": max_plan_state,
        "plan_simultaneous_positive_slots": plan_simultaneous,
        "plan_secondary_days": secondary_days,
        "max_actual_balance_residual_kwh": max_actual_balance,
        "max_actual_state_residual_kwh": max_actual_state,
        "max_crossday_soc_gap_kwh": max_crossday_gap,
    }
    return {
        "aggregate": aggregate,
        "daily": daily_rows,
        "detail": detail_rows,
        "storage": storage_rows,
        "events": event_rows,
        "plans": plan_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入无表头空CSV: {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    fixed = load_attachment1()
    annual = load_attachment2()
    dates = annual["dates"]
    load_kw = annual["load_kw"]
    pv_kw = annual["pv_kw"]
    actual_net_kw = load_kw - pv_kw
    price = fixed["price_yuan_per_kwh"]

    config_path = INTERMEDIATE / "q2_main_config.json"
    if config_path.exists():
        main_config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        main_config = {"status": "KEEP_OLD_MAIN", "selected_forecast_kind": "weekday_mean_28d"}
    selected_kind = str(main_config["selected_forecast_kind"])

    weekday_load_cache = make_historical_weekday_cache(load_kw, dates)
    weekday_pv_cache = make_historical_weekday_cache(pv_kw, dates)
    weekday_net_cache = weekday_load_cache - weekday_pv_cache
    selected_load_cache, selected_pv_cache, selected_net_cache = make_point_forecast_cache(
        selected_kind, load_kw, pv_kw, dates
    )
    eval_slice = slice(EVAL_START, len(dates))
    persistence_load = load_kw[EVAL_START - 1 : len(dates) - 1]
    persistence_pv = pv_kw[EVAL_START - 1 : len(dates) - 1]
    seasonal_load = weekday_load_cache[eval_slice]
    seasonal_pv = weekday_pv_cache[eval_slice]
    forecast_diagnostics = {
        "persistence_1d": {
            "load": forecast_metrics(load_kw[eval_slice], persistence_load),
            "pv": forecast_metrics(pv_kw[eval_slice], persistence_pv),
            "net": forecast_metrics(actual_net_kw[eval_slice], persistence_load - persistence_pv),
        },
        "weekday_mean_28d": {
            "load": forecast_metrics(load_kw[eval_slice], seasonal_load),
            "pv": forecast_metrics(pv_kw[eval_slice], seasonal_pv),
            "net": forecast_metrics(actual_net_kw[eval_slice], weekday_net_cache[eval_slice]),
        },
        "selected_main_point_forecast": {
            "forecast_kind": selected_kind,
            "load": forecast_metrics(load_kw[eval_slice], selected_load_cache[eval_slice]),
            "pv": forecast_metrics(pv_kw[eval_slice], selected_pv_cache[eval_slice]),
            "net": forecast_metrics(actual_net_kw[eval_slice], selected_net_cache[eval_slice]),
        },
    }
    q80_effective: list[np.ndarray] = []
    for idx in range(EVAL_START, len(dates)):
        uplift, _, _ = residual_quantile_kw(actual_net_kw, selected_net_cache, idx, RISK_QUANTILE)
        q80_effective.append(selected_net_cache[idx] + uplift)
    q80_effective_array = np.asarray(q80_effective)
    forecast_diagnostics["selected_main_plus_q80_residual"] = {
        "forecast_kind": selected_kind,
        "net": forecast_metrics(actual_net_kw[eval_slice], q80_effective_array),
        "empirical_one_sided_coverage": float(np.mean(actual_net_kw[eval_slice] <= q80_effective_array)),
        "target_quantile": RISK_QUANTILE,
    }

    specs = [
        ("baseline_persistence", "persistence", weekday_net_cache, None, "fixed_6000_at_48h", False),
        ("old_seasonal_q80", "weekday_mean_28d", weekday_net_cache, 0.8, "fixed_6000_at_48h", False),
        ("selected_point", selected_kind, selected_net_cache, None, "fixed_6000_at_48h", False),
        ("seasonal_q80_main", selected_kind, selected_net_cache, 0.8, "fixed_6000_at_48h", True),
        ("seasonal_q90_risk", selected_kind, selected_net_cache, 0.9, "fixed_6000_at_48h", False),
        ("seasonal_q80_terminal_hold", selected_kind, selected_net_cache, 0.8, "initial_soc_at_48h", False),
    ]
    runs: dict[str, dict[str, Any]] = {}
    for name, kind, point_cache, quantile, terminal_mode, keep_detail in specs:
        print(json.dumps({"event": "q2_strategy_start", "strategy": name}, ensure_ascii=False), flush=True)
        runs[name] = run_strategy(
            name=name,
            forecast_kind=kind,
            quantile=quantile,
            terminal_mode=terminal_mode,
            load_kw=load_kw,
            pv_kw=pv_kw,
            dates=dates,
            price=price,
            actual_net_kw=actual_net_kw,
            weekday_net_cache_kw=point_cache,
            raw_endpoint_labels=annual["raw_endpoint_labels"],
            keep_detail=keep_detail,
        )
        print(json.dumps({"event": "q2_strategy_complete", **runs[name]["aggregate"]}, ensure_ascii=False), flush=True)

    main_run = runs["seasonal_q80_main"]
    detail_path = RESULTS / "q2_detail.csv"
    daily_path = RESULTS / "q2_daily.csv"
    storage_path = RESULTS / "q2_storage_4h.csv"
    events_path = RESULTS / "q2_emergency_events.csv"
    write_csv(detail_path, main_run["detail"])
    write_csv(daily_path, main_run["daily"])
    write_csv(storage_path, main_run["storage"])
    if main_run["events"]:
        write_csv(events_path, main_run["events"])
    else:
        events_path.write_text("date,event_id,start_slot,end_slot_exclusive,interval,purchase_kwh\n", encoding="utf-8-sig")

    selected_dates = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    selected_events = {
        target: [row for row in main_run["events"] if row["date"] == target]
        for target in selected_dates
    }
    aggregates = {name: run["aggregate"] for name, run in runs.items()}
    baseline_cost = aggregates["baseline_persistence"]["total_cost_yuan"]
    main_cost = aggregates["seasonal_q80_main"]["total_cost_yuan"]
    summary = {
        "schema_version": 1,
        "status": "SOLVED_AND_VALIDATED",
        "question": "Q2",
        "evaluation_period": {"start": dates[EVAL_START].isoformat(), "end": dates[-1].isoformat(), "days": len(dates) - EVAL_START},
        "frozen_basis": {
            "time": "natural_day_144_slots_right_endpoint_rectangle",
            "information": "00:00 plan uses only prior-day-and-earlier history; current-slot storage feedback uses no future slot",
            "storage": "cross-day continuous; January idle gives 2025-02-01 opening SOC 6000 kWh",
            "emergency": "shortfall-only and charged at five times the delivery-slot fixed daily price",
            "known_conflict": "A01 remains; result workbook will use corrected natural-day labels with visible disclosure",
        },
        "model_settings": {
            "baseline_forecast": "previous-day same-slot persistence",
            "old_point_forecast": "mean of available same-weekday load and PV profiles in prior 28 days",
            "upgraded_point_forecast": selected_kind,
            "upgrade_gate": main_config["status"],
            "residual_uplift": "slotwise causal trailing-56-day empirical 0.8 quantile",
            "risk_quantile_basis": "minimizes p*q + 5*p*shortage pointwise; critical fractile is 0.8",
            "planning_horizon": "48 hours",
            "terminal_main": "SOC=6000 kWh at the end of the moving 48-hour planning horizon; only first day is executed",
            "execution": "fixed normal purchase plus causal greedy charge/discharge, then emergency for remaining shortage",
        },
        "forecast_diagnostics": forecast_diagnostics,
        "strategies": aggregates,
        "main_improvement_vs_persistence": {
            "cost_saving_yuan": baseline_cost - main_cost,
            "cost_saving_fraction": 1.0 - main_cost / baseline_cost,
            "emergency_reduction_kwh": aggregates["baseline_persistence"]["emergency_purchase_kwh"] - aggregates["seasonal_q80_main"]["emergency_purchase_kwh"],
        },
        "main_improvement_vs_old_q80": {
            "cost_saving_yuan": aggregates["old_seasonal_q80"]["total_cost_yuan"] - main_cost,
            "cost_saving_fraction": 1.0 - main_cost / aggregates["old_seasonal_q80"]["total_cost_yuan"],
            "emergency_reduction_kwh": aggregates["old_seasonal_q80"]["emergency_purchase_kwh"] - aggregates["seasonal_q80_main"]["emergency_purchase_kwh"],
        },
        "selected_date_emergency_events": selected_events,
        "files": {
            "detail_csv": str(detail_path.relative_to(PROJECT_ROOT)),
            "daily_csv": str(daily_path.relative_to(PROJECT_ROOT)),
            "storage_4h_csv": str(storage_path.relative_to(PROJECT_ROOT)),
            "emergency_events_csv": str(events_path.relative_to(PROJECT_ROOT)),
        },
    }
    summary_path = RESULTS / "q2_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

    main_agg = main_run["aggregate"]
    cost_from_daily = float(sum(row["total_cost_yuan"] for row in main_run["daily"]))
    emergency_charge_overlap = sum(
        1
        for row in main_run["detail"]
        if row["emergency_purchase_kwh"] > POSITIVE_TOL_KWH and row["charge_bus_kwh"] > POSITIVE_TOL_KWH
    )
    simultaneous_actual = sum(
        1
        for row in main_run["detail"]
        if row["charge_bus_kwh"] > POSITIVE_TOL_KWH and row["discharge_bus_kwh"] > POSITIVE_TOL_KWH
    )
    information_violations = sum(
        1 for row in main_run["daily"] if row["train_end_date"] >= row["date"] or row["residual_history_end_date"] >= row["date"]
    )
    pass_flags = {
        "evaluation_days": len(main_run["daily"]) == 334,
        "detail_rows": len(main_run["detail"]) == 334 * 144,
        "storage_rows": len(main_run["storage"]) == 334 * 6,
        "actual_balance": main_agg["max_actual_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "actual_state": main_agg["max_actual_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "soc_bounds": main_agg["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH and main_agg["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH,
        "crossday_soc": main_agg["max_crossday_soc_gap_kwh"] <= SOLVER_TOL_KWH,
        "mutual_exclusion_actual": simultaneous_actual == 0,
        "emergency_not_used_to_charge": emergency_charge_overlap == 0,
        "information_cutoff": information_violations == 0,
        "plan_lp_balance": main_agg["max_plan_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_lp_state": main_agg["max_plan_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_lp_mutual_exclusion": main_agg["plan_simultaneous_positive_slots"] == 0,
        "cost_reconciliation": abs(cost_from_daily - main_agg["total_cost_yuan"]) <= 1e-6,
    }
    validation = {
        "schema_version": 1,
        "question": "Q2",
        "status": "PASS" if all(pass_flags.values()) else "FAIL",
        "tolerances": {"solver_kwh": SOLVER_TOL_KWH, "positive_kwh": POSITIVE_TOL_KWH},
        "pass_flags": pass_flags,
        "metrics": {
            "information_violations": information_violations,
            "simultaneous_actual_slots": simultaneous_actual,
            "emergency_charge_overlap_slots": emergency_charge_overlap,
            "cost_from_daily_yuan": cost_from_daily,
            **main_agg,
        },
        "all_strategy_aggregates": aggregates,
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "solver": "scipy.optimize.linprog(method='highs')",
        },
    }
    validation_path = VALIDATION / "q2_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

    workbook_payload = {
        "schema_version": 1,
        "question": "Q2",
        "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template",
        "plans": main_run["plans"],
        "storage_four_hour": main_run["storage"],
        "emergency_events": main_run["events"],
    }
    workbook_payload_path = INTERMEDIATE / "q2_workbook_payload.json"
    workbook_payload_path.write_text(json.dumps(workbook_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    run_manifest = {
        "question": "Q2",
        "status": validation["status"],
        "input_sha256": {"attachment1": fixed["sha256"], "attachment2": annual["sha256"]},
        "code_sha256": {
            name: sha256(Path(__file__).with_name(name))
            for name in ("common_data.py", "dispatch_core.py", "q2_solve.py")
        },
        "outputs_sha256": {
            str(path.relative_to(PROJECT_ROOT)): sha256(path)
            for path in (
                detail_path,
                daily_path,
                storage_path,
                events_path,
                summary_path,
                validation_path,
                workbook_payload_path,
            )
        },
    }
    manifest_path = INTERMEDIATE / "q2_run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": validation["status"],
        "main_total_cost_yuan": main_cost,
        "baseline_total_cost_yuan": baseline_cost,
        "saving_fraction": 1.0 - main_cost / baseline_cost,
        "main_emergency_kwh": main_agg["emergency_purchase_kwh"],
        "main_final_soc_kwh": main_agg["soc_final_kwh"],
    }, ensure_ascii=False))
    if validation["status"] != "PASS":
        raise RuntimeError("Q2主结果未通过约束核验")


if __name__ == "__main__":
    main()
