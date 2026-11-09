"""C3 — отчёт: правильный формат и читаемая таблица."""
from ngk_sim.report_schema import validate
from ngk_sim.world import CHECKPOINTS


def test_report_schema(demo_run):
    errors = validate(demo_run["report"])
    assert not errors, "Отчёт не прошёл проверку формата:\n  · " + "\n  · ".join(errors)


def test_markdown_table(demo_run):
    md = demo_run["markdown"]
    table = [ln for ln in md.splitlines() if ln.strip().startswith("|")]
    assert table, "В report.md нет таблицы (строки, начинающиеся с «|»)"
    assert "Точка" in table[0], "Первая строка таблицы — заголовок со столбцом «Точка»"
    for cp in CHECKPOINTS:
        assert any(cp.id in ln for ln in table[2:]), f"В таблице нет строки для {cp.id}"


def test_team_name_is_set(mod):
    name = mod("team").TEAM_NAME
    assert name and name != "team-00", "Впишите название команды в student/team.py"
