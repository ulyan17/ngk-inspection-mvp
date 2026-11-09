"""Проверки самого симулятора (должны быть зелёными всегда)."""
from ngk_sim.bus import Bus
from ngk_sim.planner import GridMap
from ngk_sim.report_schema import validate
from ngk_sim.runner import accept, run_episode
from ngk_sim.world import BLOCKAGE, EX_ZONE, OBSTACLES, make_truth


def test_same_seed_same_world():
    a, b = make_truth(42), make_truth(42)
    assert a == b


def test_runs_are_deterministic(impl):
    k1 = run_episode(7, impl=impl, write=False, verbose=False)["kpi"]
    k2 = run_episode(7, impl=impl, write=False, verbose=False)["kpi"]
    assert k1 == k2


def test_planner_avoids_ex_zone():
    grid = GridMap(OBSTACLES, keepout=[EX_ZONE])
    path = grid.plan((15.0, 18.0), (24.5, 22.0))   # K3 → K5, напрямую — через Ex-зону
    assert path is not None
    assert not any(EX_ZONE.contains(x, y) for x, y in path)


def test_blockage_cuts_dead_end():
    grid = GridMap(OBSTACLES, keepout=[EX_ZONE])
    grid.set_dynamic([BLOCKAGE])
    assert grid.plan((3.0, 3.0), (28.0, 5.0)) is None
    grid.set_dynamic([])
    assert grid.plan((3.0, 3.0), (28.0, 5.0)) is not None


def test_bus_pubsub():
    bus, got = Bus(), []
    bus.subscribe("/alarm", got.append)
    bus.publish("/alarm", "msg")
    assert got == ["msg"] and bus.messages("/alarm") == ["msg"]


def test_validator_rejects_garbage():
    assert validate({}) and validate([]) and validate({"schema_version": "1.0"})


def test_accept_writes_gate_table(impl, tmp_path):
    res = accept([3, 4], impl=impl, out_dir=str(tmp_path), copy_to_submission=False)
    text = (tmp_path / "gate_kpi.md").read_text(encoding="utf-8")
    assert "Покрытие" in text and "seed 3" in text and res["path"].endswith("gate_kpi.md")
