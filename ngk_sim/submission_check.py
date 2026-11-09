"""Проверка папки submission/ перед сдачей:  python -m ngk_sim check-submission"""
from __future__ import annotations

import os
import re

DECISIONS = ["GO", "GO С УСЛОВИЯМИ", "HOLD", "RECYCLE", "KILL"]


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def check(folder: str = "submission") -> list[tuple[bool, str]]:
    out = []
    team = _read(os.path.join(folder, "TEAM.md"))
    if team is None:
        out.append((False, "нет submission/TEAM.md"))
    else:
        m = re.search(r"\*\*Название команды:\*\*\s*(.+)", team)
        name_ok = bool(m) and "______" not in m.group(1).split("(")[0]
        people = [ln for ln in team.splitlines() if ln.startswith("|") and "______" not in ln
                  and not ln.startswith("|---") and "Роль" not in ln and ln.count("|") >= 4
                  and ln.split("|")[2].strip() not in ("", "_(четвёртый участник, если есть)_")]
        out.append((name_ok, "TEAM.md: название команды"))
        out.append((len(people) >= 2, f"TEAM.md: участники ({len(people)} заполнено, нужно ≥ 2)"))

    kpi = _read(os.path.join(folder, "kpi_table.md"))
    if kpi is None:
        out.append((False, "нет submission/kpi_table.md"))
    else:
        rows = [ln for ln in kpi.splitlines() if re.match(r"\|\s*\d+\s*\|", ln)]
        filled = [r for r in rows if sum(1 for c in r.split("|")[3:8] if c.strip()) >= 3]
        out.append((len(filled) >= 3, f"kpi_table.md: заполнено строк с KPI — {len(filled)}, нужно ≥ 3"))

    gk = _read(os.path.join(folder, "gate_kpi.md"))
    out.append((gk is not None and "seed" in (gk or ""),
                "gate_kpi.md: таблица приёмки (создаётся командой python -m ngk_sim accept)"))

    gr = _read(os.path.join(folder, "gate_review.md"))
    if gr is None:
        out.append((False, "нет submission/gate_review.md"))
    else:
        ticked = re.findall(r"- \[[xXхХ]\] \*\*([^*]+)\*\*", gr)
        out.append((len(ticked) == 1, f"gate_review.md: отмечено решений — {len(ticked)}, нужно ровно 1"))
        sec = re.search(r"## 3\. Обоснование(.*?)## 4\.", gr, re.S)
        text = re.sub(r"3–5 предложений:.*?\n", "", sec.group(1)) if sec else ""
        text = text.replace("______", "").strip()
        out.append((len(text) >= 150, f"gate_review.md: обоснование ({len(text)} символов, нужно ≥ 150)"))
        sec2 = re.search(r"## 4\..*?\n(.*?)## 5\.", gr, re.S)
        risk_rows = [ln for ln in (sec2.group(1) if sec2 else "").splitlines()
                     if ln.startswith("|") and not ln.startswith("|---") and "Риск" not in ln
                     and len(ln.split("|")[1].strip()) > 3]
        out.append((len(risk_rows) >= 2, f"gate_review.md: рисков заполнено — {len(risk_rows)}, нужно 2"))
    return out


def main(folder: str = "submission") -> int:
    res = check(folder)
    for ok, text in res:
        print(("✅ " if ok else "❌ ") + text)
    good = all(ok for ok, _ in res)
    print("\nСдача готова 🎉" if good else "\nДозаполните отмеченное ❌ — см. README, раздел «Что сдаём».")
    return 0 if good else 1
