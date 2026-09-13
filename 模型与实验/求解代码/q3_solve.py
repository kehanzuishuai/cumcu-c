from __future__ import annotations

import csv
import json
import platform
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, load_attachment3, natural_slot_label, sha256
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
    solve_adjusted_plan,
    solve_deterministic_plan,
)
import q2_solve as q2


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"
N = 144
EVAL_START = 31
LOOKBACK_DAYS = 28
RESIDUAL_WINDOW_DAYS = 56
RISK_QUANTILE = 0.8
EMERGENCY_MULTIPLIER = 5.0
ISSUE_HOURS = [0, 6, 12, 18]


def weekday_mean(values_kw: np.ndarray, dates: list[date], cutoff_idx: int, target_date: date) -> np.ndarray:
    candidates = [
        idx for idx in range(max(0, cutoff_idx - LOOKBACK_DAYS), cutoff_idx)
        if dates[idx].weekday() == target_date.weekday()
    ]
    if not candidates:
        if cutoff_idx <= 0:
            raise ValueError("没有历史数据可生成负载日型预测")
        candidates = [cutoff_idx - 1]
    return np.mean(values_kw[candidates], axis=0)


def causal_price_forecast_horizon(
    actual_price_by_date: np.ndarray,
    dates: list[date],
    day_idx: int,
    issue_hour: int,
    kind: str,
) -> tuple[np.ndarray, float]:
    """Forecast the 24 hours after an issue using history and the observed same-day prefix only."""
    start = issue_hour * 6
    if kind in {"weekday_mean_28d", "weekday_mean_28d_intraday_scale", "weekday_mean_28d_intraday_scale_ar1"}:
        today = weekday_mean(actual_price_by_date, dates, day_idx, dates[day_idx])
        tomorrow = weekday_mean(actual_price_by_date, dates, day_idx, dates[day_idx] + timedelta(days=1))
    elif kind == "persistence":
        today = actual_price_by_date[day_idx - 1]
        tomorrow = actual_price_by_date[day_idx - 1]
    else:
        raise ValueError("实时价格模式必须明确 planning_price_kind")
    scale = 1.0
    if kind in {"weekday_mean_28d_intraday_scale", "weekday_mean_28d_intraday_scale_ar1"} and start > 0:
        denominator = float(np.sum(today[:start]))
        if denominator <= 0.0:
            raise ValueError("历史价格日型前缀和非正，无法进行因果比例修正")
        scale = float(np.sum(actual_price_by_date[day_idx, :start]) / denominator)
    horizon = np.concatenate([today[start:], tomorrow[:start]]) * scale
    if kind == "weekday_mean_28d_intraday_scale_ar1" and start > 0:
        residual_rows = []
        for history_idx in range(max(7, day_idx - 28), day_idx):
            history_base = weekday_mean(actual_price_by_date, dates, history_idx, dates[history_idx])
            residual_rows.append(actual_price_by_date[history_idx] - history_base)
        residual = np.asarray(residual_rows)
        lag = residual[:, :-1].reshape(-1)
        lead = residual[:, 1:].reshape(-1)
        denominator = float(np.dot(lag, lag))
        rho = 0.0 if denominator <= 0.0 else float(np.clip(np.dot(lag, lead) / denominator, -0.99, 0.99))
        last_residual = float(actual_price_by_date[day_idx, start - 1] - today[start - 1] * scale)
        horizon = horizon + last_residual * rho ** np.arange(1, len(horizon) + 1, dtype=float)
    return np.maximum(horizon, 0.0), scale


def target_profile(values_kw: np.ndarray, dates: list[date], cutoff_idx: int, issue_hour: int) -> np.ndarray:
    start = issue_hour * 6
    today = q2.weekday_weighted_forecast(values_kw, dates, cutoff_idx, dates[cutoff_idx], "linear")
    tomorrow = q2.weekday_weighted_forecast(values_kw, dates, cutoff_idx, dates[cutoff_idx] + timedelta(days=1), "linear")
    return np.concatenate([today[start:], tomorrow[:start]])


def actual_target(values_kw: np.ndarray, day_idx: int, issue_hour: int) -> np.ndarray:
    start = issue_hour * 6
    return np.concatenate([values_kw[day_idx, start:], values_kw[day_idx + 1, :start]])


def pv_forecast_10min(
    forecast_leads_kw: np.ndarray,
    boundary_kw: float,
    interpolation: str,
) -> np.ndarray:
    leads = np.asarray(forecast_leads_kw, dtype=float)
    if leads.shape != (24,):
        raise ValueError("光伏预报必须包含提前1至24小时")
    x = np.arange(1, 145, dtype=float) / 6.0
    if interpolation == "linear":
        return np.interp(x, np.arange(25, dtype=float), np.concatenate([[boundary_kw], leads]))
    if interpolation == "step_hold":
        result = np.empty(144, dtype=float)
        for idx, hour in enumerate(x):
            if hour < 1.0:
                result[idx] = boundary_kw
            else:
                lead_idx = min(int(np.floor(hour)) - 1, 23)
                result[idx] = leads[lead_idx]
        return result
    raise ValueError(f"未知插值方式: {interpolation}")


def issue_boundary_pv(pv_kw: np.ndarray, day_idx: int, issue_hour: int) -> float:
    if issue_hour == 0:
        return float(pv_kw[day_idx - 1, -1])
    return float(pv_kw[day_idx, issue_hour * 6 - 1])


def issue_forecast(
    *,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    forecast3_kw: np.ndarray,
    dates: list[date],
    day_idx: int,
    issue_idx: int,
    interpolation: str,
) -> tuple[np.ndarray, np.ndarray]:
    issue_hour = ISSUE_HOURS[issue_idx]
    load = target_profile(load_kw, dates, day_idx, issue_hour)
    pv = pv_forecast_10min(
        forecast3_kw[day_idx, issue_idx],
        issue_boundary_pv(pv_kw, day_idx, issue_hour),
        interpolation,
    )
    return load, pv


def build_forecast_caches(
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    forecast3_kw: np.ndarray,
    dates: list[date],
    interpolation: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    residual = np.full((len(dates), 4, N), np.nan, dtype=float)
    point_pv = np.full_like(residual, np.nan)
    point_net = np.full_like(residual, np.nan)
    for day_idx in range(1, len(dates) - 1):
        for issue_idx, issue_hour in enumerate(ISSUE_HOURS):
            forecast_load, forecast_pv = issue_forecast(
                load_kw=load_kw,
                pv_kw=pv_kw,
                forecast3_kw=forecast3_kw,
                dates=dates,
                day_idx=day_idx,
                issue_idx=issue_idx,
                interpolation=interpolation,
            )
            actual_net = actual_target(load_kw, day_idx, issue_hour) - actual_target(pv_kw, day_idx, issue_hour)
            point_pv[day_idx, issue_idx] = forecast_pv
            point_net[day_idx, issue_idx] = forecast_load - forecast_pv
            residual[day_idx, issue_idx] = actual_net - point_net[day_idx, issue_idx]
    return residual, point_pv, point_net


def risk_uplift(residual_cache: np.ndarray, day_idx: int, issue_idx: int) -> tuple[np.ndarray, int, int]:
    first = max(1, day_idx - RESIDUAL_WINDOW_DAYS)
    candidates = np.arange(first, day_idx, dtype=int)
    valid = candidates[np.isfinite(residual_cache[candidates, issue_idx]).all(axis=1)]
    if len(valid) == 0:
        raise ValueError("发布时间对应的历史残差为空")
    return np.quantile(residual_cache[valid, issue_idx], RISK_QUANTILE, axis=0), int(valid[0]), int(valid[-1])


def metric(actual: np.ndarray, forecast: np.ndarray) -> dict[str, float]:
    error = forecast - actual
    return {
        "mae_kw": float(np.mean(np.abs(error))),
        "rmse_kw": float(np.sqrt(np.mean(error**2))),
        "wape": float(np.sum(np.abs(error)) / np.sum(np.abs(actual))),
        "bias_kw": float(np.mean(error)),
    }


def run_strategy(
    *,
    name: str,
    update_hours: list[int],
    interpolation: str,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    forecast3_kw: np.ndarray,
    dates: list[date],
    price: np.ndarray,
    residual_cache: np.ndarray,
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
    version_rows: list[dict[str, Any]] = []
    workbook_plans: list[dict[str, Any]] = []
    max_plan_balance = max_plan_state = max_link = 0.0
    max_actual_balance = max_actual_state = max_crossday_gap = 0.0
    min_soc = max_soc = soc
    plan_simultaneous = secondary_plans = 0
    previous_close: float | None = None

    for day_idx in range(EVAL_START, len(dates)):
        day = dates[day_idx]
        if actual_price_by_date is None:
            plan_price_today = price
            plan_price_tomorrow = price
            settlement_price = price
        else:
            if planning_price_kind in {"weekday_mean_28d", "weekday_mean_28d_intraday_scale", "weekday_mean_28d_intraday_scale_ar1"}:
                plan_price_today = weekday_mean(actual_price_by_date, dates, day_idx, day)
                plan_price_tomorrow = weekday_mean(actual_price_by_date, dates, day_idx, day + timedelta(days=1))
            elif planning_price_kind == "persistence":
                plan_price_today = actual_price_by_date[day_idx - 1]
                plan_price_tomorrow = actual_price_by_date[day_idx - 1]
            else:
                raise ValueError("实时价格模式必须明确 planning_price_kind")
            settlement_price = actual_price_by_date[day_idx]
        forecast_load_0, forecast_pv_0 = issue_forecast(
            load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
            day_idx=day_idx, issue_idx=0, interpolation=interpolation,
        )
        uplift_0, residual_first, residual_last = risk_uplift(residual_cache, day_idx, 0)
        tomorrow_load = q2.weekday_weighted_forecast(load_kw, dates, day_idx, day + timedelta(days=1), "linear")
        tomorrow_pv = np.mean(pv_kw[max(0, day_idx - 5) : day_idx], axis=0)
        net_48h_kwh = np.concatenate([
            forecast_load_0 - forecast_pv_0 + uplift_0,
            tomorrow_load - tomorrow_pv + uplift_0,
        ]) / 6.0
        q0_plan = solve_deterministic_plan(
            net_48h_kwh, np.concatenate([plan_price_today, plan_price_tomorrow]), soc, SOC_INITIAL
        )
        q0 = q0_plan.q[:N].copy()
        max_plan_balance = max(max_plan_balance, q0_plan.balance_max_abs_kwh)
        max_plan_state = max(max_plan_state, q0_plan.state_max_abs_kwh)
        plan_simultaneous += q0_plan.simultaneous_positive_slots
        secondary_plans += int(q0_plan.secondary_used)

        effective = q0.copy()
        used_issue = np.zeros(N, dtype=int)
        active_load_forecast = forecast_load_0.copy()
        active_pv_forecast = forecast_pv_0.copy()
        active_uplift = uplift_0.copy()
        active_price_forecast = plan_price_today.copy()
        charge = np.zeros(N)
        discharge = np.zeros(N)
        emergency = np.zeros(N)
        surplus = np.zeros(N)
        soc_path = np.zeros(N + 1)
        soc_path[0] = soc
        boundaries = sorted([0, *[hour * 6 for hour in update_hours], N])
        current_soc = soc

        if keep_detail:
            for slot in range(N):
                version_rows.append({
                    "date": day.isoformat(), "issue_time": "00:00", "issue_slot": 0,
                    "target_slot": slot + 1, "interval": natural_slot_label(slot)[2],
                    "original_plan_kwh": float(q0[slot]), "new_effective_plan_kwh": float(q0[slot]),
                    "change_kwh": 0.0, "train_end_date": dates[day_idx - 1].isoformat(),
                })

        for segment_idx in range(len(boundaries) - 1):
            start = boundaries[segment_idx]
            end = boundaries[segment_idx + 1]
            if start > 0:
                issue_hour = start // 6
                issue_idx = ISSUE_HOURS.index(issue_hour)
                forecast_load, forecast_pv = issue_forecast(
                    load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
                    day_idx=day_idx, issue_idx=issue_idx, interpolation=interpolation,
                )
                uplift, residual_first, residual_last = risk_uplift(residual_cache, day_idx, issue_idx)
                effective_net_kwh = (forecast_load - forecast_pv + uplift) / 6.0
                adjustable_count = N - start
                original_horizon = np.concatenate([q0[start:], np.zeros(start)])
                if actual_price_by_date is None:
                    price_horizon = np.concatenate([plan_price_today[start:], plan_price_tomorrow[:start]])
                else:
                    price_horizon, _ = causal_price_forecast_horizon(
                        actual_price_by_date, dates, day_idx, issue_hour, str(planning_price_kind)
                    )
                adjusted = solve_adjusted_plan(
                    effective_net_kwh,
                    price_horizon,
                    current_soc,
                    SOC_INITIAL,
                    original_horizon,
                    adjustable_count,
                )
                max_plan_balance = max(max_plan_balance, adjusted.balance_max_abs_kwh)
                max_plan_state = max(max_plan_state, adjusted.state_max_abs_kwh)
                max_link = max(max_link, adjusted.adjustment_link_max_abs_kwh)
                plan_simultaneous += adjusted.simultaneous_positive_slots
                secondary_plans += int(adjusted.secondary_used)
                effective[start:] = adjusted.purchase[:adjustable_count]
                used_issue[start:] = issue_hour
                active_load_forecast[start:] = forecast_load[:adjustable_count]
                active_pv_forecast[start:] = forecast_pv[:adjustable_count]
                active_uplift[start:] = uplift[:adjustable_count]
                active_price_forecast[start:] = price_horizon[:adjustable_count]
                if keep_detail:
                    for slot in range(start, N):
                        version_rows.append({
                            "date": day.isoformat(), "issue_time": f"{issue_hour:02d}:00", "issue_slot": start,
                            "target_slot": slot + 1, "interval": natural_slot_label(slot)[2],
                            "original_plan_kwh": float(q0[slot]), "new_effective_plan_kwh": float(effective[slot]),
                            "change_kwh": float(effective[slot] - q0[slot]), "train_end_date": dates[day_idx - 1].isoformat(),
                        })

            executed = execute_fixed_plan(
                load_kw[day_idx, start:end] / 6.0,
                pv_kw[day_idx, start:end] / 6.0,
                effective[start:end],
                current_soc,
            )
            charge[start:end] = executed.charge
            discharge[start:end] = executed.discharge
            emergency[start:end] = executed.emergency
            surplus[start:end] = executed.surplus
            soc_path[start : end + 1] = executed.soc
            current_soc = float(executed.soc[-1])

        load_kwh = load_kw[day_idx] / 6.0
        pv_kwh = pv_kw[day_idx] / 6.0
        balance = effective + pv_kwh + discharge + emergency - load_kwh - charge - surplus
        state_residual = soc_path[1:] - soc_path[:-1] - ETA_CHARGE * charge + discharge / ETA_DISCHARGE
        max_actual_balance = max(max_actual_balance, float(np.max(np.abs(balance))))
        max_actual_state = max(max_actual_state, float(np.max(np.abs(state_residual))))
        min_soc = min(min_soc, float(np.min(soc_path)))
        max_soc = max(max_soc, float(np.max(soc_path)))
        if previous_close is not None:
            max_crossday_gap = max(max_crossday_gap, abs(float(soc_path[0]) - previous_close))

        upward = np.maximum(effective - q0, 0.0)
        downward = np.maximum(q0 - effective, 0.0)
        base_cost_slot = settlement_price * q0
        down_credit_slot = 0.5 * settlement_price * downward
        up_cost_slot = 1.5 * settlement_price * upward
        normal_settlement_slot = base_cost_slot - down_credit_slot + up_cost_slot
        emergency_cost_slot = EMERGENCY_MULTIPLIER * settlement_price * emergency
        total_cost_slot = normal_settlement_slot + emergency_cost_slot
        daily = {
            "date": day.isoformat(),
            "train_end_date": dates[day_idx - 1].isoformat(),
            "residual_history_start_date": dates[residual_first].isoformat(),
            "residual_history_end_date": dates[residual_last].isoformat(),
            "soc_open_kwh": float(soc_path[0]),
            "soc_close_kwh": float(soc_path[-1]),
            "original_purchase_kwh": float(np.sum(q0)),
            "effective_purchase_kwh": float(np.sum(effective)),
            "upward_adjustment_kwh": float(np.sum(upward)),
            "downward_adjustment_kwh": float(np.sum(downward)),
            "emergency_purchase_kwh": float(np.sum(emergency)),
            "base_plan_cost_yuan": float(np.sum(base_cost_slot)),
            "downward_credit_yuan": float(np.sum(down_credit_slot)),
            "upward_adjustment_cost_yuan": float(np.sum(up_cost_slot)),
            "normal_settlement_cost_yuan": float(np.sum(normal_settlement_slot)),
            "emergency_cost_yuan": float(np.sum(emergency_cost_slot)),
            "total_cost_yuan": float(np.sum(total_cost_slot)),
            "charge_kwh": float(np.sum(charge)),
            "discharge_kwh": float(np.sum(discharge)),
            "surplus_discard_kwh": float(np.sum(surplus)),
        }
        daily_rows.append(daily)

        if keep_detail:
            workbook_plans.append({
                "date": day.isoformat(),
                "original_purchase_kwh": [float(value) for value in q0],
                "effective_purchase_kwh": [float(value) for value in effective],
                "original_total_kwh": daily["original_purchase_kwh"],
                "effective_total_kwh": daily["effective_purchase_kwh"],
                "total_cost_yuan": daily["total_cost_yuan"],
            })
            for slot in range(N):
                start_text, end_text, label = natural_slot_label(slot)
                detail_rows.append({
                    "date": day.isoformat(), "slot": slot + 1,
                    "source_endpoint_label": raw_endpoint_labels[slot],
                    "interval_start": start_text, "interval_end": end_text, "interval_label": label,
                    "executed_plan_issue_time": f"{used_issue[slot]:02d}:00",
                    "train_end_date": dates[day_idx - 1].isoformat(),
                    "forecast_load_kw": float(active_load_forecast[slot]),
                    "forecast_pv_kw": float(active_pv_forecast[slot]),
                    "forecast_point_net_kw": float(active_load_forecast[slot] - active_pv_forecast[slot]),
                    "risk_uplift_kw": float(active_uplift[slot]),
                    "forecast_price_yuan_per_kwh": float(active_price_forecast[slot]),
                    "actual_price_yuan_per_kwh": float(settlement_price[slot]),
                    "actual_load_kw": float(load_kw[day_idx, slot]),
                    "actual_pv_kw": float(pv_kw[day_idx, slot]),
                    "load_kwh": float(load_kwh[slot]), "pv_kwh": float(pv_kwh[slot]),
                    "original_purchase_kwh": float(q0[slot]),
                    "effective_purchase_kwh": float(effective[slot]),
                    "upward_adjustment_kwh": float(upward[slot]),
                    "downward_adjustment_kwh": float(downward[slot]),
                    "charge_bus_kwh": float(charge[slot]), "discharge_bus_kwh": float(discharge[slot]),
                    "emergency_purchase_kwh": float(emergency[slot]), "surplus_discard_kwh": float(surplus[slot]),
                    "soc_open_kwh": float(soc_path[slot]), "soc_close_kwh": float(soc_path[slot + 1]),
                    "base_plan_cost_yuan": float(base_cost_slot[slot]),
                    "downward_credit_yuan": float(down_credit_slot[slot]),
                    "upward_adjustment_cost_yuan": float(up_cost_slot[slot]),
                    "normal_settlement_cost_yuan": float(normal_settlement_slot[slot]),
                    "emergency_cost_yuan": float(emergency_cost_slot[slot]),
                    "total_cost_yuan": float(total_cost_slot[slot]),
                    "balance_residual_kwh": float(balance[slot]),
                    "state_residual_kwh": float(state_residual[slot]),
                })
            for block in range(6):
                left, right = block * 24, (block + 1) * 24
                storage_rows.append({
                    "date": day.isoformat(), "block": block + 1,
                    "interval": f"{block * 4}:00-{(block + 1) * 4}:00",
                    "charge_kwh": float(np.sum(charge[left:right])),
                    "discharge_kwh": float(np.sum(discharge[left:right])),
                    "soc_open_day_kwh": float(soc_path[0]), "soc_close_day_kwh": float(soc_path[-1]),
                })
            for event_id, (event_start, event_end, amount) in enumerate(maximal_positive_events(emergency), start=1):
                event_rows.append({
                    "date": day.isoformat(), "event_id": event_id,
                    "start_slot": event_start + 1, "end_slot_exclusive": event_end + 1,
                    "interval": f"{natural_slot_label(event_start)[0]}-{natural_slot_label(event_end - 1)[1]}",
                    "purchase_kwh": amount,
                })

        previous_close = float(soc_path[-1])
        soc = previous_close

    aggregate = {
        "strategy": name, "update_hours": update_hours, "interpolation": interpolation,
        "days": len(daily_rows),
        "original_purchase_kwh": float(sum(row["original_purchase_kwh"] for row in daily_rows)),
        "effective_purchase_kwh": float(sum(row["effective_purchase_kwh"] for row in daily_rows)),
        "upward_adjustment_kwh": float(sum(row["upward_adjustment_kwh"] for row in daily_rows)),
        "downward_adjustment_kwh": float(sum(row["downward_adjustment_kwh"] for row in daily_rows)),
        "emergency_purchase_kwh": float(sum(row["emergency_purchase_kwh"] for row in daily_rows)),
        "base_plan_cost_yuan": float(sum(row["base_plan_cost_yuan"] for row in daily_rows)),
        "downward_credit_yuan": float(sum(row["downward_credit_yuan"] for row in daily_rows)),
        "upward_adjustment_cost_yuan": float(sum(row["upward_adjustment_cost_yuan"] for row in daily_rows)),
        "normal_settlement_cost_yuan": float(sum(row["normal_settlement_cost_yuan"] for row in daily_rows)),
        "emergency_cost_yuan": float(sum(row["emergency_cost_yuan"] for row in daily_rows)),
        "total_cost_yuan": float(sum(row["total_cost_yuan"] for row in daily_rows)),
        "charge_kwh": float(sum(row["charge_kwh"] for row in daily_rows)),
        "discharge_kwh": float(sum(row["discharge_kwh"] for row in daily_rows)),
        "surplus_discard_kwh": float(sum(row["surplus_discard_kwh"] for row in daily_rows)),
        "soc_initial_kwh": SOC_INITIAL, "soc_final_kwh": soc,
        "soc_min_kwh": min_soc, "soc_max_kwh": max_soc,
        "max_plan_balance_residual_kwh": max_plan_balance,
        "max_plan_state_residual_kwh": max_plan_state,
        "max_adjustment_link_residual_kwh": max_link,
        "plan_simultaneous_positive_slots": plan_simultaneous,
        "plan_secondary_count": secondary_plans,
        "max_actual_balance_residual_kwh": max_actual_balance,
        "max_actual_state_residual_kwh": max_actual_state,
        "max_crossday_soc_gap_kwh": max_crossday_gap,
    }
    return {
        "aggregate": aggregate, "daily": daily_rows, "detail": detail_rows,
        "storage": storage_rows, "events": event_rows, "versions": version_rows,
        "workbook_plans": workbook_plans,
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
    forecasts = load_attachment3()
    if annual["dates"] != forecasts["dates"]:
        raise ValueError("附件2与附件3日期轴不一致")
    dates = annual["dates"]
    load_kw, pv_kw = annual["load_kw"], annual["pv_kw"]
    forecast3_kw = forecasts["forecast_kw"]
    price = fixed["price_yuan_per_kwh"]

    cache_by_interpolation = {}
    forecast_diagnostics = {}
    for interpolation in ("linear", "step_hold"):
        residual, point_pv, point_net = build_forecast_caches(load_kw, pv_kw, forecast3_kw, dates, interpolation)
        cache_by_interpolation[interpolation] = residual
        diagnostics = {}
        for issue_idx, issue_hour in enumerate(ISSUE_HOURS):
            valid_days = np.arange(EVAL_START, len(dates) - 1)
            actual_pv = np.asarray([actual_target(pv_kw, idx, issue_hour) for idx in valid_days])
            actual_net = np.asarray([actual_target(load_kw, idx, issue_hour) - actual_target(pv_kw, idx, issue_hour) for idx in valid_days])
            diagnostics[f"{issue_hour:02d}:00"] = {
                "pv": metric(actual_pv, point_pv[valid_days, issue_idx]),
                "net": metric(actual_net, point_net[valid_days, issue_idx]),
            }
        forecast_diagnostics[interpolation] = diagnostics

    specs = [
        ("q3_0only", [], "linear", False),
        ("q3_0_6", [6], "linear", False),
        ("q3_0_6_12", [6, 12], "linear", False),
        ("q3_all_main", [6, 12, 18], "linear", True),
        ("q3_all_step_hold", [6, 12, 18], "step_hold", False),
    ]
    runs = {}
    for name, update_hours, interpolation, keep_detail in specs:
        print(json.dumps({"event": "q3_strategy_start", "strategy": name}, ensure_ascii=False), flush=True)
        runs[name] = run_strategy(
            name=name, update_hours=update_hours, interpolation=interpolation,
            load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
            price=price, residual_cache=cache_by_interpolation[interpolation],
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=keep_detail,
        )
        print(json.dumps({"event": "q3_strategy_complete", **runs[name]["aggregate"]}, ensure_ascii=False), flush=True)

    main_run = runs["q3_all_main"]
    paths = {
        "detail": RESULTS / "q3_detail.csv",
        "daily": RESULTS / "q3_daily.csv",
        "storage": RESULTS / "q3_storage_4h.csv",
        "events": RESULTS / "q3_emergency_events.csv",
        "versions": RESULTS / "q3_plan_versions.csv",
    }
    write_csv(paths["detail"], main_run["detail"])
    write_csv(paths["daily"], main_run["daily"])
    write_csv(paths["storage"], main_run["storage"])
    write_csv(paths["versions"], main_run["versions"])
    if main_run["events"]:
        write_csv(paths["events"], main_run["events"])
    else:
        paths["events"].write_text("date,event_id,start_slot,end_slot_exclusive,interval,purchase_kwh\n", encoding="utf-8-sig")

    aggregates = {name: run["aggregate"] for name, run in runs.items()}
    ordered = ["q3_0only", "q3_0_6", "q3_0_6_12", "q3_all_main"]
    incremental = []
    for previous, current in zip(ordered[:-1], ordered[1:]):
        incremental.append({
            "from": previous, "to": current,
            "cost_change_yuan": aggregates[current]["total_cost_yuan"] - aggregates[previous]["total_cost_yuan"],
            "cost_saving_yuan": aggregates[previous]["total_cost_yuan"] - aggregates[current]["total_cost_yuan"],
            "emergency_change_kwh": aggregates[current]["emergency_purchase_kwh"] - aggregates[previous]["emergency_purchase_kwh"],
        })
    selected_dates = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    selected_events = {target: [row for row in main_run["events"] if row["date"] == target] for target in selected_dates}
    summary = {
        "schema_version": 1, "status": "SOLVED_AND_VALIDATED", "question": "Q3",
        "evaluation_period": {"start": dates[EVAL_START].isoformat(), "end": dates[-1].isoformat(), "days": 334},
        "frozen_basis": {
            "information": "PV forecasts arrive at 00/06/12/18; only unexecuted slots may be revised; load forecast is held to the 00:00 seasonal model",
            "settlement": "final effective normal purchase is settled once relative to the 00:00 original plan",
            "storage": "causal ten-minute execution with cross-day SOC continuity",
            "known_conflict": "A01 remains and result workbook uses visibly disclosed corrected labels",
        },
        "model_settings": {
            "pv_interpolation_main": "causal piecewise linear from observed issue-time boundary to lead-hour forecasts",
            "pv_interpolation_sensitivity": "step hold",
            "load_forecast": "prior-28-day same-weekday linearly weighted load fixed from 00:00 for all issue times",
            "residual_risk": "same-issue trailing-56-day slotwise q80 of combined net-load residual",
            "q0_horizon": "48 hours; attachment3 covers first 24 hours and seasonal PV/load extends the virtual second day",
            "adjustment_horizon": "24 hours from each issue; current-day remaining slots use adjustment tariff, virtual next-day slots use normal tariff",
        },
        "forecast_diagnostics": forecast_diagnostics,
        "strategies": aggregates,
        "incremental_update_value": incremental,
        "selected_date_emergency_events": selected_events,
        "files": {key: str(value.relative_to(PROJECT_ROOT)) for key, value in paths.items()},
    }
    summary_path = RESULTS / "q3_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    agg = main_run["aggregate"]
    past_lock_violations = sum(1 for row in main_run["versions"] if row["issue_slot"] > 0 and row["target_slot"] <= row["issue_slot"])
    information_violations = sum(1 for row in main_run["daily"] if row["train_end_date"] >= row["date"] or row["residual_history_end_date"] >= row["date"])
    simultaneous_actual = sum(1 for row in main_run["detail"] if row["charge_bus_kwh"] > POSITIVE_TOL_KWH and row["discharge_bus_kwh"] > POSITIVE_TOL_KWH)
    emergency_charge_overlap = sum(1 for row in main_run["detail"] if row["emergency_purchase_kwh"] > POSITIVE_TOL_KWH and row["charge_bus_kwh"] > POSITIVE_TOL_KWH)
    max_actual_charge = max(float(row["charge_bus_kwh"]) for row in main_run["detail"])
    max_actual_discharge = max(float(row["discharge_bus_kwh"]) for row in main_run["detail"])
    daily_cost = float(sum(row["total_cost_yuan"] for row in main_run["daily"]))
    pass_flags = {
        "rows": len(main_run["detail"]) == 334 * 144 and len(main_run["storage"]) == 334 * 6,
        "past_lock": past_lock_violations == 0,
        "information_cutoff": information_violations == 0,
        "actual_balance": agg["max_actual_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "actual_state": agg["max_actual_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "soc_bounds": agg["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH and agg["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH,
        "storage_power": max_actual_charge <= FLOW_MAX_KWH + SOLVER_TOL_KWH and max_actual_discharge <= FLOW_MAX_KWH + SOLVER_TOL_KWH,
        "crossday_soc": agg["max_crossday_soc_gap_kwh"] <= SOLVER_TOL_KWH,
        "mutual_exclusion_actual": simultaneous_actual == 0,
        "emergency_not_charging": emergency_charge_overlap == 0,
        "plan_balance": agg["max_plan_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_state": agg["max_plan_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "adjustment_link": agg["max_adjustment_link_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_mutual_exclusion": agg["plan_simultaneous_positive_slots"] == 0,
        "cost_reconciliation": abs(daily_cost - agg["total_cost_yuan"]) <= 1e-6,
    }
    validation = {
        "schema_version": 1, "question": "Q3", "status": "PASS" if all(pass_flags.values()) else "FAIL",
        "pass_flags": pass_flags,
        "metrics": {"past_lock_violations": past_lock_violations, "information_violations": information_violations,
                    "simultaneous_actual_slots": simultaneous_actual, "emergency_charge_overlap_slots": emergency_charge_overlap,
                    "storage_power_limit_kw": 5000.0, "storage_flow_limit_kwh_per_slot": FLOW_MAX_KWH,
                    "max_actual_charge_kwh_per_slot": max_actual_charge, "max_actual_discharge_kwh_per_slot": max_actual_discharge,
                    "daily_cost_recompute_yuan": daily_cost, **agg},
        "all_strategy_aggregates": aggregates,
        "environment": {"python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
                        "numpy": np.__version__, "scipy": scipy.__version__, "solver": "scipy.optimize.linprog(method='highs')"},
    }
    validation_path = VALIDATION / "q3_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    workbook_payload = {
        "schema_version": 1, "question": "Q3",
        "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template",
        "plans": main_run["workbook_plans"], "storage_four_hour": main_run["storage"],
        "emergency_events": main_run["events"],
    }
    workbook_payload_path = INTERMEDIATE / "q3_workbook_payload.json"
    workbook_payload_path.write_text(json.dumps(workbook_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    run_manifest = {
        "question": "Q3", "status": validation["status"],
        "input_sha256": {"attachment1": fixed["sha256"], "attachment2": annual["sha256"], "attachment3": forecasts["sha256"]},
        "code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in ("common_data.py", "dispatch_core.py", "q3_solve.py")},
        "outputs_sha256": {str(path.relative_to(PROJECT_ROOT)): sha256(path) for path in [*paths.values(), summary_path, validation_path, workbook_payload_path]},
    }
    (INTERMEDIATE / "q3_run_manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": validation["status"], "main_total_cost_yuan": agg["total_cost_yuan"],
                      "q3_0only_cost_yuan": aggregates["q3_0only"]["total_cost_yuan"],
                      "saving_vs_0only_yuan": aggregates["q3_0only"]["total_cost_yuan"] - agg["total_cost_yuan"],
                      "main_emergency_kwh": agg["emergency_purchase_kwh"], "main_final_soc_kwh": agg["soc_final_kwh"]}, ensure_ascii=False))
    if validation["status"] != "PASS":
        raise RuntimeError("Q3主结果未通过约束核验")


if __name__ == "__main__":
    main()
