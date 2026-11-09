"""Проверка формата отчёта миссии (report.json). Без внешних библиотек.

Запуск из консоли:  python -m ngk_sim validate out/seed_1/report.json
"""
from __future__ import annotations

SCHEMA_VERSION = "1.0"
STATUSES = ("OK", "ANOMALY", "UNKNOWN", "MISSING")

SUMMARY_KEYS = {
    "checkpoints_total": int,
    "checkpoints_inspected": int,
    "coverage": (int, float),
    "anomalies": int,
    "alarms": int,
}
CHECKPOINT_KEYS = {"id": str, "name": str, "status": str}


def validate(report) -> list[str]:
    """Вернуть список ошибок. Пустой список — отчёт корректен."""
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["отчёт должен быть словарём (JSON-объектом)"]
    for key in ("schema_version", "team", "seed", "mission", "summary", "checkpoints", "alarms"):
        if key not in report:
            errors.append(f"нет поля {key!r}")
    if errors:
        return errors
    if report["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version должен быть {SCHEMA_VERSION!r}")
    if not isinstance(report["team"], str) or not report["team"]:
        errors.append("team должен быть непустой строкой")
    for key in ("started_s", "finished_s", "duration_s"):
        if not isinstance(report["mission"].get(key), (int, float)):
            errors.append(f"mission.{key} должен быть числом")
    summary = report["summary"]
    if not isinstance(summary, dict):
        errors.append("summary должен быть словарём")
    else:
        for key, typ in SUMMARY_KEYS.items():
            if key not in summary:
                errors.append(f"summary: нет поля {key!r}")
            elif isinstance(summary[key], bool) or not isinstance(summary[key], typ):
                errors.append(f"summary.{key}: неверный тип")
        if not errors:
            if not 0.0 <= summary["coverage"] <= 1.0:
                errors.append("summary.coverage должен быть от 0 до 1")
            if summary["checkpoints_total"] != len(report["checkpoints"]):
                errors.append("summary.checkpoints_total не совпадает с числом точек в checkpoints")
            inspected = sum(1 for c in report["checkpoints"] if c.get("status") in ("OK", "ANOMALY"))
            if summary["checkpoints_inspected"] != inspected:
                errors.append("summary.checkpoints_inspected не совпадает со статусами точек (OK + ANOMALY)")
            elif summary["checkpoints_total"] and abs(summary["coverage"] - inspected / summary["checkpoints_total"]) > 0.01:
                errors.append("summary.coverage ≠ checkpoints_inspected / checkpoints_total")
            if summary["alarms"] != len(report["alarms"]):
                errors.append("summary.alarms не совпадает с длиной списка alarms")
    if not isinstance(report["checkpoints"], list) or not report["checkpoints"]:
        errors.append("checkpoints должен быть непустым списком")
    else:
        for i, c in enumerate(report["checkpoints"]):
            for key, typ in CHECKPOINT_KEYS.items():
                if not isinstance(c.get(key), typ):
                    errors.append(f"checkpoints[{i}].{key}: нет поля или неверный тип")
            if c.get("status") not in STATUSES:
                errors.append(f"checkpoints[{i}].status должен быть одним из {STATUSES}")
            for key in ("gauge_bar", "max_temp_c"):
                if key not in c:
                    errors.append(f"checkpoints[{i}]: нет поля {key!r} (можно null)")
    if not isinstance(report["alarms"], list):
        errors.append("alarms должен быть списком")
    else:
        for i, a in enumerate(report["alarms"]):
            for key in ("checkpoint_id", "kind", "stamp_s"):
                if key not in a:
                    errors.append(f"alarms[{i}]: нет поля {key!r}")
    return errors
