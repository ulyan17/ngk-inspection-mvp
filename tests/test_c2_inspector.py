"""C2 — инспекция: блик ≠ перегрев, выброс манометра ≠ авария."""
import numpy as np

from ngk_sim.messages import CheckpointReading, Status
from ngk_sim.world import WorldInfo

K1 = WorldInfo().checkpoint("K1")   # давление 4–6 бар, предел 70 °C


def frame(hot=None, glare=None):
    t = np.full((8, 8), 30.0)
    if hot:
        t[3:5, 3:5] = 85.0           # пятно 2×2 выше предела
    if glare:
        t[1, 6] = 110.0              # один горячий пиксель — блик
    return t


def readings(gauges, frames):
    return [CheckpointReading("K1", float(i), g, f, 11) for i, (g, f) in enumerate(zip(gauges, frames))]


def test_glare_is_not_alarm(mod):
    rd = readings([5.0, 5.02, 4.98], [frame(), frame(glare=True), frame()])
    r = mod("inspector").Inspector().evaluate(K1, rd, 10.0)
    assert r.status == Status.OK, "Один горячий пиксель на одном кадре — это блик, а не перегрев (C2.3)"


def test_overheat_patch_is_alarm(mod):
    rd = readings([5.0, 5.02, 4.98], [frame(hot=True)] * 3)
    r = mod("inspector").Inspector().evaluate(K1, rd, 10.0)
    assert r.status == Status.ANOMALY and "overheat" in r.reason, "Пятно во всех кадрах — это перегрев"


def test_gauge_outlier_is_rejected(mod):
    rd = readings([6.7, 5.0, 5.04], [frame()] * 3)
    r = mod("inspector").Inspector().evaluate(K1, rd, 10.0)
    assert r.status == Status.OK, "Одно показание 6,7 бар среди 5,0 и 5,04 — выброс. Используйте медиану (C2.2)"
    assert r.gauge_bar is not None and abs(r.gauge_bar - 5.02) < 0.1


def test_real_overpressure_is_alarm(mod):
    rd = readings([6.8, 6.75, 6.82], [frame()] * 3)
    r = mod("inspector").Inspector().evaluate(K1, rd, 10.0)
    assert r.status == Status.ANOMALY and "overpressure" in r.reason


def test_blurred_frame_does_not_break(mod):
    rd = readings([None, 5.0, 5.02], [frame()] * 3)
    r = mod("inspector").Inspector().evaluate(K1, rd, 10.0)
    assert r.status == Status.OK


class _FakeSensors:
    def __init__(self):
        self.n = 0

    def capture(self, cp_id):
        self.n += 1
        return CheckpointReading(cp_id, float(self.n), 5.0, frame(), 11)


class _FakeCtx:
    def __init__(self):
        self.sensors = _FakeSensors()


def test_several_measurements_per_checkpoint(mod):
    ctx = _FakeCtx()
    rd = mod("inspector").Inspector().measure(ctx, K1)
    assert len(rd) >= 3, "Одного замера мало: смазанный кадр или выброс ломают решение (C2.1)"


def test_demo_mission_alarms(demo_run):
    k = demo_run["kpi"]
    assert k["anomaly_detected"], "Аномалия не найдена"
    assert k["false_alarms"] <= 1, f"Ложные тревоги на {k['false_alarm_checkpoints']} — порог ворот ≤ 1"
