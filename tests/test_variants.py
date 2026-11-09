"""Профили подрядчиков: у каждого свой изъян, который должна найти комиссия."""
from ngk_sim.compare import compare
from ngk_sim.runner import run_episode
from variants import VARIANTS, resolve


def run(letter, seed=101):
    return run_episode(seed, impl=VARIANTS[letter], write=False, verbose=False)


def test_resolve_russian_letters():
    assert resolve("Г") == VARIANTS["D"] and resolve("a") == VARIANTS["A"]


def test_a_skips_blocked_point():
    assert run("A", 19)["kpi"]["coverage"] < 0.9


def test_b_calls_operator_and_is_slow():
    k = run("B")["kpi"]
    assert k["manual_interventions"] > 0 and k["mission_time_s"] > 360


def test_c_passes_on_demo_world():
    assert run("C", 19)["gate"]["must_ok"]


def test_d_enters_ex_zone():
    k = run("D")["kpi"]
    assert k["ex_zone_violations"] > 0 and k["false_alarms"] == 0 and k["coverage"] == 1.0


def test_compare_writes_table(tmp_path):
    res = compare(seeds=[101], out_dir=str(tmp_path), to_submission=False, letters=["A", "D"])
    text = (tmp_path / "compare.md").read_text(encoding="utf-8")
    assert "Все обязательные сразу" in text and (tmp_path / "compare.png").exists() and res["must_rate"]["D"] == 0
