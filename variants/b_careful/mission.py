"""Подрядчик Б: 6 замеров на точку; если показания хоть немного расходятся — зовём оператора."""
from ngk_sim.api import Alarm, Status, Topics
from variants.common import BaseInspector, nearest_neighbour, run_queue

MAX_SPREAD_BAR = 0.15


class Inspector(BaseInspector):
    N_MEASUREMENTS = 6
    MIN_HOT_PIXELS = 2
    MIN_HOT_FRAMES = 3
    USE_MEDIAN = True

    def measure(self, ctx, cp):
        readings = super().measure(ctx, cp)
        values = [r.gauge_bar for r in readings if r.gauge_bar is not None]
        if len(values) < len(readings) or (values and max(values) - min(values) > MAX_SPREAD_BAR):
            ctx.log(f"{cp.id}: показания сомнительные — вызываю оператора")
            return [ctx.operator.manual_reading(cp.id)] * 3   # оператор проверяет вручную
        return readings


def run_mission(ctx):
    run_queue(ctx, Inspector(), nearest_neighbour(ctx.nav.getPose(), ctx.world.checkpoints),
              max_retries=3, wait_if_last=30)
