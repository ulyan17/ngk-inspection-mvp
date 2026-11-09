"""Общие настройки тестов.

По умолчанию проверяется код команды (student/).
Преподаватель проверяет эталон так:  NGK_IMPL=solutions pytest
"""
import importlib
import os
import sys

import matplotlib

matplotlib.use("Agg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

IMPL = os.environ.get("NGK_IMPL", "student")
DEMO_SEED = 19   # в этом мире тупик с K2 перекрыт, есть блик и выброс манометра


@pytest.fixture(scope="session")
def impl():
    return IMPL


@pytest.fixture(scope="session")
def mod(impl):
    """Модули решения: mod('mission'), mod('inspector'), mod('report')."""
    def _load(name):
        return importlib.import_module(f"{impl}.{name}")
    return _load


@pytest.fixture(scope="session")
def demo_run(impl):
    from ngk_sim.runner import run_episode
    return run_episode(DEMO_SEED, impl=impl, write=False, verbose=False)
