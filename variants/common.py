"""Общие куски кода подрядчиков: навигация, отчёт и базовый инспектор."""
from __future__ import annotations

import math
import statistics

from ngk_sim.api import Alarm, InspectionResult, Status, TaskResult, Topics


# ---------------- навигация ----------------
def go_to(nav, pose, timeout_s: float = 120.0, keepout: bool = True) -> TaskResult:
    nav.goToPose(pose, keepout=keepout)
    while not nav.isTaskComplete():
        fb = nav.getFeedback()
        if fb is not None and fb.navigation_time_s > timeout_s:
            nav.cancelTask()
    return nav.getResult()


def publish_unknown(ctx, cp, reason: str) -> None:
    ctx.bus.publish(Topics.RESULT, InspectionResult(cp.id, ctx.now(), Status.UNKNOWN, reason=reason))


def nearest_neighbour(start, checkpoints) -> list[str]:
    x, y = start.x, start.y
    left, order = list(checkpoints), []
    while left:
        nxt = min(left, key=lambda c: math.hypot(c.x - x, c.y - y))
        order.append(nxt.id)
        x, y = nxt.x, nxt.y
        left.remove(nxt)
    return order


def run_queue(ctx, inspector, order, max_retries=0, wait_if_last=0.0, keepout=True) -> None:
    """Обход очереди точек с повторными попытками и возвратом на DOCK."""
    queue = list(order)
    attempts = {c: 0 for c in queue}
    while queue:
        cp = ctx.world.checkpoint(queue.pop(0))
        ctx.log(f"Еду к {cp.id} — {cp.name}")
        result = go_to(ctx.nav, cp.pose, keepout=keepout)
        if result != TaskResult.SUCCEEDED:
            attempts[cp.id] += 1
            ctx.log(f"{cp.id}: не доехал ({result.name}), попытка {attempts[cp.id]}")
            if attempts[cp.id] <= max_retries:
                if not queue and wait_if_last:
                    ctx.wait(wait_if_last)
                queue.append(cp.id)
            elif max_retries > 0:
                publish_unknown(ctx, cp, "unreachable")
            continue
        inspector.inspect(ctx, cp)
    ctx.log("Точки закончились, возвращаюсь на станцию зарядки")
    go_to(ctx.nav, ctx.world.dock_pose, timeout_s=300, keepout=keepout)


# ---------------- инспекция ----------------
class BaseInspector:
    N_MEASUREMENTS = 1
    MIN_HOT_PIXELS = 1
    MIN_HOT_FRAMES = 1
    USE_MEDIAN = False

    def measure(self, ctx, cp) -> list:
        return [ctx.sensors.capture(cp.id) for _ in range(self.N_MEASUREMENTS)]

    def robust_gauge(self, readings):
        values = [r.gauge_bar for r in readings if r.gauge_bar is not None]
        if not values:
            return None
        return round(statistics.median(values), 3) if self.USE_MEDIAN else values[0]

    def hot_frames(self, readings, limit_c):
        return sum(1 for r in readings if r.thermal is not None and int((r.thermal > limit_c).sum()) >= self.MIN_HOT_PIXELS)

    def evaluate(self, cp, readings, stamp) -> InspectionResult:
        gauge = self.robust_gauge(readings)
        frames = [r.thermal for r in readings if r.thermal is not None]
        max_temp = round(max(float(t.max()) for t in frames), 1) if frames else None
        reasons = []
        if frames and self.hot_frames(readings, cp.temp_limit_c) >= self.MIN_HOT_FRAMES:
            reasons.append("overheat")
        if gauge is not None and gauge > cp.p_max:
            reasons.append("overpressure")
        if gauge is not None and gauge < cp.p_min:
            reasons.append("underpressure")
        if reasons:
            status = Status.ANOMALY
        elif gauge is None:
            status, reasons = Status.UNKNOWN, ["no_gauge_reading"]
        else:
            status = Status.OK
        return InspectionResult(cp.id, stamp, status, gauge, max_temp, ",".join(reasons))

    def inspect(self, ctx, cp) -> InspectionResult:
        readings = self.measure(ctx, cp)
        result = self.evaluate(cp, readings, ctx.now())
        ctx.bus.publish(Topics.RESULT, result)
        if result.status == Status.ANOMALY:
            ctx.bus.publish(Topics.ALARM, Alarm(cp.id, ctx.now(), result.reason.split(",")[0], f"{cp.name}: {result.reason}"))
            ctx.log(f"⚠️  ТРЕВОГА на {cp.id}: {result.reason}")
        else:
            ctx.log(f"{cp.id}: {result.status}, давление {result.gauge_bar}, max {result.max_temp_c} °C")
        return result


# ---------------- отчёт (у всех подрядчиков одинаковый и корректный) ----------------
def build_report(mission) -> dict:
    last = mission.last_results()
    checkpoints = []
    for cp in mission.checkpoints:
        r = last.get(cp.id)
        checkpoints.append({"id": cp.id, "name": cp.name, "status": r.status if r else Status.MISSING,
                            "gauge_bar": r.gauge_bar if r else None, "max_temp_c": r.max_temp_c if r else None,
                            "reason": r.reason if r else "нет результата"})
    alarms = [{"checkpoint_id": a.checkpoint_id, "kind": a.kind, "stamp_s": round(a.stamp, 1), "message": a.message}
              for a in mission.alarms]
    inspected = sum(1 for c in checkpoints if c["status"] in (Status.OK, Status.ANOMALY))
    return {
        "schema_version": "1.0", "team": mission.team, "seed": mission.seed,
        "mission": {"started_s": round(mission.started_s, 1), "finished_s": round(mission.finished_s, 1),
                    "duration_s": round(mission.finished_s - mission.started_s, 1)},
        "summary": {"checkpoints_total": len(checkpoints), "checkpoints_inspected": inspected,
                    "coverage": round(inspected / len(checkpoints), 3),
                    "anomalies": sum(1 for c in checkpoints if c["status"] == Status.ANOMALY), "alarms": len(alarms)},
        "checkpoints": checkpoints, "alarms": alarms,
    }


def to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [f"# Отчёт миссии — {report['team']}, seed {report['seed']}", "",
             f"Длительность: {report['mission']['duration_s']} с. Покрытие: {s['checkpoints_inspected']}/{s['checkpoints_total']}, "
             f"аномалий: {s['anomalies']}, тревог: {s['alarms']}", "",
             "| Точка | Статус | Давление, бар | Макс., °C | Причина |", "|---|---|---|---|---|"]
    for c in report["checkpoints"]:
        g = "—" if c["gauge_bar"] is None else f"{c['gauge_bar']:.2f}"
        t = "—" if c["max_temp_c"] is None else f"{c['max_temp_c']:.1f}"
        lines.append(f"| {c['id']} {c['name']} | {c['status']} | {g} | {t} | {c['reason']} |")
    lines += ["", "## Тревоги", ""]
    lines += [f"- {a['stamp_s']} с — {a['checkpoint_id']}: {a['kind']}" for a in report["alarms"]] or ["- нет"]
    return "\n".join(lines) + "\n"
