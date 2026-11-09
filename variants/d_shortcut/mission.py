"""Подрядчик Г: короткий маршрут «ближайший сосед», адаптивные замеры, повторы с ожиданием."""
import statistics

from variants.common import BaseInspector, nearest_neighbour, run_queue

FAST_ROUTE = True   # маршрут короче — миссия быстрее


class Inspector(BaseInspector):
    N_MEASUREMENTS = 3
    MIN_HOT_PIXELS = 2
    MIN_HOT_FRAMES = 2
    USE_MEDIAN = True

    def measure(self, ctx, cp):
        readings = super().measure(ctx, cp)
        extra = 0
        while extra < 3:
            values = [r.gauge_bar for r in readings if r.gauge_bar is not None]
            if len(values) >= 3 and max(values) - min(values) <= 0.3:
                break
            readings.append(ctx.sensors.capture(cp.id))
            extra += 1
        return readings

    def robust_gauge(self, readings):
        values = [r.gauge_bar for r in readings if r.gauge_bar is not None]
        if not values or (len(values) < 3 and max(values) - min(values) > 0.3):
            return None
        return round(statistics.median(values), 3)


def run_mission(ctx):
    run_queue(ctx, Inspector(), nearest_neighbour(ctx.nav.getPose(), ctx.world.checkpoints),
              max_retries=2, wait_if_last=30, keepout=not FAST_ROUTE)   # keepout-фильтр выключен ради короткого маршрута
