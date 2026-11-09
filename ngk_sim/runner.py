"""Запуск миссии и приёмочного прогона."""
from __future__ import annotations

import importlib
import json
import os
import traceback

from .api import Context
from .bus import Bus, to_jsonable
from .evaluate import check_gate, compute_kpi, fmt, load_thresholds
from .messages import MissionRecord, Topics
from .report_schema import validate
from .sim import MissionTimeout, Sim, SimNavigator, SimOperator, SimSensors
from .world import WorldInfo, make_truth

OK = "✅"
BAD = "❌"


def load_impl(impl: str):
    """impl — имя пакета с решением: 'student' (по умолчанию) или 'solutions'."""
    mission = importlib.import_module(f"{impl}.mission")
    report = importlib.import_module(f"{impl}.report")
    team = importlib.import_module(f"{impl}.team")
    return mission, report, team


def run_episode(seed: int, impl: str = "student", viz: bool = False, out_dir: str = "out", write: bool = True,
                verbose: bool = True, blockage_until: float | None = None, speed: int = 2, wait: bool = True,
                thresholds_path: str | None = None) -> dict:
    if not viz:
        from .viz import use_headless
        use_headless()
    mission_mod, report_mod, team_mod = load_impl(impl)
    world = WorldInfo()
    truth = make_truth(seed, blockage_until)
    bus = Bus()
    sim = Sim(world, truth, bus)
    nav, sensors, operator = SimNavigator(sim), SimSensors(sim), SimOperator(sim)
    ctx = Context(sim, nav, sensors, operator, bus, world, verbose=verbose)
    record = MissionRecord(seed=seed, team=getattr(team_mod, "TEAM_NAME", "team-00"), checkpoints=list(world.checkpoints))
    bus.subscribe(Topics.RESULT, record.results.append)
    bus.subscribe(Topics.ALARM, record.alarms.append)

    live = None
    if viz:
        try:
            from .viz import LiveViz
            live = LiveViz(sim, bus, every=speed, title=f"{record.team} · seed {seed}")
        except Exception as e:  # окно не открылось — работаем без него
            print(f"⚠️  Не удалось открыть окно визуализации ({e}). Продолжаю без него, см. map.png")
            live = None

    record.started_s = sim.t
    try:
        mission_mod.run_mission(ctx)
    except MissionTimeout as e:
        record.crashed = True
        print(f"{BAD} {e}")
    except Exception:
        record.crashed = True
        print(f"{BAD} Миссия упала с ошибкой:")
        traceback.print_exc()
    record.finished_s = sim.t

    # отчёт команды
    report, md, report_errors = None, "", []
    try:
        report = report_mod.build_report(record)
        report_errors = validate(report)
        md = report_mod.to_markdown(report)
    except Exception as e:
        report_errors = [f"build_report/to_markdown упали: {e!r}"]
        traceback.print_exc()

    kpi = compute_kpi(record, truth, sim)
    kpi["report_valid"] = not report_errors
    gate = check_gate(kpi, load_thresholds(thresholds_path))

    paths = {}
    if write:
        d = os.path.join(out_dir, f"seed_{seed}")
        os.makedirs(d, exist_ok=True)
        paths = {k: os.path.join(d, v) for k, v in
                 {"report": "report.json", "md": "report.md", "kpi": "kpi.json", "bag": "mission.jsonl",
                  "map": "map.png"}.items()}
        if report is not None:
            with open(paths["report"], "w", encoding="utf-8") as f:
                json.dump(to_jsonable(report), f, ensure_ascii=False, indent=2)
        with open(paths["md"], "w", encoding="utf-8") as f:
            f.write(md or "")
        with open(paths["kpi"], "w", encoding="utf-8") as f:
            json.dump({"kpi": kpi, "gate": gate, "report_errors": report_errors}, f, ensure_ascii=False, indent=2)
        bus.dump_jsonl(paths["bag"])
        try:
            from .viz import save_map
            save_map(paths["map"], sim, bus, record.last_results(),
                     f"{record.team} · seed {seed} · покрытие {kpi['checkpoints_covered']}/{kpi['checkpoints_total']}")
        except Exception as e:
            print(f"⚠️  Не удалось сохранить map.png: {e}")

    if verbose:
        print_summary(kpi, gate, report_errors, paths)
    if live is not None:
        live.close(wait=wait)
    return {"kpi": kpi, "gate": gate, "report_errors": report_errors, "record": record, "paths": paths,
            "truth": truth, "sim": sim, "bus": bus, "report": report, "markdown": md}


def print_summary(kpi: dict, gate: dict, report_errors: list, paths: dict) -> None:
    print("\n" + "=" * 64)
    print(f" ИТОГ МИССИИ · {kpi['team']} · seed {kpi['seed']}")
    print("=" * 64)
    for r in gate["rows"]:
        mark = OK if r["ok"] else BAD
        kind = "обяз." if r["group"] == "must" else "желат."
        print(f" {mark} {r['label']:<34} {fmt(r['value']):>8}   порог {r['op']} {fmt(r['threshold']):<6} ({kind})")
    print("-" * 64)
    if report_errors:
        print(f" {BAD} Отчёт не прошёл проверку формата:")
        for e in report_errors[:8]:
            print(f"    · {e}")
    else:
        print(f" {OK} Отчёт report.json прошёл проверку формата")
    verdict = "все обязательные критерии выполнены" if gate["must_ok"] else "есть невыполненные обязательные критерии"
    print(f" Ворота: {verdict}. Решение Go / Kill / Hold / Recycle принимаете вы.")
    t = kpi["truth"]
    print(f" Истина этого seed: аномалия на {t['anomaly_checkpoint']} ({t['anomaly_kind']}).")
    if paths:
        print(f" Файлы: {os.path.dirname(paths['kpi'])}/  (report.json, report.md, kpi.json, map.png, mission.jsonl)")
    print("=" * 64 + "\n")


def accept(seeds: list[int], impl: str = "student", out_dir: str = "out/accept", thresholds_path: str | None = None,
           copy_to_submission: bool = True) -> dict:
    """Приёмочный прогон на нескольких seed. Пишет gate_kpi.md — исходные данные для ворот."""
    runs = []
    for s in seeds:
        print(f"▶ Приёмочный прогон: seed {s}")
        runs.append(run_episode(s, impl=impl, viz=False, out_dir=out_dir, verbose=False,
                                thresholds_path=thresholds_path))
    thresholds = load_thresholds(thresholds_path)
    keys = list(thresholds["must"].keys()) + list(thresholds["should"].keys())
    team = runs[0]["kpi"]["team"] if runs else "?"
    lines = [f"# KPI приёмочного прогона — {team}", "",
             f"Seed: {', '.join(str(s) for s in seeds)}. KPI посчитаны симулятором по эталонным данным.", "",
             "| Критерий | Тип | Порог | " + " | ".join(f"seed {s}" for s in seeds) + " | Итог |",
             "|---|---|---|" + "---|" * len(seeds) + "---|"]
    all_must = True
    for key in keys:
        group = "must" if key in thresholds["must"] else "should"
        rule = thresholds[group][key]
        cells, oks = [], []
        for run in runs:
            row = next(r for r in run["gate"]["rows"] if r["key"] == key)
            oks.append(row["ok"])
            cells.append(f"{fmt(row['value'])} {OK if row['ok'] else BAD}")
        ok_all = all(oks)
        if group == "must" and not ok_all:
            all_must = False
        label = runs[0]["gate"]["rows"][[r["key"] for r in runs[0]["gate"]["rows"]].index(key)]["label"]
        lines.append(f"| {label} | {'обязательный' if group == 'must' else 'желательный'} | {rule['op']} {fmt(rule['value'])} | "
                     + " | ".join(cells) + f" | {OK if ok_all else BAD} |")
    valid = all(not r["report_errors"] for r in runs)
    lines += ["", f"Отчёт в правильном формате на всех прогонах: {'да ' + OK if valid else 'нет ' + BAD}",
              f"Воспроизводимость: {sum(not r['kpi']['crashed'] for r in runs)} из {len(runs)} прогонов без сбоев", "",
              "**Автоматическая проверка:** " + ("все обязательные критерии выполнены на всех seed."
                                                 if all_must else "есть невыполненные обязательные критерии."),
              "", "Решение (Go / Kill / Hold / Recycle) и обоснование — в homework/gate_review.md.", ""]
    lines.append("<details><summary>Истина (раскрывается после прогона)</summary>\n")
    for s, r in zip(seeds, runs):
        t = r["kpi"]["truth"]
        lines.append(f"- seed {s}: аномалия {t['anomaly_checkpoint']} ({t['anomaly_kind']}); "
                     f"ложные тревоги на: {', '.join(r['kpi']['false_alarm_checkpoints']) or '—'}")
    lines.append("\n</details>\n")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "gate_kpi.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:len(keys) + 8]))
    print(f"\n📄 Таблица для ворот: {path}")
    if copy_to_submission and os.path.isdir("homework"):
        import shutil
        shutil.copy(path, os.path.join("homework", "gate_kpi.md"))
        print("📄 Копия для сдачи: homework/gate_kpi.md")
    return {"runs": runs, "all_must": all_must, "path": path}
