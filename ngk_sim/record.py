"""Запись миссии в видео (MP4 или GIF) — по журналу топиков, без окна.

    python -m ngk_sim record --seed 19 --out mission.mp4
    python -m ngk_sim record --seed 19 --impl solutions --out good.mp4

Пригодится как запасной вариант на занятии, если у кого-то не открывается окно.
"""
from __future__ import annotations

import shutil

from .messages import Status, Topics
from .viz import COL, STATUS_COL, use_headless
from .world import BLOCKAGE, CHECKPOINTS


def record(seed: int, out: str, impl: str = "student", fps: int = 20, step: int = 2, hold_s: float = 3.0) -> str:
    use_headless()
    import matplotlib.pyplot as plt
    import matplotlib.patches as mp
    from matplotlib.animation import FFMpegWriter, PillowWriter

    from .runner import run_episode
    from .viz import _draw_static

    res = run_episode(seed, impl=impl, write=False, verbose=False)
    bus, kpi, gate, truth = res["bus"], res["kpi"], res["gate"], res["truth"]

    # ---- раскладываем журнал на кадры ----
    frames = []      # (t, x, y, trail_len, thermal, info, statuses, log, blockage)
    t, n_pose = 0.0, 0
    xs, ys = [], []
    thermal, info, log = None, "", ""
    statuses = {}
    for topic, msg in bus.journal:
        if topic == Topics.POSE:
            t += 0.5
            n_pose += 1
            xs.append(msg.x)
            ys.append(msg.y)
            if n_pose % step == 0:
                frames.append((t, msg.x, msg.y, len(xs), thermal, info, dict(statuses), log,
                               t < truth.blockage_until_s))
        elif topic == Topics.READING and msg.thermal is not None:
            thermal = msg.thermal
            g = "—" if msg.gauge_bar is None else f"{msg.gauge_bar:.2f} бар"
            info = f"{msg.checkpoint_id}: max {msg.thermal.max():.0f} °C · манометр {g}"
        elif topic == Topics.RESULT:
            statuses[msg.checkpoint_id] = msg.status
        elif topic == Topics.LOG:
            log = msg.text
    if not frames:
        raise RuntimeError("Миссия не сделала ни одного шага")
    last = frames[-1]
    frames += [last] * int(hold_s * fps)

    # ---- фигура ----
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor(COL["bg"])
    ax = fig.add_axes([0.04, 0.08, 0.62, 0.82])
    axt = fig.add_axes([0.70, 0.46, 0.27, 0.40])
    dots, _ = _draw_static(ax, show_blockage=False)
    blk = mp.Rectangle((BLOCKAGE.x0, BLOCKAGE.y0), BLOCKAGE.x1 - BLOCKAGE.x0, BLOCKAGE.y1 - BLOCKAGE.y0,
                       facecolor="#FF6B1A", edgecolor="none", alpha=0.9)
    ax.add_patch(blk)
    (trail,) = ax.plot([], [], "-", color=COL["route"], lw=1.8, alpha=0.8)
    (robot,) = ax.plot([], [], "^", ms=14, color="#F7F4EE", mec="#FF6B1A", mew=2)
    (exdots,) = ax.plot([], [], "o", ms=7, color="#FF3B30", mec="#F7F4EE", mew=1)
    from .world import EX_ZONE
    team = kpi["team"]
    fig.text(0.04, 0.95, f"ngk_sim · {team} · seed {seed}", color=COL["text"], fontsize=15, weight="bold")
    tclock = fig.text(0.04, 0.915, "", color="#9AA4B2", fontsize=11, family="monospace")
    axt.set_facecolor(COL["bg"])
    axt.set_title("Тепловизор 8×8, °C", color=COL["text"], fontsize=11)
    img = axt.imshow([[20] * 8] * 8, cmap="inferno", vmin=15, vmax=100)
    axt.set_xticks([])
    axt.set_yticks([])
    tinfo = fig.text(0.70, 0.415, "", color=COL["text"], fontsize=10.5, family="monospace")
    tstat = fig.text(0.70, 0.08, "", color=COL["text"], fontsize=11, family="monospace", va="bottom", linespacing=1.6)
    tlog = fig.text(0.04, 0.025, "", color="#9AA4B2", fontsize=10.5, family="monospace")
    banner = fig.text(0.35, 0.50, "", color="#0E1116", fontsize=26, weight="bold", ha="center", va="center",
                      bbox=dict(boxstyle="round,pad=0.6", fc="#FF6B1A", ec="none"), visible=False)

    all_x, all_y = xs, ys
    names = {cp.id: cp.name for cp in CHECKPOINTS}
    n_real = len(frames) - int(hold_s * fps)

    def draw(i):
        t, x, y, n, th, inf, st, lg, blocked = frames[i]
        trail.set_data(all_x[:n], all_y[:n])
        bx = [(a, b) for a, b in zip(all_x[:n], all_y[:n]) if EX_ZONE.contains(a, b)]
        exdots.set_data([a for a, _ in bx], [b for _, b in bx])
        robot.set_data([x], [y])
        blk.set_visible(blocked)
        tclock.set_text(f"t = {t:6.1f} с")
        if th is not None:
            img.set_data(th)
        tinfo.set_text(inf)
        lines = []
        final = i >= n_real
        for cid, dot in dots.items():
            s = st.get(cid) or (Status.MISSING if final else None)
            dot.set_color(STATUS_COL.get(s, "#5B6472") if s else "#3DD6D0")
            lines.append(f"{cid} {(s or '…'):<8} {names[cid][:18]}")
        tstat.set_text("\n".join(lines))
        tlog.set_text(lg[:110])
        if i >= n_real:
            ok = gate["must_ok"]
            banner.set_text(("GO-КАНДИДАТ" if ok else "NO-GO") +
                            f"\nпокрытие {kpi['checkpoints_covered']}/{kpi['checkpoints_total']} · ложных тревог {kpi['false_alarms']}")
            banner.get_bbox_patch().set_facecolor("#3DD6D0" if ok else "#FF6B1A")
            banner.set_visible(True)
        return []

    if out.lower().endswith(".gif"):
        writer = PillowWriter(fps=fps)
    else:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("Для MP4 нужен ffmpeg. Установите его или сохраните в .gif")
        writer = FFMpegWriter(fps=fps, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23"])
    with writer.saving(fig, out, dpi=100):
        for i in range(len(frames)):
            draw(i)
            writer.grab_frame(facecolor=fig.get_facecolor())
    plt.close(fig)
    return out
