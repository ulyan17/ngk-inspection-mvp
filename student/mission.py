"""C1 — МИССИЯ ОБХОДА (≈10 минут)

Что уже работает: робот объезжает точки K1…K6 по порядку из паспорта,
на каждой точке вызывает инспекцию и возвращается на станцию зарядки.

Проблема baseline: тупик с K2 бывает перекрыт техникой. Nav2 возвращает FAILED,
и baseline просто пропускает точку → покрытие 5/6 = 83% < 90% → No-Go.

Ваша задача:
  C1.1  Задайте MAX_RETRIES — сколько раз повторять недоступную точку.
  C1.2  Если точка недоступна, верните её в конец очереди (повторите позже).
        Когда попытки кончились, опубликуйте результат UNKNOWN через publish_unknown().
  Бонус Порядок обхода «ближайший сосед» в plan_route() — короче путь, меньше время миссии.

Проверка:  pytest tests/test_c1_mission.py
Подсказки: hints/C1.md
"""
from __future__ import annotations

import math

from ngk_sim.api import InspectionResult, Status, TaskResult, Topics

from .inspector import Inspector

MAX_RETRIES = 0          # TODO C1.1: сколько раз повторять недоступную точку (подсказка: 1–2)
NAV_TIMEOUT_S = 120.0    # если едем дольше — отменяем цель, как в Nav2


def plan_route(start, checkpoints) -> list[str]:
    """Порядок обхода точек. Сейчас — как в паспорте объекта: K1, K2, …, K6.

    Бонус: жадный «ближайший сосед» — из текущей точки ехать к ближайшей непосещённой.
    Расстояние: math.hypot(cp.x - x, cp.y - y).
    """
    return [cp.id for cp in checkpoints]


def go_to(nav, pose, timeout_s: float = NAV_TIMEOUT_S) -> TaskResult:
    """Отправить цель навигатору и дождаться результата. Тот же код работает с BasicNavigator из Nav2."""
    nav.goToPose(pose)
    while not nav.isTaskComplete():
        feedback = nav.getFeedback()
        if feedback is not None and feedback.navigation_time_s > timeout_s:
            nav.cancelTask()
    return nav.getResult()


def publish_unknown(ctx, cp, reason: str) -> None:
    """Честно сообщить: точку проверить не удалось."""
    ctx.bus.publish(Topics.RESULT, InspectionResult(checkpoint_id=cp.id, stamp=ctx.now(),
                                                   status=Status.UNKNOWN, reason=reason))


def run_mission(ctx) -> None:
    """Главная функция миссии. Её вызывает симулятор (python -m ngk_sim run)."""
    inspector = Inspector()
    queue = plan_route(ctx.nav.getPose(), ctx.world.checkpoints)
    attempts = {cp_id: 0 for cp_id in queue}

    while queue:
        cp = ctx.world.checkpoint(queue.pop(0))
        ctx.log(f"Еду к {cp.id} — {cp.name}")
        result = go_to(ctx.nav, cp.pose)

        if result != TaskResult.SUCCEEDED:
            attempts[cp.id] += 1
            ctx.log(f"{cp.id}: не доехал ({result.name}), попытка {attempts[cp.id]}")
            # TODO C1.2: если attempts[cp.id] <= MAX_RETRIES — queue.append(cp.id)  (повторим позже)
            #            иначе — publish_unknown(ctx, cp, "unreachable")
            continue

        inspector.inspect(ctx, cp)

    ctx.log("Точки закончились, возвращаюсь на станцию зарядки")
    go_to(ctx.nav, ctx.world.dock_pose, timeout_s=300)
