"""Проверка самого валидатора документов (на заполненных примерах)."""
import os
import re
import shutil

from ngk_sim.submission_check import check, check_homework

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG = "Покрытие 100%, но на одном сценарии из пяти две ложные тревоги: выброс манометра на K3. " * 2


def _team(tmp):
    t = open(os.path.join(ROOT, "submission", "TEAM.md"), encoding="utf-8").read()
    t = t.replace("**Название команды:** ______", "**Название команды:** team-03")
    t = t.replace("| Оператор стенда (запускает команды) | ______ | ______ |", "| Оператор стенда (запускает команды) | Иванов И. | ivanov |")
    t = t.replace("| Следователь (ищет причины в картах, логах и коде) | ______ | ______ |", "| Следователь (ищет причины в картах, логах и коде) | Петрова А. | petrova |")
    (tmp / "TEAM.md").write_text(t, encoding="utf-8")


def test_filled_protocol_passes(tmp_path):
    _team(tmp_path)
    p = open(os.path.join(ROOT, "submission", "gate_protocol.md"), encoding="utf-8").read()
    for v in ("А «Быстрый обход»", "Б «Надёжный»", "В «Сбалансированный»", "Г «Оптимальный маршрут»"):
        p = p.replace(f"| {v} | | |", f"| {v} | 40% | 50% |")
    p = p.replace("**Измерения показали:** ______", "**Измерения показали:** " + LONG)
    p = p.replace("**Почему (причина и доказательство):** ______", "**Почему (причина и доказательство):** " + LONG)
    p = p.replace("**Что подрядчику исправить:** ______", "**Что подрядчику исправить:** добавить повтор точки")
    p = p.replace("- [ ] **RECYCLE**", "- [x] **RECYCLE**")
    p = p.replace("- [ ] **В**\n", "- [x] **В**\n")
    p = p.replace("**Условия допуска и обоснование (3–5 предложений):** ______", "**Условия допуска и обоснование (3–5 предложений):** " + LONG)
    p = re.sub(r"\| Риск \| Вероятность \(Н/С/В\) \| Что будет, если случится \| Что делаем \|\n\|---\|---\|---\|---\|\n\| \| \| \| \|\n\| \| \| \| \|",
               "| Риск | Вероятность (Н/С/В) | Что будет, если случится | Что делаем |\n|---|---|---|---|\n| Блики на солнце | В | ложные тревоги | досъём |\n| Нет связи | С | потеря данных | буфер |", p)
    p = p.replace("Согласны ли вы с порогами из `configs/gate_thresholds.json`? Что бы вы изменили или добавили для реального объекта и почему (2–3 предложения)?\n\n______",
                  "Согласны ли вы с порогами из `configs/gate_thresholds.json`? Что бы вы изменили или добавили для реального объекта и почему (2–3 предложения)?\n\n" + LONG)
    (tmp_path / "gate_protocol.md").write_text(p, encoding="utf-8")
    res = check(str(tmp_path))
    assert all(ok for ok, _ in res), [t for ok, t in res if not ok]


def test_empty_protocol_fails(tmp_path):
    shutil.copy(os.path.join(ROOT, "submission", "gate_protocol.md"), tmp_path / "gate_protocol.md")
    assert not all(ok for ok, _ in check(str(tmp_path)))


def test_filled_homework_passes(tmp_path):
    k = open(os.path.join(ROOT, "homework", "kpi_table.md"), encoding="utf-8").read()
    k = k.replace("| 0 | baseline, ничего не меняли | | | | | | |", "| 0 | baseline | 0.83 | 2 | да | 0.67 | 144 | нет |")
    k = k.replace("| 1 | C1: повтор недоступной точки | | | | | | |", "| 1 | C1 | 1 | 2 | да | 0.83 | 184 | нет |")
    k = k.replace("| 2 | C2: | | | | | | |", "| 2 | C2: медиана | 1 | 0 | да | 1 | 232 | да |")
    (tmp_path / "kpi_table.md").write_text(k, encoding="utf-8")
    g = open(os.path.join(ROOT, "homework", "gate_review.md"), encoding="utf-8").read()
    g = g.replace("- [ ] **RECYCLE**", "- [x] **RECYCLE**")
    g = g.replace("3–5 предложений: на какие KPI опирается решение, что из обязательного выполнено, что нет и почему вы всё равно (не) идёте дальше.\n\n______",
                  "3–5 предложений: на какие KPI опирается решение, что из обязательного выполнено, что нет и почему вы всё равно (не) идёте дальше.\n\n" + LONG)
    g = re.sub(r"\| Риск \| Вероятность \(Н/С/В\) \| Что будет, если случится \| Что делаем \|\n\|---\|---\|---\|---\|\n\| \| \| \| \|\n\| \| \| \| \|",
               "| Риск | Вероятность (Н/С/В) | Что будет, если случится | Что делаем |\n|---|---|---|---|\n| Блики | В | тревоги | досъём |\n| Связь | С | потеря | буфер |", g)
    (tmp_path / "gate_review.md").write_text(g, encoding="utf-8")
    (tmp_path / "gate_kpi.md").write_text("| seed 11 |", encoding="utf-8")
    res = check_homework(str(tmp_path))
    assert all(ok for ok, _ in res), [t for ok, t in res if not ok]
