"""Командная строка симулятора.

    python -m ngk_sim run --seed 1            # миссия с анимацией
    python -m ngk_sim run --seed 1 --no-viz   # без окна, только файлы в out/
    python -m ngk_sim run --variant A         # готовый MVP подрядчика (A, B, C, D)
    python -m ngk_sim compare                 # сравнить подрядчиков на 5 сценариях
    python -m ngk_sim accept --seeds 11 22 33 # приёмочный прогон → out/accept/gate_kpi.md
    python -m ngk_sim validate out/seed_1/report.json
    python -m ngk_sim check-submission        # проверить папку submission/ перед сдачей
    python -m ngk_sim world                   # нарисовать карту объекта в world.png
    python -m ngk_sim record --out mission.mp4  # видео миссии без окна
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    # чтобы пакеты student/ и solutions/ находились при запуске из корня репозитория
    sys.path.insert(0, os.getcwd())
    ap = argparse.ArgumentParser(prog="python -m ngk_sim", description="Симулятор инспекционного MVP (НГК)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="запустить миссию")
    r.add_argument("--seed", type=int, default=19, help="seed мира (19 — демо)")
    r.add_argument("--impl", default=os.environ.get("NGK_IMPL", "student"), help="пакет с решением (student)")
    r.add_argument("--variant", help="готовый MVP подрядчика: A, B, C или D")
    r.add_argument("--no-viz", action="store_true", help="без окна анимации")
    r.add_argument("--speed", type=int, default=2, help="перерисовка каждые N шагов (больше — быстрее)")
    r.add_argument("--out", default="out")
    r.add_argument("--no-wait", action="store_true", help="не ждать закрытия окна в конце")

    a = sub.add_parser("accept", help="приёмочный прогон на нескольких seed")
    a.add_argument("--seeds", type=int, nargs="+", required=True)
    a.add_argument("--impl", default=os.environ.get("NGK_IMPL", "student"))
    a.add_argument("--variant", help="готовый MVP подрядчика: A, B, C или D")
    a.add_argument("--out", default=os.path.join("out", "accept"))

    v = sub.add_parser("validate", help="проверить формат report.json")
    v.add_argument("path")

    rc = sub.add_parser("record", help="записать миссию в видео (mp4 или gif)")
    rc.add_argument("--seed", type=int, default=19)
    rc.add_argument("--impl", default=os.environ.get("NGK_IMPL", "student"))
    rc.add_argument("--variant", help="готовый MVP подрядчика: A, B, C или D")
    rc.add_argument("--out", default="mission.mp4")
    rc.add_argument("--fps", type=int, default=20)

    cp_ = sub.add_parser("compare", help="сравнить подрядчиков A–D на одних сценариях")
    cp_.add_argument("--seeds", type=int, nargs="+", help="сценарии (по умолчанию 101–105)")
    cp_.add_argument("--runs", type=int, help="проверка надёжности: N случайных сценариев")
    cp_.add_argument("--out", default=os.path.join("out", "compare"))

    cs = sub.add_parser("check-submission", help="проверить папку submission/ перед сдачей")
    cs.add_argument("--folder", default=None)
    cs.add_argument("--homework", action="store_true", help="проверить домашнее задание (homework/)")

    w = sub.add_parser("world", help="нарисовать карту объекта")
    w.add_argument("--out", default="world.png")

    args = ap.parse_args(argv)
    if getattr(args, "variant", None):
        from variants import resolve
        args.impl = resolve(args.variant)

    if args.cmd == "run":
        from .runner import run_episode
        res = run_episode(args.seed, impl=args.impl, viz=not args.no_viz, out_dir=args.out, speed=args.speed,
                          wait=not args.no_wait)
        return 0 if not res["kpi"]["crashed"] else 1
    if args.cmd == "accept":
        from .runner import accept
        accept(args.seeds, impl=args.impl, out_dir=args.out)
        return 0
    if args.cmd == "validate":
        from .report_schema import validate
        with open(args.path, encoding="utf-8") as f:
            errs = validate(json.load(f))
        if errs:
            print("❌ Отчёт не прошёл проверку:")
            for e in errs:
                print("  ·", e)
            return 1
        print("✅ Отчёт корректен")
        return 0
    if args.cmd == "compare":
        from .compare import compare
        compare(seeds=args.seeds, runs=args.runs, out_dir=args.out)
        return 0
    if args.cmd == "check-submission":
        from .submission_check import main as check_main
        return check_main(args.folder, homework=args.homework)
    if args.cmd == "record":
        from .record import record
        print(f"Видео сохранено: {record(args.seed, args.out, impl=args.impl, fps=args.fps)}")
        return 0
    if args.cmd == "world":
        from .viz import use_headless
        use_headless()
        import matplotlib.pyplot as plt
        from .viz import COL, _draw_static
        fig, ax = plt.subplots(figsize=(10, 7.5))
        fig.patch.set_facecolor(COL["bg"])
        _draw_static(ax)
        ax.set_title("Насосная станция: K1–K6, Ex-зона, техника на проезде (оранжевая)", color=COL["text"], loc="left")
        fig.tight_layout()
        fig.savefig(args.out, dpi=120, facecolor=fig.get_facecolor())
        print(f"Карта сохранена: {args.out}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
