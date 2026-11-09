"""Собирает «материалы комиссии» — папку evidence/ для практики без запуска.

На занятии студенты ничего не запускают: они открывают evidence/ на GitHub
и пишут протокол по готовым гифкам, картам, логам, замерам и коду.
Эту папку собирает преподаватель (или студент дома, чтобы проверить себя):

    python tools/build_evidence.py

Результат детерминирован: те же seed → те же файлы.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ngk_sim.compare import compare  # noqa: E402
from ngk_sim.runner import run_episode  # noqa: E402
from ngk_sim.world import WorldInfo  # noqa: E402
from variants import NAMES, VARIANTS  # noqa: E402

OUT = os.path.join(ROOT, "evidence")
DEMO_SEED = 19
ACCEPT = [101, 102, 103, 104, 105]
LETTERS_RU = {"A": "А", "B": "Б", "C": "В", "D": "Г"}
STATUS_RU = {"OK": "норма", "ANOMALY": "ТРЕВОГА", "UNKNOWN": "не определено", "FAILED": "не доехал"}


def vendor_claims() -> dict:
    """Заявления подрядчиков из variants/VENDORS.md."""
    text = open(os.path.join(ROOT, "variants", "VENDORS.md"), encoding="utf-8").read()
    claims = {}
    for L, ru in LETTERS_RU.items():
        m = re.search(r"\| \*\*" + ru + r"\*\* \| [^|]+\| (.+?) \| `", text)
        claims[L] = m.group(1).strip() if m else ""
    return claims


def run_one(L: str, seed: int, tmp: str) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_episode(seed, impl=VARIANTS[L], out_dir=tmp, write=True, verbose=True)
    run_dir = os.path.join(tmp, f"seed_{seed}")
    log = "\n".join(ln for ln in buf.getvalue().splitlines() if not ln.lstrip().startswith("Файлы:")).rstrip()
    readings = []
    with open(os.path.join(run_dir, "mission.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["topic"] == "/sensors/reading":
                readings.append(d["msg"])
    return {"log": log, "readings": readings, "map": os.path.join(run_dir, "map.png"),
            "report": open(os.path.join(run_dir, "report.md"), encoding="utf-8").read()}


def readings_table(readings: list) -> str:
    world = WorldInfo()
    rows = ["| Время, с | Точка | Манометр, бар | Норма, бар | Макс. в кадре, °C | Пикселей выше предела | Предел, °C |",
            "|---:|---|---:|---|---:|---:|---:|"]
    for r in readings:
        cp = world.checkpoint(r["checkpoint_id"])
        g = r.get("gauge_bar")
        g_txt = "— (кадр смазан)" if g is None else f"{g:.3f}" + (" ⚠️" if g < cp.p_min or g > cp.p_max else "")
        th = r.get("thermal")
        if th:
            flat = [v for row in th for v in row]
            hot = sum(1 for v in flat if v > cp.temp_limit_c)
            t_max, hot_txt = f"{max(flat):.1f}", str(hot) + (" 🔥" if hot else "")
        else:
            t_max, hot_txt = "—", "—"
        rows.append(f"| {r['stamp']:.1f} | {cp.id} | {g_txt} | {cp.p_min}–{cp.p_max} | {t_max} | {hot_txt} | {cp.temp_limit_c:.0f} |")
    return "\n".join(rows)


def section_run(L: str, seed: int, data: dict, img_rel: str, title: str) -> str:
    n = len(data["readings"])
    return f"""### {title}

<img src="{img_rel}" width="640" alt="{NAMES[L]}, seed {seed}">

<details><summary>📜 Лог миссии и итог (как в терминале)</summary>

```
{data['log']}
```
</details>

<details><summary>📋 Отчёт подрядчика (report.md)</summary>

{data['report'].replace('# ', '#### ', 1).replace(chr(10) + '## ', chr(10) + '##### ')}
</details>

<details><summary>🔬 Все замеры датчиков: {n} кадров</summary>

⚠️ — давление вне нормы паспорта, 🔥 — в кадре есть пиксели горячее предела точки.

{readings_table(data['readings'])}
</details>
"""


def code_block(L: str) -> str:
    pkg = VARIANTS[L].split(".")[1]
    rel = f"../../variants/{pkg}/mission.py"
    code = open(os.path.join(ROOT, "variants", pkg, "mission.py"), encoding="utf-8").read().rstrip()
    return f"""## 3. Код подрядчика

Файл [`variants/{pkg}/mission.py`]({rel}). Общая часть для всех подрядчиков — [`variants/common.py`](../../variants/common.py).

```python
{code}
```
"""


def build_vendor(L: str, claims: dict, tmp: str) -> None:
    d = os.path.join(OUT, L)
    os.makedirs(d, exist_ok=True)
    demo = run_one(L, DEMO_SEED, os.path.join(tmp, L))
    shutil.copy(demo["map"], os.path.join(d, f"seed_{DEMO_SEED}.png"))
    parts = [f"""# {NAMES[L]} · материалы комиссии

[← все материалы](../README.md) · подрядчики: {' · '.join(f'[{LETTERS_RU[x]}](../{x}/README.md)' for x in VARIANTS)}

> **Заявление подрядчика:** {claims[L]}

Ничего запускать не нужно: всё ниже — записи готовых прогонов. Ваша задача — сверить заявление с тем, что видно.

## 1. Демо-прогон (seed {DEMO_SEED})

<img src="../../docs/img/vendor-{L}.gif" width="640" alt="Анимация прогона {NAMES[L]}">

Цвет точек: 🟢 норма · 🟠 тревога · ⚪ не проверена. Красные точки на маршруте — заезд в Ex-зону.

""", section_run(L, DEMO_SEED, demo, f"seed_{DEMO_SEED}.png", f"Итоговая карта демо-прогона · seed {DEMO_SEED}"),
             f"""
## 2. Приёмка: 5 сценариев ({', '.join(map(str, ACCEPT))})

Сводка по всем подрядчикам — [compare.md](../compare.md). Здесь — каждый прогон этого подрядчика отдельно.
"""]
    for s in ACCEPT:
        data = run_one(L, s, os.path.join(tmp, L))
        shutil.copy(data["map"], os.path.join(d, f"seed_{s}.png"))
        parts.append(section_run(L, s, data, f"seed_{s}.png", f"Сценарий seed {s}"))
    parts.append(code_block(L))
    parts.append("""
## Что записать в протокол

В Word-шаблоне протокола ([⬇️ gate_protocol.docx](https://github.com/ulyan17/ngk-inspection-mvp/raw/main/submission/gate_protocol.docx)), страница этого подрядчика:
- **Измерения показали** — цифры из [compare.md](../compare.md) и [compare_30.md](../compare_30.md);
- **Почему** — по формуле «файл → что в нём видно → вывод», например: «seed N, карта → …», «замеры seed N, K… → …», «код, строка … → …».
""")
    with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def build_index(claims: dict) -> None:
    world = WorldInfo()
    passports = "\n".join(f"| {c.id} | {c.name} | {c.p_min}–{c.p_max} | {c.temp_limit_c:.0f} |" for c in world.checkpoints)
    cells = "\n".join(
        f'<td width="25%"><a href="{L}/README.md"><img src="../docs/img/vendor-{L}.gif" alt="{NAMES[L]}"></a><br>'
        f'<b><a href="{L}/README.md">{LETTERS_RU[L]} {NAMES[L].split(" ", 2)[2]}</a></b></td>' for L in VARIANTS)
    text = f"""# 🗂 Материалы комиссии

[← к уроку](../README.md)

На занятии **ничего не запускаем**. Все прогоны уже записаны: гифки, карты, логи, замеры датчиков и код. Вы открываете эти страницы прямо на GitHub и заполняете Word-шаблон протокола: [⬇️ gate_protocol.docx](https://github.com/ulyan17/ngk-inspection-mvp/raw/main/submission/gate_protocol.docx).

## Подрядчики

<table><tr>
{cells}
</tr></table>

| | Подрядчик | Заявление | Досье |
|---|---|---|---|
""" + "\n".join(f"| **{LETTERS_RU[L]}** | {NAMES[L].split(' ', 2)[2]} | {claims[L]} | [открыть →]({L}/README.md) |" for L in VARIANTS) + f"""

В каждом досье: анимация демо-прогона, карты всех 5 сценариев приёмки, лог миссии, отчёт подрядчика, **все замеры датчиков** и код.

## Сводки KPI

| | Что это | Файлы |
|---|---|---|
| **5 сценариев приёмки** | все подрядчики на одинаковых seed {ACCEPT[0]}–{ACCEPT[-1]} | [compare.md](compare.md) · [compare.png](compare.png) |
| **30 случайных сценариев** | надёжность: доля прогонов, где критерий выполнен | [compare_30.md](compare_30.md) · [compare_30.png](compare_30.png) |

<img src="compare.png" alt="Сводка KPI на 5 сценариях">

<img src="compare_30.png" alt="Сводка KPI на 30 сценариях">

## Паспорта точек контроля

Нужны, чтобы читать таблицы замеров: давление вне нормы или пиксели горячее предела — это повод для тревоги.

| Точка | Оборудование | Норма давления, бар | Предел температуры, °C |
|---|---|---|---|
{passports}

<img src="../docs/img/world.png" width="560" alt="Карта насосной станции">

## Блик или перегрев

Датчики ошибаются, как настоящие: бывают смазанные кадры (нет показания манометра), выбросы манометра и блики на тепловизоре. Блик — это один-два горячих пикселя в одном кадре, перегрев — пятно, которое повторяется в нескольких кадрах.

<img src="../docs/img/glare-vs-overheat.png" alt="Реальные кадры тепловизора: блик и перегрев">

---

*Папка собрана командой `python tools/build_evidence.py`. Дома можете запустить всё сами — см. [homework/README.md](../homework/README.md).*
"""
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(text)


def main() -> None:
    tmp = os.path.join(ROOT, "out", "_evidence")
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(OUT)
    claims = vendor_claims()
    with contextlib.redirect_stdout(io.StringIO()):
        compare(seeds=ACCEPT, out_dir=os.path.join(tmp, "c5"), to_submission=False)
        compare(runs=30, out_dir=os.path.join(tmp, "c30"), to_submission=False)
    for name, src in [("compare", "c5"), ("compare_30", "c30")]:
        for ext in ("md", "png"):
            cand = [f for f in os.listdir(os.path.join(tmp, src)) if f.endswith("." + ext)]
            dst = os.path.join(OUT, f"{name}.{ext}")
            shutil.copy(os.path.join(tmp, src, cand[0]), dst)
            if ext == "md":
                t = open(dst, encoding="utf-8").read()
                t = re.sub(r"\nКарты первых сценариев:.*\n?", "\nКарты, логи и замеры каждого прогона — в досье подрядчиков: "
                           + " · ".join(f"[{LETTERS_RU[x]}]({x}/README.md)" for x in VARIANTS) + "\n", t)
                open(dst, "w", encoding="utf-8").write(t)
    for L in VARIANTS:
        build_vendor(L, claims, tmp)
    build_index(claims)
    shutil.rmtree(tmp, ignore_errors=True)
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print(f"✅ evidence/ собрана: {total / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
