"""Сравнение четырёх подрядчиков на одних и тех же сценариях.

    python -m ngk_sim compare                    # 5 сценариев приёмки (seed 101–105)
    python -m ngk_sim compare --runs 30          # проверка надёжности на 30 сценариях

Пишет out/compare/compare.md, compare.png, карты по каждому варианту и копирует сводку в submission/.
"""
from __future__ import annotations

import os
import shutil
import statistics

from .evaluate import LABELS, fmt, load_thresholds
from .runner import run_episode

ACCEPT_SEEDS = [101, 102, 103, 104, 105]


def compare(seeds: list[int] | None = None, runs: int | None = None, out_dir: str = "out/compare",
            to_submission: bool = True, letters: list[str] | None = None) -> dict:
    from variants import NAMES, VARIANTS
    from .viz import save_map, use_headless
    use_headless()
    if runs:
        seeds = list(range(1000, 1000 + runs))
    seeds = seeds or ACCEPT_SEEDS
    letters = letters or list(VARIANTS)
    thr = load_thresholds()
    keys = list(thr["must"]) + list(thr["should"])
    os.makedirs(out_dir, exist_ok=True)

    results = {}
    for L in letters:
        print(f"▶ {NAMES[L]}: {len(seeds)} сценариев")
        rows = []
        for i, s in enumerate(seeds):
            r = run_episode(s, impl=VARIANTS[L], write=False, verbose=False)
            rows.append(r)
            if i < 5:   # карты для первых сценариев — это доказательства для протокола
                d = os.path.join(out_dir, "maps", L)
                os.makedirs(d, exist_ok=True)
                k = r["kpi"]
                save_map(os.path.join(d, f"seed_{s}.png"), r["sim"], r["bus"], r["record"].last_results(),
                         f"{NAMES[L]} · seed {s} · покрытие {k['checkpoints_covered']}/6 · ложных тревог {k['false_alarms']}")
        results[L] = rows

    # ---- сводка: доля прогонов, где критерий выполнен ----
    def ok_rate(L, key):
        rows = results[L]
        return sum(1 for r in rows if next(x for x in r["gate"]["rows"] if x["key"] == key)["ok"]) / len(rows)

    def mean_val(L, key):
        vals = [r["kpi"][key] for r in results[L]]
        if isinstance(vals[0], bool):
            return f"{sum(vals)}/{len(vals)}"
        return fmt(round(statistics.mean(vals), 2))

    must_rate = {L: sum(r["gate"]["must_ok"] for r in results[L]) / len(seeds) for L in letters}
    head = "| Критерий | Тип | Порог | " + " | ".join(NAMES[L] for L in letters) + " |"
    sep = "|---|---|---|" + "---|" * len(letters)
    lines = ["# Сравнение подрядчиков", "",
             f"Сценарии (seed): {seeds[0]}…{seeds[-1]} ({len(seeds)} шт.). KPI посчитаны симулятором по эталонным данным.", "",
             "## 1. Доля прогонов, где критерий выполнен", "", head, sep]
    for key in keys:
        g = "must" if key in thr["must"] else "should"
        rule = thr[g][key]
        cells = []
        for L in letters:
            rr = ok_rate(L, key)
            cells.append(f"{rr:.0%} {'✅' if rr == 1 else ('⚠️' if rr >= 0.9 else '❌')}")
        lines.append(f"| {LABELS.get(key, key)} | {'обяз.' if g == 'must' else 'желат.'} | {rule['op']} {fmt(rule['value'])} | " + " | ".join(cells) + " |")
    lines.append("| **Все обязательные сразу** | | | " + " | ".join(f"**{must_rate[L]:.0%}**" for L in letters) + " |")
    lines += ["", "## 2. Средние значения KPI", "", head.replace("| Тип | Порог ", ""), "|---|" + "---|" * len(letters)]
    for key in keys + ["distance_m", "measurements"]:
        label = {"distance_m": "Путь, м", "measurements": "Замеров датчиками"}.get(key, LABELS.get(key, key))
        lines.append(f"| {label} | " + " | ".join(mean_val(L, key) for L in letters) + " |")
    lines += ["", "## 3. По каждому сценарию", ""]
    for L in letters:
        lines += [f"### {NAMES[L]}", "", "| seed | покрытие | аномалия | ложные тревоги | ручные вмеш. | Ex-зона, шагов | точность | время, с | обязательные |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s, r in zip(seeds, results[L]):
            k = r["kpi"]
            lines.append(f"| {s} | {fmt(k['coverage'])} | {fmt(k['anomaly_detected'])} | {k['false_alarms']} | {k['manual_interventions']} | "
                         f"{k['ex_zone_violations']} | {fmt(k['reading_accuracy'])} | {fmt(k['mission_time_s'])} | {'✅' if r['gate']['must_ok'] else '❌'} |")
        lines.append("")
    lines += ["Карты первых сценариев: `out/compare/maps/<A|B|C|D>/seed_N.png`. Подробности одного прогона: "
              "`python -m ngk_sim run --variant A --seed N` → `out/seed_N/`.", ""]
    md = "\n".join(lines)
    md_path = os.path.join(out_dir, "compare.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    png_path = os.path.join(out_dir, "compare.png")
    _chart(png_path, letters, NAMES, keys, thr, ok_rate, must_rate, seeds)

    print("\n" + "\n".join(lines[4:6 + len(keys) + 2]))
    print(f"\n📄 {md_path}\n🖼  {png_path}")
    if to_submission and os.path.isdir("submission"):
        suffix = "" if not runs else f"_{len(seeds)}"
        shutil.copy(md_path, os.path.join("submission", f"compare{suffix}.md"))
        shutil.copy(png_path, os.path.join("submission", f"compare{suffix}.png"))
        print(f"📄 Копия для сдачи: submission/compare{suffix}.md и .png")
    return {"results": results, "md": md_path, "png": png_path, "must_rate": must_rate}


def _chart(path, letters, names, keys, thr, ok_rate, must_rate, seeds):
    import matplotlib.pyplot as plt
    import numpy as np
    BG, TXT, MUT, OR = "#0E1116", "#EDEAE3", "#9AA4B2", "#FF6B1A"
    cols = keys + ["__all__"]
    data = np.array([[must_rate[L] if k == "__all__" else ok_rate(L, k) for k in cols] for L in letters])
    fig, ax = plt.subplots(figsize=(15, 1.2 + 0.9 * len(letters)), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    # один оттенок: светлее = меньше прогонов прошло
    cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list("pass", ["#2A1B12", "#7A3A16", "#3DD6D0"])
    ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(len(letters)):
        for j in range(len(cols)):
            v = data[i, j]
            ax.text(j, i, f"{v:.0%}", ha="center", va="center", color="#0E1116" if v > 0.75 else TXT,
                    fontsize=13, weight="bold")
    short = {"ex_zone_violations": "Ex-зона", "coverage": "Покрытие", "anomaly_detected": "Аномалия",
             "false_alarms": "Ложные\nтревоги", "manual_interventions": "Ручные\nвмешательства", "crashed": "Без сбоев",
             "reading_accuracy": "Точность\n(желат.)", "mission_time_s": "Время\n(желат.)", "__all__": "ВСЕ\nобязательные"}
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([short.get(k, k) for k in cols], color=TXT, fontsize=11)
    ax.set_yticks(range(len(letters)))
    ax.set_yticklabels([names[L] for L in letters], color=TXT, fontsize=12)
    ax.tick_params(length=0)
    ax.xaxis.tick_top()
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(cols)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(letters)), minor=True)
    ax.grid(which="minor", color=BG, linewidth=3)
    ax.axvline(len(cols) - 1.5, color=OR, lw=2)
    fig.text(0.01, 0.02, f"Доля прогонов, где критерий выполнен · {len(seeds)} сценариев · ярче = лучше",
             color=MUT, fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
