"""Визуализация: живая анимация миссии и итоговая карта (matplotlib).

Если окно не открывается — запускайте с --no-viz и смотрите out/seed_N/map.png.
"""
from __future__ import annotations

import matplotlib

from .messages import Status, Topics
from .world import BLOCKAGE, EX_ZONE, OBSTACLES, CHECKPOINTS, DOCK, HEIGHT_M, WIDTH_M

COL = {"bg": "#0E1116", "obst": "#3A4250", "ex": "#FF6B1A", "cp": "#3DD6D0", "route": "#3DD6D0",
       "ok": "#3DD6D0", "anom": "#FF6B1A", "unk": "#9AA4B2", "text": "#EDEAE3"}
STATUS_COL = {Status.OK: "#2FBF71", Status.ANOMALY: "#FF6B1A", Status.UNKNOWN: "#9AA4B2"}


def _draw_static(ax, show_blockage=True):
    import matplotlib.patches as mp
    ax.set_facecolor(COL["bg"])
    ax.set_xlim(0, WIDTH_M)
    ax.set_ylim(0, HEIGHT_M)
    ax.set_aspect("equal")
    ax.set_xticks(range(0, 41, 5))
    ax.set_yticks(range(0, 31, 5))
    ax.tick_params(colors="#9AA4B2", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#2A313C")
    ax.grid(color="#1A2029", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.add_patch(mp.Rectangle((EX_ZONE.x0, EX_ZONE.y0), EX_ZONE.x1 - EX_ZONE.x0, EX_ZONE.y1 - EX_ZONE.y0,
                              facecolor="#FF6B1A22", edgecolor=COL["ex"], hatch="//", linewidth=1.5))
    ax.text(EX_ZONE.x0 + 0.3, EX_ZONE.y1 - 1.0, "Ex-зона", color=COL["ex"], fontsize=9, weight="bold")
    for r in OBSTACLES:
        ax.add_patch(mp.Rectangle((r.x0, r.y0), r.x1 - r.x0, r.y1 - r.y0, facecolor=COL["obst"], edgecolor="none"))
        if not r.name.startswith("Стена"):
            ax.text((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, r.name.replace(" ", "\n", 1), color="#9AA4B2",
                    fontsize=7, ha="center", va="center")
    blk = None
    if show_blockage:
        blk = mp.Rectangle((BLOCKAGE.x0, BLOCKAGE.y0), BLOCKAGE.x1 - BLOCKAGE.x0, BLOCKAGE.y1 - BLOCKAGE.y0,
                           facecolor="#FF6B1A", edgecolor="none", alpha=0.9)
        ax.add_patch(blk)
    ax.add_patch(mp.Rectangle((DOCK.x - 1, DOCK.y - 1), 2, 2, facecolor="#F2EFE8", edgecolor="none"))
    ax.text(DOCK.x - 1, DOCK.y + 1.3, "DOCK", color="#F2EFE8", fontsize=8)
    cp_dots = {}
    for cp in CHECKPOINTS:
        (dot,) = ax.plot(cp.x, cp.y, "o", ms=11, color=COL["cp"], mec=COL["bg"], mew=2)
        ax.text(cp.x + 0.6, cp.y + 0.6, cp.id, color=COL["text"], fontsize=9, weight="bold")
        cp_dots[cp.id] = dot
    return cp_dots, blk


class LiveViz:
    """Окно с анимацией: карта слева, последний кадр тепловизора справа."""

    def __init__(self, sim, bus, every: int = 2, title: str = ""):
        import matplotlib.pyplot as plt
        self.plt = plt
        self.sim = sim
        self.every = max(1, every)
        self.n = 0
        plt.ion()
        self.fig, (self.ax, self.axt) = plt.subplots(1, 2, figsize=(13, 6.2), gridspec_kw={"width_ratios": [3, 1.2]})
        self.fig.patch.set_facecolor(COL["bg"])
        self.cp_dots, self.blk = _draw_static(self.ax, sim.blockage_active)
        (self.trail,) = self.ax.plot([], [], "-", color=COL["route"], lw=1.5, alpha=0.7)
        (self.robot,) = self.ax.plot([], [], "^", ms=13, color="#F7F4EE", mec="#FF6B1A", mew=2)
        self.xs, self.ys = [], []
        self.title = self.ax.set_title(title, color=COL["text"], fontsize=11, loc="left")
        self.axt.set_facecolor(COL["bg"])
        self.axt.set_title("Тепловизор 8×8, °C", color=COL["text"], fontsize=10)
        self.img = self.axt.imshow([[20] * 8] * 8, cmap="inferno", vmin=15, vmax=100)
        self.axt.set_xticks([])
        self.axt.set_yticks([])
        self.tinfo = self.axt.text(0, 9.3, "", color=COL["text"], fontsize=9, va="top")
        cb = self.fig.colorbar(self.img, ax=self.axt, fraction=0.046)
        cb.ax.tick_params(colors="#9AA4B2", labelsize=8)
        sim.on_step.append(self._on_step)
        bus.subscribe(Topics.READING, self._on_reading)
        bus.subscribe(Topics.RESULT, self._on_result)
        self.plt.show(block=False)

    def _on_step(self, sim):
        self.xs.append(sim.pose.x)
        self.ys.append(sim.pose.y)
        if self.blk is not None and not sim.blockage_active:
            self.blk.remove()
            self.blk = None
        self.n += 1
        if self.n % self.every == 0:
            self._refresh()

    def _refresh(self):
        self.trail.set_data(self.xs, self.ys)
        self.robot.set_data([self.sim.pose.x], [self.sim.pose.y])
        self.title.set_text(f"t = {self.sim.t:6.1f} с   путь = {self.sim.distance_m:5.1f} м")
        try:
            self.fig.canvas.draw_idle()
            self.plt.pause(0.001)
        except Exception:
            pass

    def _on_reading(self, r):
        if r.thermal is not None:
            self.img.set_data(r.thermal)
            g = "—" if r.gauge_bar is None else f"{r.gauge_bar:.2f} бар"
            self.tinfo.set_text(f"{r.checkpoint_id}: max {r.thermal.max():.0f} °C\nманометр: {g}")
            self._refresh()

    def _on_result(self, res):
        dot = self.cp_dots.get(res.checkpoint_id)
        if dot is not None:
            dot.set_color(STATUS_COL.get(res.status, COL["cp"]))
            self._refresh()

    def close(self, wait: bool = True):
        self._refresh()
        if wait:
            try:
                self.plt.ioff()
                self.plt.show()
            except Exception:
                pass


def save_map(path: str, sim, bus, last_results: dict, title: str) -> None:
    """Итоговая карта миссии в PNG (работает и без экрана)."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 7.5))
    fig.patch.set_facecolor(COL["bg"])
    import matplotlib.patches as mp
    dots, _ = _draw_static(ax, show_blockage=False)
    if sim.truth.blockage_until_s > 0:
        b = BLOCKAGE
        ax.add_patch(mp.Rectangle((b.x0, b.y0), b.x1 - b.x0, b.y1 - b.y0, facecolor="none", edgecolor="#FF6B1A",
                                  linestyle="--", linewidth=1.5))
        ax.text(b.x0, b.y0 - 0.9, f"техника до t={sim.truth.blockage_until_s:.0f} с", color="#FF6B1A", fontsize=7)
    poses = bus.messages(Topics.POSE)
    ax.plot([p.x for p in poses], [p.y for p in poses], "-", color=COL["route"], lw=1.6, alpha=0.8)
    bad = [p for p in poses if EX_ZONE.contains(p.x, p.y)]
    if bad:   # заезды в Ex-зону — красным, их должно быть видно издалека
        ax.plot([p.x for p in bad], [p.y for p in bad], "o", ms=7, color="#FF3B30", mec="#F7F4EE", mew=1)
        ax.text(EX_ZONE.x0 + 0.3, EX_ZONE.y0 + 0.6, f"ЗАЕЗД В Ex-ЗОНУ · {len(bad)} шагов", color="#FF3B30", fontsize=10,
                weight="bold", bbox=dict(boxstyle="round,pad=0.3", fc="#0E1116", ec="#FF3B30"))
    for cid, dot in dots.items():
        r = last_results.get(cid)
        dot.set_color(STATUS_COL.get(r.status, "#5B6472") if r else "#5B6472")
    ax.set_title(title, color=COL["text"], fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)


def use_headless() -> None:
    matplotlib.use("Agg")
