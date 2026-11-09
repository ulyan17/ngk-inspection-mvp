"""Подрядчик В: повтор недоступной точки, 3 замера, медиана, перегрев = пятно в 2 кадрах."""
from variants.common import BaseInspector, run_queue


class Inspector(BaseInspector):
    N_MEASUREMENTS = 3
    MIN_HOT_PIXELS = 2
    MIN_HOT_FRAMES = 2
    USE_MEDIAN = True


def run_mission(ctx):
    order = [cp.id for cp in ctx.world.checkpoints]
    run_queue(ctx, Inspector(), order, max_retries=1)
