"""C1 — миссия: недоступная точка не должна теряться."""
from ngk_sim.messages import Pose, Status
from ngk_sim.runner import run_episode
from ngk_sim.world import CHECKPOINTS

from conftest import DEMO_SEED

ALL_IDS = {cp.id for cp in CHECKPOINTS}


def test_every_checkpoint_has_result(demo_run):
    got = set(demo_run["record"].last_results())
    missing = sorted(ALL_IDS - got)
    assert not missing, (f"Нет результата по точкам {missing}. Тупик с K2 был перекрыт, "
                         "и миссия просто пропустила точку. Верните её в конец очереди (C1.2).")


def test_blocked_checkpoint_is_inspected_later(demo_run):
    n = demo_run["sim"].captures_at.get("K2", 0)
    assert n > 0, "Робот так и не доехал до K2. Нужна повторная попытка позже, когда проезд освободится."


def test_permanently_blocked_checkpoint_reported_unknown(impl):
    res = run_episode(DEMO_SEED, impl=impl, write=False, verbose=False, blockage_until=1e9)
    assert not res["kpi"]["crashed"], "Миссия упала или зациклилась, когда точка недоступна навсегда"
    r = res["record"].last_results().get("K2")
    assert r is not None, "Если точка недоступна навсегда, опубликуйте UNKNOWN через publish_unknown()"
    assert r.status == Status.UNKNOWN, f"Ожидался статус UNKNOWN для недоступной K2, а получен {r.status}"


def test_mission_returns_to_dock(demo_run):
    p = demo_run["sim"].pose
    assert abs(p.x - 3.0) < 1.0 and abs(p.y - 3.0) < 1.0, "В конце миссии робот должен вернуться на DOCK"


def test_plan_route_is_permutation(mod):
    order = mod("mission").plan_route(Pose(3.0, 3.0), CHECKPOINTS)
    assert sorted(order) == sorted(ALL_IDS), "plan_route должен вернуть каждую точку ровно один раз"
