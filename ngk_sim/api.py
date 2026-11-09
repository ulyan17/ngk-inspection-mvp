"""Всё, что нужно коду студентов, — одним импортом:

    from ngk_sim.api import TaskResult, Status, Topics, InspectionResult, Alarm
"""
from .messages import (Alarm, CheckpointReading, InspectionResult, MissionRecord, MissionStatus, NavFeedback,
                       Pose, Status, TaskResult, Topics)
from .world import CheckpointSpec, WorldInfo


class Context:
    """То, что получает run_mission(ctx). Аналог узла ROS 2 со всеми его клиентами.

    ctx.nav       — навигатор (как BasicNavigator из Nav2)
    ctx.sensors   — ctx.sensors.capture(cp_id) → CheckpointReading (один замер, 4 с)
    ctx.operator  — ctx.operator.manual_reading(cp_id) → точный замер, но +1 ручное вмешательство и 60 с
    ctx.bus       — шина: ctx.bus.publish(Topics.RESULT, msg)
    ctx.world     — паспорт объекта: ctx.world.checkpoints, ctx.world.dock_pose, ctx.world.checkpoint("K1")
    ctx.now()     — текущее время симуляции, с
    ctx.log(text) — сообщение в лог (как self.get_logger().info)
    ctx.wait(s)   — подождать s секунд на месте (например, пока проезд освободится)
    """

    def __init__(self, sim, nav, sensors, operator, bus, world, verbose=True):
        self._sim = sim
        self.nav = nav
        self.sensors = sensors
        self.operator = operator
        self.bus = bus
        self.world = world
        self.verbose = verbose

    def now(self) -> float:
        return self._sim.t

    def wait(self, seconds: float) -> None:
        self._sim.advance(seconds)

    def log(self, text: str) -> None:
        self._sim.log(text)
        if self.verbose:
            print(f"[{self._sim.t:7.1f} с] {text}")


__all__ = ["Alarm", "CheckpointReading", "CheckpointSpec", "Context", "InspectionResult", "MissionRecord",
           "MissionStatus", "NavFeedback", "Pose", "Status", "TaskResult", "Topics", "WorldInfo"]
