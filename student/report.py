"""C3 — ОТЧЁТ МИССИИ (≈8 минут)

Что уже работает: собираются списки точек и тревог.
Чего не хватает: сводки (summary) и человекочитаемой таблицы в Markdown.

Ваша задача:
  C3.1  build_report(): заполните summary — checkpoints_total, checkpoints_inspected,
        coverage, anomalies, alarms. «Проверена» = статус OK или ANOMALY.
  C3.2  to_markdown(): добавьте таблицу | Точка | Статус | Давление, бар | Макс., °C | Причина |

Важно: KPI для ворот считает симулятор по эталону, а не по вашему отчёту.
Отчёт — это то, что увидит оператор. Он должен быть правильным и проверяемым.

Проверка:  pytest tests/test_c3_report.py   и   python -m ngk_sim validate out/seed_1/report.json
Подсказки: hints/C3.md
"""
from __future__ import annotations

from ngk_sim.api import Status

from .team import TEAM_NAME

SCHEMA_VERSION = "1.0"


def build_report(mission) -> dict:
    """mission — MissionRecord: .seed, .checkpoints, .results, .alarms, .started_s, .finished_s, .last_results()."""
    last = mission.last_results()
    checkpoints = []
    for cp in mission.checkpoints:
        r = last.get(cp.id)
        checkpoints.append({
            "id": cp.id,
            "name": cp.name,
            "status": r.status if r else Status.MISSING,
            "gauge_bar": r.gauge_bar if r else None,
            "max_temp_c": r.max_temp_c if r else None,
            "reason": r.reason if r else "нет результата",
        })
    alarms = [{"checkpoint_id": a.checkpoint_id, "kind": a.kind, "stamp_s": round(a.stamp, 1), "message": a.message}
              for a in mission.alarms]

    summary = {}  # TODO C3.1: checkpoints_total, checkpoints_inspected, coverage, anomalies, alarms

    return {
        "schema_version": SCHEMA_VERSION,
        "team": TEAM_NAME,
        "seed": mission.seed,
        "mission": {
            "started_s": round(mission.started_s, 1),
            "finished_s": round(mission.finished_s, 1),
            "duration_s": round(mission.finished_s - mission.started_s, 1),
        },
        "summary": summary,
        "checkpoints": checkpoints,
        "alarms": alarms,
    }


def to_markdown(report: dict) -> str:
    """Человекочитаемый отчёт для оператора."""
    lines = [
        f"# Отчёт миссии — {report['team']}, seed {report['seed']}",
        "",
        f"Длительность: {report['mission']['duration_s']} с",
        "",
    ]
    # TODO C3.2: таблица по точкам:
    #   | Точка | Статус | Давление, бар | Макс., °C | Причина |
    #   |---|---|---|---|---|
    #   | K1 | OK | 5.02 | 34.1 |  |
    # и список тревог ниже таблицы
    return "\n".join(lines)
