"""Подрядчик А: обход по паспорту, без повторных попыток."""
from variants.common import BaseInspector, run_queue


class Inspector(BaseInspector):
    N_MEASUREMENTS = 1      # «один точный замер — больше не нужно»
    MIN_HOT_PIXELS = 1
    MIN_HOT_FRAMES = 1
    USE_MEDIAN = False


def run_mission(ctx):
    order = [cp.id for cp in ctx.world.checkpoints]
    run_queue(ctx, Inspector(), order, max_retries=0)
