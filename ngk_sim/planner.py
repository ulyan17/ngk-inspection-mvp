"""Планировщик пути A* на сетке — упрощённый аналог глобального планировщика Nav2.

Ex-зона помечается непроходимой, как маска keepout-фильтра Nav2
(nav2_costmap_2d::KeepoutFilter). Препятствия «раздуваются» на радиус робота,
как inflation layer в costmap.
"""
from __future__ import annotations

import heapq
import math
from typing import Iterable, Optional

import numpy as np

from .world import HEIGHT_M, WIDTH_M, Rect

RESOLUTION = 0.5       # м на клетку
ROBOT_RADIUS = 0.5     # м, радиус «раздувания» препятствий


class GridMap:
    def __init__(self, obstacles: Iterable[Rect], keepout: Iterable[Rect] = ()) -> None:
        self.res = RESOLUTION
        self.nx = int(round(WIDTH_M / self.res))
        self.ny = int(round(HEIGHT_M / self.res))
        self.static = np.zeros((self.nx, self.ny), dtype=bool)
        self._mark(obstacles, ROBOT_RADIUS)
        self._mark(keepout, ROBOT_RADIUS)
        # забор по периметру
        self.static[0, :] = self.static[-1, :] = True
        self.static[:, 0] = self.static[:, -1] = True
        self.dynamic = np.zeros_like(self.static)

    def _mark(self, rects: Iterable[Rect], margin: float, target: Optional[np.ndarray] = None) -> None:
        grid = self.static if target is None else target
        for r in rects:
            for i in range(self.nx):
                x = (i + 0.5) * self.res
                if not (r.x0 - margin <= x <= r.x1 + margin):
                    continue
                for j in range(self.ny):
                    y = (j + 0.5) * self.res
                    if r.y0 - margin <= y <= r.y1 + margin:
                        grid[i, j] = True

    def set_dynamic(self, rects: Iterable[Rect]) -> None:
        self.dynamic[:] = False
        self._mark(rects, ROBOT_RADIUS, self.dynamic)

    def blocked(self, i: int, j: int) -> bool:
        if not (0 <= i < self.nx and 0 <= j < self.ny):
            return True
        return bool(self.static[i, j] or self.dynamic[i, j])

    def cell(self, x: float, y: float) -> tuple[int, int]:
        return (min(self.nx - 1, max(0, int(x / self.res))), min(self.ny - 1, max(0, int(y / self.res))))

    def center(self, i: int, j: int) -> tuple[float, float]:
        return ((i + 0.5) * self.res, (j + 0.5) * self.res)

    def plan(self, start: tuple[float, float], goal: tuple[float, float]) -> Optional[list[tuple[float, float]]]:
        """Путь из точек (м) от start до goal или None, если пути нет."""
        s = self.cell(*start)
        g = self.cell(*goal)
        if self.blocked(*g):
            return None
        # старт может оказаться в «раздутой» зоне — разрешаем выйти из неё
        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]
        openq = [(0.0, 0.0, s)]
        came = {s: None}
        cost = {s: 0.0}
        while openq:
            _, c, cur = heapq.heappop(openq)
            if cur == g:
                break
            if c > cost.get(cur, math.inf):
                continue
            for di, dj, w in moves:
                nb = (cur[0] + di, cur[1] + dj)
                if self.blocked(*nb) and nb != g:
                    continue
                if di and dj and (self.blocked(cur[0] + di, cur[1]) or self.blocked(cur[0], cur[1] + dj)):
                    continue  # не срезаем углы
                nc = c + w
                if nc < cost.get(nb, math.inf):
                    cost[nb] = nc
                    came[nb] = cur
                    h = math.hypot(g[0] - nb[0], g[1] - nb[1])
                    heapq.heappush(openq, (nc + h, nc, nb))
        if g not in came:
            return None
        cells = []
        cur = g
        while cur is not None:
            cells.append(cur)
            cur = came[cur]
        cells.reverse()
        pts = [self.center(i, j) for i, j in cells[1:-1]]
        return pts + [goal]
