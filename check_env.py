"""Проверка окружения перед занятием:  python check_env.py

Если всё зелёное — вы готовы. Если нет — сообщение подскажет, что поставить.
"""
import os
import sys

ok = True


def line(good, text, hint=""):
    global ok
    ok = ok and good
    print(("✅ " if good else "❌ ") + text + ("" if good or not hint else f"\n   → {hint}"))


line(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "нужен Python 3.10 или новее: https://www.python.org/downloads/")
for name in ("numpy", "matplotlib", "pytest"):
    try:
        mod = __import__(name)
        line(True, f"{name} {getattr(mod, '__version__', '')}")
    except Exception:
        line(False, f"{name} не установлен", "выполните в папке репозитория: pip install -e .")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if ok:
    try:
        import matplotlib
        matplotlib.use("Agg")
        from ngk_sim.runner import run_episode
        res = run_episode(19, impl="student", write=False, verbose=False)
        k = res["kpi"]
        line(True, f"Симулятор работает: миссия seed 19 за {k['mission_time_s']} с, покрытие {k['checkpoints_covered']}/{k['checkpoints_total']}")
    except Exception as e:
        line(False, f"Симулятор не запустился: {e!r}", "запускайте из корня репозитория; пришлите ошибку преподавателю")

try:
    import matplotlib
    backend = matplotlib.get_backend()
    print(f"ℹ️  matplotlib backend: {backend}. Если окно анимации не откроется — запускайте с флагом --no-viz")
except Exception:
    pass

print("\nГотово к занятию 🎉" if ok else "\nЕсть проблемы — исправьте до занятия или работайте в паре с соседом.")
sys.exit(0 if ok else 1)
