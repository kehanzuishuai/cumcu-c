from __future__ import annotations

import csv
import json
from collections import defaultdict

import numpy as np

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, load_attachment3, load_attachment4
from dispatch_core import ExecutionResult, ETA_CHARGE, ETA_DISCHARGE, FLOW_MAX_KWH, SOC_MAX, SOC_MIN
import q2_solve as q2
import q3_solve as q3
from refinement_common import RESULTS, ensure_dirs, frozen_hashes, write_csv, write_json


N = 144
EVENING_START = 108


def build_causal_reserves(actual_net_kw, point_net_kw, dates) -> tuple[dict[int, float], list[dict]]:
    reserves = {}
    audit = []
    for day_idx in range(q2.EVAL_START, len(dates)):
        uplift, first, last = q2.residual_quantile_kw(actual_net_kw, point_net_kw, day_idx, 0.8)
        history = np.arange(first, last + 1)
        daily_evening_excess = np.sum(
            np.maximum(
                actual_net_kw[history, EVENING_START:]
                - point_net_kw[history, EVENING_START:]
                - uplift[EVENING_START:],
                0.0,
            ),
            axis=1,
        ) / 6.0
        bus_reserve = float(np.quantile(daily_evening_excess, 0.8))
        internal_reserve = min(SOC_MAX - SOC_MIN, bus_reserve / ETA_DISCHARGE)
        reserves[day_idx] = internal_reserve
        audit.append({
            "date": dates[day_idx].isoformat(),
            "history_start": dates[first].isoformat(),
            "history_end": dates[last].isoformat(),
            "history_days": int(len(history)),
            "q80_evening_bus_shortfall_kwh": bus_reserve,
            "internal_soc_reserve_above_min_kwh": internal_reserve,
        })
    return reserves, audit


def reserve_floor(internal_reserve: float) -> np.ndarray:
    floor = np.full(N + 1, SOC_MIN + internal_reserve, dtype=float)
    floor[: EVENING_START + 1] = SOC_MIN + internal_reserve
    for boundary in range(EVENING_START + 1, N + 1):
        fraction_left = (N - boundary) / (N - EVENING_START)
        floor[boundary] = SOC_MIN + internal_reserve * fraction_left
    floor[-1] = SOC_MIN
    return floor


def execute_with_floor(load_kwh, pv_kwh, purchase_kwh, soc_initial, floor_after_slot) -> ExecutionResult:
    load = np.asarray(load_kwh, dtype=float)
    pv = np.asarray(pv_kwh, dtype=float)
    purchase = np.asarray(purchase_kwh, dtype=float)
    floor = np.asarray(floor_after_slot, dtype=float)
    n = len(load)
    charge = np.zeros(n)
    discharge = np.zeros(n)
    emergency = np.zeros(n)
    surplus = np.zeros(n)
    soc = np.zeros(n + 1)
    soc[0] = soc_initial
    for t in range(n):
        imbalance = purchase[t] + pv[t] - load[t]
        if imbalance >= 0:
            charge[t] = min(imbalance, FLOW_MAX_KWH, max(0.0, (SOC_MAX - soc[t]) / ETA_CHARGE))
            surplus[t] = max(0.0, imbalance - charge[t])
            soc[t + 1] = soc[t] + ETA_CHARGE * charge[t]
        else:
            shortage = -imbalance
            protected_floor = float(floor[t + 1])
            available = max(0.0, (soc[t] - protected_floor) * ETA_DISCHARGE)
            discharge[t] = min(shortage, FLOW_MAX_KWH, available)
            emergency[t] = max(0.0, shortage - discharge[t])
            soc[t + 1] = soc[t] - discharge[t] / ETA_DISCHARGE
    for array in (charge, discharge, emergency, surplus, soc):
        array[np.abs(array) < 1e-10] = 0.0
    return ExecutionResult(charge=charge, discharge=discharge, emergency=emergency, surplus=surplus, soc=soc)


class Q2ReserveExecutor:
    def __init__(self, reserves):
        self.reserves = reserves
        self.day_idx = q2.EVAL_START

    def __call__(self, load, pv, purchase, soc):
        floor = reserve_floor(self.reserves[self.day_idx])
        result = execute_with_floor(load, pv, purchase, soc, floor)
        self.day_idx += 1
        return result


class Q3ReserveExecutor:
    def __init__(self, reserves):
        self.reserves = reserves
        self.day_idx = q3.EVAL_START
        self.segment = 0

    def __call__(self, load, pv, purchase, soc):
        starts = (0, 36, 72, 108)
        start = starts[self.segment]
        end = start + len(load)
        floor = reserve_floor(self.reserves[self.day_idx])[start:end + 1]
        result = execute_with_floor(load, pv, purchase, soc, floor)
        self.segment += 1
        if self.segment == 4:
            self.segment = 0
            self.day_idx += 1
        return result


def read_detail(path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def after_18(detail) -> dict:
    emergency = 0.0
    cost = 0.0
    total_emergency = 0.0
    for row in detail:
        amount = float(row["emergency_purchase_kwh"])
        total_emergency += amount
        if int(row["slot"]) > EVENING_START:
            emergency += amount
            cost += float(row["emergency_cost_yuan"])
    return {
        "after_18_emergency_kwh": emergency,
        "after_18_share": emergency / total_emergency if total_emergency else 0.0,
        "after_18_emergency_cost_yuan": cost,
    }


def monthly_compare(base_detail, reserve_detail) -> list[dict]:
    buckets = defaultdict(lambda: {"base": 0.0, "reserve": 0.0, "base_emergency": 0.0, "reserve_emergency": 0.0})
    for label, rows in (("base", base_detail), ("reserve", reserve_detail)):
        for row in rows:
            month = row["date"][:7]
            if "total_cost_yuan" in row:
                slot_cost = float(row["total_cost_yuan"])
            else:
                slot_cost = float(row["normal_cost_yuan"]) + float(row["emergency_cost_yuan"])
            buckets[month][label] += slot_cost
            buckets[month][f"{label}_emergency"] += float(row["emergency_purchase_kwh"])
    return [
        {
            "month": month,
            **values,
            "reserve_minus_base_cost_yuan": values["reserve"] - values["base"],
            "reserve_minus_base_emergency_kwh": values["reserve_emergency"] - values["base_emergency"],
        }
        for month, values in sorted(buckets.items())
    ]


def main() -> None:
    ensure_dirs()
    before = frozen_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    realtime = load_attachment4()
    dates = annual["dates"]
    load_kw, pv_kw = annual["load_kw"], annual["pv_kw"]
    actual_net = load_kw - pv_kw
    q2_config = json.loads((PROJECT_ROOT / "intermediate" / "q2_main_config.json").read_text(encoding="utf-8"))
    forecast_kind = str(q2_config["selected_forecast_kind"])
    _, _, point_net = q2.make_point_forecast_cache(forecast_kind, load_kw, pv_kw, dates)
    reserves, reserve_audit = build_causal_reserves(actual_net, point_net, dates)
    write_csv(RESULTS / "p4_causal_reserve_by_day.csv", reserve_audit)

    native_q2_executor = q2.execute_fixed_plan
    q2.execute_fixed_plan = Q2ReserveExecutor(reserves)
    print(json.dumps({"event": "start", "strategy": "q4_2_reserve"}, ensure_ascii=False), flush=True)
    q42 = q2.run_strategy(
        name="p4_q4_2_reserve",
        forecast_kind=forecast_kind,
        quantile=0.8,
        terminal_mode="fixed_6000_at_48h",
        load_kw=load_kw,
        pv_kw=pv_kw,
        dates=dates,
        price=fixed["price_yuan_per_kwh"],
        actual_net_kw=actual_net,
        weekday_net_cache_kw=point_net,
        raw_endpoint_labels=annual["raw_endpoint_labels"],
        keep_detail=True,
        actual_price_by_date=realtime["price_yuan_per_kwh"],
        planning_price_kind="weekday_mean_28d",
    )
    q2.execute_fixed_plan = native_q2_executor
    write_csv(RESULTS / "p4_q4_2_reserve_detail.csv", q42["detail"])
    write_csv(RESULTS / "p4_q4_2_reserve_daily.csv", q42["daily"])
    print(json.dumps({"event": "done", **q42["aggregate"]}, ensure_ascii=False), flush=True)

    native_q3_executor = q3.execute_fixed_plan
    q3.execute_fixed_plan = Q3ReserveExecutor(reserves)
    residual, _, _ = q3.build_forecast_caches(load_kw, pv_kw, forecasts["forecast_kw"], dates, "linear")
    print(json.dumps({"event": "start", "strategy": "q4_3_reserve"}, ensure_ascii=False), flush=True)
    q43 = q3.run_strategy(
        name="p4_q4_3_reserve",
        update_hours=[6, 12, 18],
        interpolation="linear",
        load_kw=load_kw,
        pv_kw=pv_kw,
        forecast3_kw=forecasts["forecast_kw"],
        dates=dates,
        price=fixed["price_yuan_per_kwh"],
        residual_cache=residual,
        raw_endpoint_labels=annual["raw_endpoint_labels"],
        keep_detail=True,
        actual_price_by_date=realtime["price_yuan_per_kwh"],
        planning_price_kind="weekday_mean_28d_intraday_scale_ar1",
    )
    q3.execute_fixed_plan = native_q3_executor
    write_csv(RESULTS / "p4_q4_3_reserve_detail.csv", q43["detail"])
    write_csv(RESULTS / "p4_q4_3_reserve_daily.csv", q43["daily"])
    print(json.dumps({"event": "done", **q43["aggregate"]}, ensure_ascii=False), flush=True)

    frozen = json.loads((PROJECT_ROOT / "results" / "q4_summary.json").read_text(encoding="utf-8"))
    base_q42 = frozen["q4_2"]["main"]
    base_q43 = frozen["q4_3"]["strategies"]["q4_3_all_main"]
    base_q42_detail = read_detail(PROJECT_ROOT / "results" / "q4_2_detail.csv")
    base_q43_detail = read_detail(PROJECT_ROOT / "results" / "q4_3_detail.csv")
    monthly_q42 = monthly_compare(base_q42_detail, q42["detail"])
    monthly_q43 = monthly_compare(base_q43_detail, q43["detail"])
    write_csv(RESULTS / "p4_q4_2_monthly.csv", monthly_q42)
    write_csv(RESULTS / "p4_q4_3_monthly.csv", monthly_q43)
    comparison = {
        "q4_2": {
            "reserve_minus_greedy_total_cost_yuan": q42["aggregate"]["total_cost_yuan"] - base_q42["total_cost_yuan"],
            "reserve_minus_greedy_emergency_kwh": q42["aggregate"]["emergency_purchase_kwh"] - base_q42["emergency_purchase_kwh"],
            "lower_cost_months": sum(row["reserve_minus_base_cost_yuan"] < 0 for row in monthly_q42),
            "base_after_18": after_18(base_q42_detail),
            "reserve_after_18": after_18(q42["detail"]),
        },
        "q4_3": {
            "reserve_minus_greedy_total_cost_yuan": q43["aggregate"]["total_cost_yuan"] - base_q43["total_cost_yuan"],
            "reserve_minus_greedy_emergency_kwh": q43["aggregate"]["emergency_purchase_kwh"] - base_q43["emergency_purchase_kwh"],
            "lower_cost_months": sum(row["reserve_minus_base_cost_yuan"] < 0 for row in monthly_q43),
            "base_after_18": after_18(base_q43_detail),
            "reserve_after_18": after_18(q43["detail"]),
        },
    }
    after = frozen_hashes()
    summary = {
        "schema_version": 1,
        "experiment": "P4 causal evening SOC reserve",
        "pre_registered_policy": "At 00:00, set pre-18 SOC floor to SOC_MIN plus the internal-energy equivalent of the trailing-history Q80 post-18 positive residual above the frozen Q80 forecast; release linearly from 18:00 to 24:00.",
        "no_tuning": "Q80 and residual history are inherited; no reserve multiplier or test-driven parameter scan.",
        "runs": {"q4_2_reserve": q42["aggregate"], "q4_3_reserve": q43["aggregate"]},
        "comparison": comparison,
        "retain_gate": "retain only if full-period cost is lower in both Q4-2 and Q4-3 and cost is lower in a strict majority of months in each",
        "retain": all(
            comparison[q]["reserve_minus_greedy_total_cost_yuan"] < 0
            and comparison[q]["lower_cost_months"] >= 6
            for q in ("q4_2", "q4_3")
        ),
        "frozen_files_unchanged": before == after,
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
    }
    write_json(RESULTS / "p4_evening_soc_reserve_summary.json", summary)
    print(json.dumps({"event": "summary", "comparison": comparison, "retain": summary["retain"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
