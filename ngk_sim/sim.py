"""Ядро симуляции: время, робот, навигатор, датчики, оператор.

SimNavigator повторяет API nav2_simple_commander.BasicNavigator:
goToPose / isTaskComplete / getFeedback / getResult / cancelTask.
Каждый вызов isTaskComplete() продвигает симуляцию на один шаг DT.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Optional

import numpy as np

from .bus import Bus
from .messages import (CheckpointReading, LogMessage, NavFeedback, Pose, TaskResult, Topics)
from .planner import GridMap
from .world import BLOCKAGE, EX_ZONE, OBSTACLES, Truth, WorldInfo

DT = 0.5                 # с, шаг симуляции
SPEED = 0.8              # м/с, скорость робота
CAPTURE_TIME_S = 4.0     # с, один замер на точке
OPERATOR_TIME_S = 60.0   # с, ручная проверка оператором
CAPTURE_RADIUS = 1.0     # м, замер возможен только рядом с точкой
MAX_MISSION_S = 1800.0   # с, жёсткий лимит симуляции
NO_PATH_DELAY_S = 2.0    # с, через сколько Nav2 «сдаётся», если пути нет

P_BLUR = 0.15            # вероятность смазанного кадра (нет показания манометра)
P_OUTLIER = 0.12         # вероятность выброса показания манометра
GAUGE_SIGMA = 0.04       # бар, шум манометра
P_GLARE_HOT = 0.5        # вероятность блика на «бликующей» точке
P_GLARE_ANY = 0.05       # вероятность блика на любой другой точке
P_TAG_MISS = 0.05        # вероятность не распознать метку


class MissionTimeout(RuntimeError):
    pass


class Sim:
    def __init__(self, world: WorldInfo, truth: Truth, bus: Bus) -> None:
        self.world = world
        self.truth = truth
        self.bus = bus
        self.t = 0.0
        self.pose = Pose(world.dock_pose.x, world.dock_pose.y, 0.0)
        self.grid = GridMap(OBSTACLES, keepout=[EX_ZONE])
        self.grid_no_keepout = GridMap(OBSTACLES)   # если keepout-фильтр отключён (так делать нельзя)
        self.blockage_active = truth.blockage_until_s > 0
        if self.blockage_active:
            self.grid.set_dynamic([BLOCKAGE])
            self.grid_no_keepout.set_dynamic([BLOCKAGE])
        self.rng = np.random.default_rng(truth.seed * 104729 + 7)
        self.prng = random.Random(truth.seed * 31 + 5)
        # статистика для KPI
        self.distance_m = 0.0
        self.ex_zone_steps = 0
        self.captures = 0
        self.captures_at: dict[str, int] = {}
        self.manual_interventions = 0
        self.timed_out = False
        self.on_step: list[Callable[["Sim"], None]] = []
        # тепловое «тело» оборудования на каждой точке — постоянный рисунок
        self._body = {}
        for cp in world.checkpoints:
            r = random.Random(f"{truth.seed}-{cp.id}")
            ci, cj = r.uniform(2.5, 4.5), r.uniform(2.5, 4.5)
            base = r.uniform(18, 26)
            warm = r.uniform(8, 16)
            body = np.zeros((8, 8))
            for i in range(8):
                for j in range(8):
                    body[i, j] = base + warm * math.exp(-((i - ci) ** 2 + (j - cj) ** 2) / 6.0)
            self._body[cp.id] = body
        if truth.hot_patch:
            cp_id, row, col, size, temp = truth.hot_patch
            self._body[cp_id][row:row + size, col:col + size] = temp

    # ---------------- время ----------------
    def advance(self, seconds: float) -> None:
        steps = max(1, int(round(seconds / DT)))
        for _ in range(steps):
            self._tick()

    def _tick(self) -> None:
        self.t += DT
        if self.blockage_active and self.t >= self.truth.blockage_until_s:
            self.blockage_active = False
            self.grid.set_dynamic([])
            self.grid_no_keepout.set_dynamic([])
        if EX_ZONE.contains(self.pose.x, self.pose.y):
            self.ex_zone_steps += 1
        self.bus.publish(Topics.POSE, Pose(self.pose.x, self.pose.y, self.pose.theta))
        for cb in self.on_step:
            cb(self)
        if self.t > MAX_MISSION_S:
            self.timed_out = True
            raise MissionTimeout(f"Превышен лимит симуляции {MAX_MISSION_S:.0f} с")

    def log(self, text: str, level: str = "INFO") -> None:
        self.bus.publish(Topics.LOG, LogMessage(self.t, text, level))


class SimNavigator:
    """Аналог BasicNavigator из nav2_simple_commander."""

    def __init__(self, sim: Sim) -> None:
        self.sim = sim
        self._path: list[tuple[float, float]] = []
        self._goal: Optional[Pose] = None
        self._result = TaskResult.UNKNOWN
        self._started = 0.0
        self._fail_at: Optional[float] = None
        self._active = False

    # --- API как у BasicNavigator ---
    def getPose(self) -> Pose:
        p = self.sim.pose
        return Pose(p.x, p.y, p.theta)

    def goToPose(self, pose: Pose, keepout: bool = True) -> bool:
        """keepout=False — планировать, игнорируя Ex-зону (аналог отключённого keepout-фильтра Nav2)."""
        self._goal = Pose(pose.x, pose.y, pose.theta)
        self._started = self.sim.t
        self._active = True
        self._result = TaskResult.UNKNOWN
        grid = self.sim.grid if keepout else self.sim.grid_no_keepout
        path = grid.plan((self.sim.pose.x, self.sim.pose.y), (pose.x, pose.y))
        if path is None:
            self._path = []
            self._fail_at = self.sim.t + NO_PATH_DELAY_S
            self.sim.log(f"Nav2: нет пути до ({pose.x:.1f}, {pose.y:.1f})", "WARN")
        else:
            self._path = path
            self._fail_at = None
        return True

    def isTaskComplete(self) -> bool:
        if not self._active:
            return True
        self.sim._tick()
        if self._fail_at is not None:
            if self.sim.t >= self._fail_at:
                self._finish(TaskResult.FAILED)
            return not self._active
        self._move(SPEED * DT)
        if not self._path:
            self._finish(TaskResult.SUCCEEDED)
        return not self._active

    def getFeedback(self) -> Optional[NavFeedback]:
        if self._goal is None:
            return None
        return NavFeedback(self.getPose(), self._remaining(), self.sim.t - self._started)

    def getResult(self) -> TaskResult:
        return self._result

    def cancelTask(self) -> None:
        if self._active:
            self._finish(TaskResult.CANCELED)

    # --- внутреннее ---
    def _finish(self, result: TaskResult) -> None:
        self._active = False
        self._result = result
        self._path = []
        self._fail_at = None

    def _remaining(self) -> float:
        d, px, py = 0.0, self.sim.pose.x, self.sim.pose.y
        for x, y in self._path:
            d += math.hypot(x - px, y - py)
            px, py = x, y
        return d

    def _move(self, dist: float) -> None:
        p = self.sim.pose
        while dist > 1e-9 and self._path:
            tx, ty = self._path[0]
            dx, dy = tx - p.x, ty - p.y
            seg = math.hypot(dx, dy)
            if seg <= dist:
                p.x, p.y = tx, ty
                dist -= seg
                self.sim.distance_m += seg
                self._path.pop(0)
            else:
                p.x += dx / seg * dist
                p.y += dy / seg * dist
                self.sim.distance_m += dist
                dist = 0.0
            if seg > 1e-9:
                p.theta = math.atan2(dy, dx)


class SimSensors:
    """Камера + «тепловизор» 8×8 + распознавание метки. Один замер = 4 с."""

    def __init__(self, sim: Sim) -> None:
        self.sim = sim

    def capture(self, checkpoint_id: str) -> CheckpointReading:
        sim = self.sim
        cp = sim.world.checkpoint(checkpoint_id)
        sim.advance(CAPTURE_TIME_S)
        if math.hypot(sim.pose.x - cp.x, sim.pose.y - cp.y) > CAPTURE_RADIUS:
            r = CheckpointReading(cp.id, sim.t, None, None, None, failure="too_far")
            sim.bus.publish(Topics.READING, r)
            return r
        sim.captures += 1
        sim.captures_at[cp.id] = sim.captures_at.get(cp.id, 0) + 1
        rng = sim.rng
        # манометр
        if rng.random() < P_BLUR:
            gauge = None
        else:
            gauge = sim.truth.gauge_true[cp.id] + rng.normal(0, GAUGE_SIGMA)
            if rng.random() < P_OUTLIER:
                gauge += rng.choice([-1, 1]) * rng.uniform(0.8, 1.6)
            gauge = round(float(max(0.0, gauge)), 3)
        # тепловизор
        thermal = sim._body[cp.id] + rng.uniform(-1.5, 1.5, size=(8, 8))
        p_glare = P_GLARE_HOT if cp.id == sim.truth.glare_cp else P_GLARE_ANY
        if rng.random() < p_glare:
            i, j = int(rng.integers(0, 8)), int(rng.integers(0, 8))
            thermal[i, j] = rng.uniform(100, 125)
        thermal = np.round(thermal, 1)
        tag = None if rng.random() < P_TAG_MISS else cp.tag_id
        r = CheckpointReading(cp.id, sim.t, gauge, thermal, tag)
        sim.bus.publish(Topics.READING, r)
        return r


class SimOperator:
    """Ручная проверка оператором: данные точные, но это ручное вмешательство (портит KPI)."""

    def __init__(self, sim: Sim) -> None:
        self.sim = sim

    def manual_reading(self, checkpoint_id: str) -> CheckpointReading:
        sim = self.sim
        cp = sim.world.checkpoint(checkpoint_id)
        sim.advance(OPERATOR_TIME_S)
        sim.manual_interventions += 1
        sim.log(f"Оператор вручную проверил {cp.id}", "WARN")
        r = CheckpointReading(cp.id, sim.t, sim.truth.gauge_true[cp.id], np.round(sim._body[cp.id].copy(), 1),
                              cp.tag_id, source="operator")
        sim.bus.publish(Topics.READING, r)
        return r
