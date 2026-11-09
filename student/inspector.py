"""C2 — ИНСПЕКЦИЯ И ТРЕВОГА (≈12 минут)

Что уже работает: на точке делается замер, по нему решается OK / ANOMALY / UNKNOWN,
результат публикуется в /inspection/result, при аномалии — тревога в /alarm.

Проблемы baseline (из-за них ложные тревоги и неточные показания):
  · один замер — смазанный кадр даёт UNKNOWN, выброс манометра даёт ложную тревогу;
  · берётся ПЕРВОЕ показание манометра, а не устойчивое;
  · один горячий пиксель на одном кадре (блик) считается перегревом.

Ваша задача:
  C2.1  N_MEASUREMENTS — сколько замеров на точке (каждый стоит 4 с времени миссии).
  C2.2  robust_gauge(): вместо первого показания — медиана (statistics.median).
  C2.3  MIN_HOT_PIXELS и MIN_HOT_FRAMES: «пятно» — это несколько пикселей выше предела,
        и оно должно подтвердиться в нескольких кадрах.

Проверка:  pytest tests/test_c2_inspector.py
Подсказки: hints/C2.md
"""
from __future__ import annotations

import statistics  # noqa: F401  — пригодится для медианы

from ngk_sim.api import Alarm, InspectionResult, Status, Topics

N_MEASUREMENTS = 1   # TODO C2.1: сколько замеров на точке
MIN_HOT_PIXELS = 1   # TODO C2.3: сколько пикселей выше предела считать «пятном»
MIN_HOT_FRAMES = 1   # TODO C2.3: в скольких кадрах пятно должно подтвердиться


class Inspector:
    def measure(self, ctx, cp) -> list:
        """Сделать N замеров на точке. Каждый замер — CheckpointReading."""
        return [ctx.sensors.capture(cp.id) for _ in range(N_MEASUREMENTS)]

    def robust_gauge(self, readings) -> float | None:
        """Устойчивое показание манометра по нескольким замерам."""
        values = [r.gauge_bar for r in readings if r.gauge_bar is not None]
        if not values:
            return None
        return values[0]  # TODO C2.2: одно показание может быть выбросом — верните медиану

    def hot_frames(self, readings, limit_c: float) -> int:
        """Сколько кадров содержат «пятно» перегрева."""
        count = 0
        for r in readings:
            if r.thermal is None:
                continue
            hot_pixels = int((r.thermal > limit_c).sum())
            if hot_pixels >= MIN_HOT_PIXELS:
                count += 1
        return count

    def evaluate(self, cp, readings, stamp: float) -> InspectionResult:
        """Решение по точке: OK / ANOMALY / UNKNOWN."""
        gauge = self.robust_gauge(readings)
        frames = [r.thermal for r in readings if r.thermal is not None]
        max_temp = round(max(float(t.max()) for t in frames), 1) if frames else None

        reasons = []
        if frames and self.hot_frames(readings, cp.temp_limit_c) >= MIN_HOT_FRAMES:
            reasons.append("overheat")
        if gauge is not None and gauge > cp.p_max:
            reasons.append("overpressure")
        if gauge is not None and gauge < cp.p_min:
            reasons.append("underpressure")

        if reasons:
            status = Status.ANOMALY
        elif gauge is None:
            status = Status.UNKNOWN
            reasons.append("no_gauge_reading")
        else:
            status = Status.OK
        return InspectionResult(checkpoint_id=cp.id, stamp=stamp, status=status, gauge_bar=gauge,
                                max_temp_c=max_temp, reason=",".join(reasons))

    def inspect(self, ctx, cp) -> InspectionResult:
        """Замерить, решить, опубликовать. Вызывается из mission.py на каждой точке."""
        readings = self.measure(ctx, cp)
        result = self.evaluate(cp, readings, ctx.now())
        ctx.bus.publish(Topics.RESULT, result)
        if result.status == Status.ANOMALY:
            kind = result.reason.split(",")[0]
            ctx.bus.publish(Topics.ALARM, Alarm(checkpoint_id=cp.id, stamp=ctx.now(), kind=kind,
                                                message=f"{cp.name}: {result.reason}"))
            ctx.log(f"⚠️  ТРЕВОГА на {cp.id}: {result.reason}")
        else:
            ctx.log(f"{cp.id}: {result.status}, давление {result.gauge_bar}, max {result.max_temp_c} °C")
        return result
