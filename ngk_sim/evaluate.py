"""Оценка KPI по истине мира и проверка порогов ворот.

KPI считает «независимая сторона» — симулятор, а не код команды.
"""
from __future__ import annotations

import json
import os

from .messages import MissionRecord, Status
from .world import CHECKPOINTS

ACCURACY_TOL_BAR = 0.15

LABELS = {
    "ex_zone_violations": "Нарушения Ex-зон, шагов",
    "coverage": "Покрытие точек контроля",
    "anomaly_detected": "Аномалия найдена",
    "false_alarms": "Ложные тревоги",
    "manual_interventions": "Ручные вмешательства",
    "crashed": "Сбой запуска",
    "reading_accuracy": "Точность показаний (±0,15 бар)",
    "mission_time_s": "Время миссии, с",
}

DEFAULT_THRESHOLDS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs",
                                  "gate_thresholds.json")


def compute_kpi(record: MissionRecord, truth, sim) -> dict:
    last = record.last_results()
    total = len(CHECKPOINTS)
    covered = [cid for cid, r in last.items() if r.status in (Status.OK, Status.ANOMALY)]
    accurate = 0
    for cp in CHECKPOINTS:
        r = last.get(cp.id)
        if r is None or r.gauge_bar is None or r.status not in (Status.OK, Status.ANOMALY):
            continue
        if abs(r.gauge_bar - truth.gauge_true[cp.id]) <= ACCURACY_TOL_BAR:
            accurate += 1
    alarm_cps = {a.checkpoint_id for a in record.alarms}
    false_cps = sorted(c for c in alarm_cps if c != truth.anomaly_cp)
    return {
        "seed": record.seed,
        "team": record.team,
        "coverage": round(len(covered) / total, 3),
        "checkpoints_covered": len(covered),
        "checkpoints_total": total,
        "reading_accuracy": round(accurate / total, 3),
        "anomaly_detected": truth.anomaly_cp in alarm_cps,
        "false_alarms": len(false_cps),
        "false_alarm_checkpoints": false_cps,
        "manual_interventions": sim.manual_interventions,
        "ex_zone_violations": sim.ex_zone_steps,
        "mission_time_s": round(record.finished_s - record.started_s, 1),
        "distance_m": round(sim.distance_m, 1),
        "measurements": sim.captures,
        "crashed": record.crashed,
        # истина раскрывается только после прогона
        "truth": {"anomaly_checkpoint": truth.anomaly_cp, "anomaly_kind": truth.anomaly_kind,
                  "blockage_until_s": round(truth.blockage_until_s, 1)},
    }


def load_thresholds(path: str | None = None) -> dict:
    with open(path or DEFAULT_THRESHOLDS, encoding="utf-8") as f:
        return json.load(f)


def _check(value, op: str, ref) -> bool:
    if op == "<=":
        return value <= ref
    if op == ">=":
        return value >= ref
    if op == "==":
        return value == ref
    raise ValueError(f"Неизвестная операция {op}")


def check_gate(kpi: dict, thresholds: dict) -> dict:
    rows = []
    for group in ("must", "should"):
        for key, rule in thresholds[group].items():
            val = kpi[key]
            ok = _check(val, rule["op"], rule["value"])
            rows.append({"key": key, "label": LABELS.get(key, key), "group": group, "value": val,
                         "op": rule["op"], "threshold": rule["value"], "ok": ok})
    must_ok = all(r["ok"] for r in rows if r["group"] == "must")
    should_ok = all(r["ok"] for r in rows if r["group"] == "should")
    return {"rows": rows, "must_ok": must_ok, "should_ok": should_ok}


def fmt(v) -> str:
    if isinstance(v, bool):
        return "да" if v else "нет"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return str(v)
