"""Сообщения симулятора — аналоги ROS 2 msg.

В ROS 2 это были бы .msg-файлы в пакете ngk_interfaces.
Здесь — обычные dataclass, чтобы всё работало без ROS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class Topics:
    """Имена топиков. Совпадают с ROS-версией из домашнего задания."""

    POSE = "/robot/pose"                # Pose, каждый шаг симуляции
    READING = "/sensors/reading"        # CheckpointReading, каждый замер
    RESULT = "/inspection/result"       # InspectionResult, итог по точке
    ALARM = "/alarm"                    # Alarm, тревога оператору
    STATUS = "/mission/status"          # MissionStatus, по желанию
    LOG = "/rosout"                     # LogMessage, текстовый лог


class Status:
    """Статус точки контроля в отчёте."""

    OK = "OK"
    ANOMALY = "ANOMALY"
    UNKNOWN = "UNKNOWN"   # робот честно говорит «не смог проверить»
    MISSING = "MISSING"   # результата нет вовсе (используется только в отчёте)

    ALL = (OK, ANOMALY, UNKNOWN, MISSING)


class TaskResult(Enum):
    """Как nav2_simple_commander.robot_navigator.TaskResult."""

    UNKNOWN = 0
    SUCCEEDED = 1
    CANCELED = 2
    FAILED = 3


@dataclass
class Pose:
    x: float
    y: float
    theta: float = 0.0


@dataclass
class NavFeedback:
    """Как feedback у action NavigateToPose."""

    current_pose: Pose
    distance_remaining: float
    navigation_time_s: float


@dataclass
class CheckpointReading:
    """Сырые данные одного замера на точке контроля."""

    checkpoint_id: str
    stamp: float
    gauge_bar: Optional[float]           # None — кадр смазан, стрелку не видно
    thermal: Optional[np.ndarray]        # матрица 8×8, °C; None — замер не удался
    tag_id: Optional[int] = None         # ID метки на оборудовании, None — не распознана
    source: str = "robot"                # "robot" или "operator"
    failure: Optional[str] = None        # причина неудачи, например "too_far"


@dataclass
class InspectionResult:
    """Итог инспекции точки — то, что идёт в отчёт."""

    checkpoint_id: str
    stamp: float
    status: str                          # Status.OK / ANOMALY / UNKNOWN
    gauge_bar: Optional[float] = None
    max_temp_c: Optional[float] = None
    reason: str = ""                     # например "overheat" или "unreachable"


@dataclass
class Alarm:
    """Тревога оператору."""

    checkpoint_id: str
    stamp: float
    kind: str                            # "overheat" | "overpressure" | "underpressure" | ...
    message: str = ""


@dataclass
class MissionStatus:
    stamp: float
    state: str                           # произвольная строка: "start", "goal K1", "done"…
    detail: str = ""


@dataclass
class LogMessage:
    stamp: float
    text: str
    level: str = "INFO"


@dataclass
class MissionRecord:
    """Всё, что записала миссия. Передаётся в build_report()."""

    seed: int
    team: str
    checkpoints: list                    # список CheckpointSpec (паспорт объекта)
    results: list = field(default_factory=list)   # все InspectionResult в порядке публикации
    alarms: list = field(default_factory=list)    # все Alarm в порядке публикации
    started_s: float = 0.0
    finished_s: float = 0.0
    crashed: bool = False

    def last_results(self) -> dict:
        """Последний опубликованный результат по каждой точке: {id: InspectionResult}."""
        out = {}
        for r in self.results:
            out[r.checkpoint_id] = r
        return out
