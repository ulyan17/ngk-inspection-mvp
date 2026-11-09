"""Мини-шина «публикация–подписка» — замена топиков ROS 2.

    bus.subscribe("/alarm", callback)   # ~ node.create_subscription(...)
    bus.publish("/alarm", Alarm(...))   # ~ publisher.publish(msg)

Все сообщения пишутся в журнал: это наш аналог rosbag2.
"""
from __future__ import annotations

import dataclasses
import json
from collections import defaultdict
from enum import Enum
from typing import Any, Callable

import numpy as np


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Any], None]]] = defaultdict(list)
        self.journal: list[tuple[str, Any]] = []
        self.record_pose = True   # позы публикуются часто; в журнал пишем каждую

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        self._subs[topic].append(callback)

    def publish(self, topic: str, msg: Any) -> None:
        self.journal.append((topic, msg))
        for cb in list(self._subs[topic]):
            cb(msg)

    def messages(self, topic: str) -> list:
        return [m for t, m in self.journal if t == topic]

    def dump_jsonl(self, path: str) -> None:
        """Сохранить журнал как JSON Lines (аналог `ros2 bag record -a`)."""
        with open(path, "w", encoding="utf-8") as f:
            for topic, msg in self.journal:
                f.write(json.dumps({"topic": topic, "msg": to_jsonable(msg)}, ensure_ascii=False) + "\n")


def to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, np.ndarray):
        return np.round(obj, 2).tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 4)
    return obj
