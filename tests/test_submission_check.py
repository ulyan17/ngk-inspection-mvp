"""Проверка самого валидатора папки submission/ (на заполненном примере)."""
import os
import shutil

from ngk_sim.submission_check import check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fill(tmp):
    src = os.path.join(ROOT, "submission")
    for f in ("TEAM.md", "kpi_table.md", "gate_review.md"):
        shutil.copy(os.path.join(src, f), tmp / f)
    t = (tmp / "TEAM.md").read_text(encoding="utf-8")
    t = t.replace("**Название команды:** ______", "**Название команды:** team-03")
    t = t.replace("| Водитель (пишет код) | ______ | ______ |", "| Водитель (пишет код) | Иванов И. | ivanov |")
    t = t.replace("| Штурман (TODO, тесты, подсказки) | ______ | ______ |", "| Штурман (TODO, тесты, подсказки) | Петрова А. | petrova |")
    (tmp / "TEAM.md").write_text(t, encoding="utf-8")
    k = (tmp / "kpi_table.md").read_text(encoding="utf-8")
    k = k.replace("| 0 | baseline, ничего не меняли | | | | | | |", "| 0 | baseline | 0.83 | 2 | да | 0.67 | 144 | нет |")
    k = k.replace("| 1 | C1: повтор недоступной точки | | | | | | |", "| 1 | C1 | 1 | 2 | да | 0.83 | 184 | нет |")
    k = k.replace("| 2 | C2: | | | | | | |", "| 2 | C2: медиана | 1 | 0 | да | 1 | 232 | да |")
    (tmp / "kpi_table.md").write_text(k, encoding="utf-8")
    g = (tmp / "gate_review.md").read_text(encoding="utf-8")
    g = g.replace("- [ ] **RECYCLE**", "- [x] **RECYCLE**")
    g = g.replace("## 3. Обоснование\n\n3–5 предложений: на какие KPI опирается решение, что из обязательного выполнено, что нет и почему вы всё равно (не) идёте дальше.\n\n______",
                  "## 3. Обоснование\n\n" + "Все обязательные критерии выполнены на трёх seed, но точность на одном seed ниже порога. " * 3)
    g = g.replace("| Риск | Вероятность (Н/С/В) | Что будет, если случится | Что делаем |\n|---|---|---|---|\n| | | | |\n| | | | |",
                  "| Риск | Вероятность (Н/С/В) | Что будет, если случится | Что делаем |\n|---|---|---|---|\n| Блики на солнце | В | ложные тревоги | досъём |\n| Нет связи | С | потеря данных | буфер |")
    (tmp / "gate_review.md").write_text(g, encoding="utf-8")
    (tmp / "gate_kpi.md").write_text("# KPI\n| Критерий | seed 1 |\n", encoding="utf-8")


def test_filled_submission_passes(tmp_path):
    _fill(tmp_path)
    res = check(str(tmp_path))
    assert all(ok for ok, _ in res), [t for ok, t in res if not ok]
