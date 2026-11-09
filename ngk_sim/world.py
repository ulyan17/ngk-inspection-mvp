"""Мир «упрощённая насосная станция» 40×30 м.

Координаты в метрах, ось x вправо, ось y вверх, начало — юго-западный угол.
Публичная часть (паспорт объекта) — WorldInfo: её видит код студентов.
Истина (где аномалия, настоящие показания) — Truth: её видит только оценка KPI.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .messages import Pose

WIDTH_M = 40.0
HEIGHT_M = 30.0


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float
    name: str = ""

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (self.x0 - margin) <= x <= (self.x1 + margin) and (self.y0 - margin) <= y <= (self.y1 + margin)


# Оборудование и стены (непроходимо)
OBSTACLES = [
    Rect(10, 4, 14, 8, "Насос Н-1"),
    Rect(10, 16, 14, 20, "Насос Н-2"),
    Rect(18, 11, 32, 13, "Эстакада трубопроводов"),
    Rect(26, 18, 34, 26, "РВС-1"),
    Rect(2, 22, 8, 28, "Операторная"),
    Rect(17, 22, 21, 26, "Дренажная ёмкость ДЕ-1"),
    Rect(18, 2, 30, 3, "Стена тупика (юг)"),
    Rect(18, 7, 30, 8, "Стена тупика (север)"),
    Rect(30, 2, 31, 8, "Стена тупика (торец)"),
]

# Взрывоопасная зона: проходить можно физически, но запрещено — планировщик обходит её как keepout
EX_ZONE = Rect(15, 20, 23, 28, "Ex-зона вокруг ДЕ-1")

# Временное препятствие: техника на въезде в тупик с K2
BLOCKAGE = Rect(18.4, 3.2, 19.6, 6.8, "Техника на проезде")

DOCK = Pose(3.0, 3.0, 0.0)


@dataclass(frozen=True)
class CheckpointSpec:
    """Паспорт точки контроля — то, что знает оператор (и код студентов)."""

    id: str
    name: str
    x: float
    y: float
    p_min: float           # допустимое давление, бар
    p_max: float
    temp_limit_c: float    # предел температуры, °C
    tag_id: int            # ID метки на оборудовании

    @property
    def pose(self) -> Pose:
        return Pose(self.x, self.y, 0.0)


CHECKPOINTS = [
    CheckpointSpec("K1", "Н-1, нагнетание", 15.0, 6.0, 4.0, 6.0, 70.0, 11),
    CheckpointSpec("K2", "Узел учёта (тупик)", 28.0, 5.0, 2.5, 3.5, 60.0, 12),
    CheckpointSpec("K3", "Н-2, нагнетание", 15.0, 18.0, 4.0, 6.0, 70.0, 13),
    CheckpointSpec("K4", "Задвижка З-3 на эстакаде", 25.0, 10.0, 1.5, 2.5, 60.0, 14),
    CheckpointSpec("K5", "РВС-1, узел налива", 24.5, 22.0, 0.8, 1.6, 55.0, 15),
    CheckpointSpec("K6", "ДЕ-1, дренажная ёмкость", 19.0, 19.0, 0.5, 1.2, 55.0, 16),
]


@dataclass
class Truth:
    """Истина мира для данного seed. Студентам не показывается."""

    seed: int
    anomaly_cp: str
    anomaly_kind: str                       # "overheat" | "overpressure" | "underpressure"
    gauge_true: dict                        # {cp_id: давление, бар}
    hot_patch: Optional[tuple] = None       # (cp_id, row, col, size, temp) для перегрева
    glare_cp: str = ""                      # точка, где часто бывают блики
    blockage_until_s: float = 0.0           # до какого времени техника перекрывает тупик (0 — не перекрывает)


@dataclass
class WorldInfo:
    """Публичный паспорт объекта."""

    checkpoints: list = field(default_factory=lambda: list(CHECKPOINTS))
    dock_pose: Pose = field(default_factory=lambda: Pose(DOCK.x, DOCK.y, 0.0))
    obstacles: list = field(default_factory=lambda: list(OBSTACLES))
    ex_zone: Rect = EX_ZONE
    width_m: float = WIDTH_M
    height_m: float = HEIGHT_M

    def checkpoint(self, cp_id: str) -> CheckpointSpec:
        for cp in self.checkpoints:
            if cp.id == cp_id:
                return cp
        raise KeyError(f"Нет точки контроля {cp_id!r}")


def make_truth(seed: int, blockage_until: Optional[float] = None) -> Truth:
    """Сгенерировать истину мира по seed. Одинаковый seed — одинаковый мир."""
    rng = random.Random(seed * 7919 + 13)
    gauge = {}
    for cp in CHECKPOINTS:
        mid = (cp.p_min + cp.p_max) / 2
        half = (cp.p_max - cp.p_min) / 2
        gauge[cp.id] = round(mid + rng.uniform(-0.45, 0.45) * half, 3)

    anomaly_cp = rng.choice([cp.id for cp in CHECKPOINTS])
    kind = rng.choice(["overheat", "overheat", "overpressure", "underpressure"])
    spec = next(c for c in CHECKPOINTS if c.id == anomaly_cp)
    hot_patch = None
    if kind == "overheat":
        size = rng.choice([2, 2, 3])
        hot_patch = (anomaly_cp, rng.randint(1, 8 - size - 1), rng.randint(1, 8 - size - 1), size,
                     spec.temp_limit_c + rng.uniform(12, 25))
    elif kind == "overpressure":
        gauge[anomaly_cp] = round(spec.p_max + rng.uniform(0.6, 1.2), 3)
    else:
        gauge[anomaly_cp] = round(max(0.05, spec.p_min - rng.uniform(0.4, 0.8)), 3)

    glare_cp = rng.choice([cp.id for cp in CHECKPOINTS if cp.id != anomaly_cp])

    if blockage_until is None:
        blockage_until = rng.uniform(45, 120) if rng.random() < 0.85 else 0.0

    return Truth(seed=seed, anomaly_cp=anomaly_cp, anomaly_kind=kind, gauge_true=gauge,
                 hot_patch=hot_patch, glare_cp=glare_cp, blockage_until_s=blockage_until)
