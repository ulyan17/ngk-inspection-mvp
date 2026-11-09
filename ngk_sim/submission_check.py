"""Проверка документов перед сдачей.

    python -m ngk_sim check-submission --homework   # домашнее задание: homework/

Протокол занятия сдаётся в Word (submission/gate_protocol.docx) и проверяется преподавателем.
"""
from __future__ import annotations

import os
import re

VENDORS = ["А «Быстрый обход»", "Б «Надёжный»", "В «Сбалансированный»", "Г «Оптимальный маршрут»"]
BLANK = "______"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _field(text, label):
    """Текст после **label:** до следующего пустого абзаца с **…**, без заглушек."""
    m = re.search(r"\*\*" + re.escape(label) + r"[^*]*:\*\*(.*?)(?=\n\*\*|\n### |\n## |\Z)", text, re.S)
    return (m.group(1).replace(BLANK, "").strip() if m else "")


def _ticked(text):
    return re.findall(r"- \[[xXхХ]\] \*\*([^*]+)\*\*", text)


def _team(folder, out):
    team = _read(os.path.join(folder, "TEAM.md"))
    if team is None:
        out.append((False, f"нет {folder}/TEAM.md"))
        return
    m = re.search(r"\*\*Название команды:\*\*\s*(.+)", team)
    out.append((bool(m) and BLANK not in m.group(1).split("(")[0], "TEAM.md: название команды"))
    people = [ln for ln in team.splitlines() if ln.startswith("|") and BLANK not in ln and not ln.startswith("|---")
              and "Роль" not in ln and ln.count("|") >= 4
              and ln.split("|")[2].strip() not in ("", "_(четвёртый участник, если есть)_")]
    out.append((len(people) >= 2, f"TEAM.md: участники ({len(people)} заполнено, нужно ≥ 2)"))


def _risks(text, out, fname):
    sec = re.search(r"## \d\. [^\n]*рис[^\n]*\n(.*?)\n## ", text, re.S | re.I)
    rows = [ln for ln in (sec.group(1) if sec else "").splitlines()
            if ln.startswith("|") and not ln.startswith("|---") and "Риск" not in ln and len(ln.split("|")[1].strip()) > 3]
    out.append((len(rows) >= 2, f"{fname}: рисков заполнено — {len(rows)}, нужно 2"))


def check(folder: str = "submission") -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    _team(folder, out)
    pr = _read(os.path.join(folder, "gate_protocol.md"))
    if pr is None:
        out.append((False, f"нет {folder}/gate_protocol.md"))
        return out
    s1 = re.search(r"## 1\.(.*?)\n## 2\.", pr, re.S)
    s1_rows = [ln for ln in (s1.group(1) if s1 else "").splitlines()
               if ln.startswith("| ") and any(v.split(" ", 1)[1] in ln for v in VENDORS)]
    s1_ok = sum(1 for ln in s1_rows if all(c.strip() for c in ln.strip().strip("|").split("|")[1:3]))
    out.append((s1_ok == 4, f"Раздел 1: сводка из evidence/compare*.md ({s1_ok} из 4 подрядчиков)"))
    parts = re.split(r"\n### ", pr)
    for v in VENDORS:
        sec = next((p for p in parts if p.startswith(v)), "")
        sec = sec.split("\n## ")[0]
        ok_dec = len(_ticked(sec)) == 1
        meas, why, fix = _field(sec, "Измерения показали"), _field(sec, "Почему"), _field(sec, "Что подрядчику исправить")
        out.append((ok_dec and len(meas) >= 20 and len(why) >= 30 and len(fix) >= 10,
                    f"Подрядчик {v}: решение ({len(_ticked(sec))} отмечено), измерения, причина, что исправить"))
    pilot = re.search(r"## 3\.(.*?)\n## 4\.", pr, re.S)
    p_text = pilot.group(1) if pilot else ""
    out.append((len(_ticked(p_text)) == 1, f"Кандидат на пилот: отмечено {len(_ticked(p_text))}, нужно ровно 1"))
    just = _field(p_text, "Условия допуска и обоснование")
    out.append((len(just) >= 120, f"Обоснование выбора ({len(just)} символов, нужно ≥ 120)"))
    _risks(pr, out, "gate_protocol.md")
    q5 = re.search(r"## 5\.[^\n]*\n(.*?)\n## 6\.", pr, re.S)
    q5t = re.sub(r"Согласны ли вы.*?\n", "", q5.group(1) if q5 else "").replace(BLANK, "").strip()
    out.append((len(q5t) >= 60, f"Вопрос к воротам ({len(q5t)} символов, нужно ≥ 60)"))
    return out


def check_homework(folder: str = "homework") -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    kpi = _read(os.path.join(folder, "kpi_table.md"))
    rows = [ln for ln in (kpi or "").splitlines() if re.match(r"\|\s*\d+\s*\|", ln)]
    filled = [r for r in rows if sum(1 for c in r.split("|")[3:8] if c.strip()) >= 3]
    out.append((len(filled) >= 3, f"kpi_table.md: заполнено строк с KPI — {len(filled)}, нужно ≥ 3"))
    gk = _read(os.path.join(folder, "gate_kpi.md"))
    out.append((gk is not None and "seed" in (gk or ""), "gate_kpi.md: приёмка (python -m ngk_sim accept --seeds …)"))
    gr = _read(os.path.join(folder, "gate_review.md")) or ""
    out.append((len(_ticked(gr)) == 1, f"gate_review.md: отмечено решений — {len(_ticked(gr))}, нужно ровно 1"))
    sec = re.search(r"## 3\. Обоснование(.*?)## 4\.", gr, re.S)
    text = re.sub(r"3–5 предложений:.*?\n", "", sec.group(1) if sec else "").replace(BLANK, "").strip()
    out.append((len(text) >= 150, f"gate_review.md: обоснование ({len(text)} символов, нужно ≥ 150)"))
    _risks(gr, out, "gate_review.md")
    return out


def main(folder: str | None = None, homework: bool = False) -> int:
    if not homework:
        print("Протокол занятия сдаётся в Word: submission/gate_protocol.docx.\n"
              "Для домашнего задания: python -m ngk_sim check-submission --homework")
        return 0
    res = check_homework(folder or "homework")
    for ok, text in res:
        print(("✅ " if ok else "❌ ") + text)
    good = all(ok for ok, _ in res)
    print("\nСдача готова 🎉" if good else "\nДозаполните отмеченное ❌ — см. README, раздел «Что сдаём».")
    return 0 if good else 1
