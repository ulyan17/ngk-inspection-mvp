"""Готовые MVP четырёх «подрядчиков» для практики-оценки. Заявления подрядчиков — в variants/VENDORS.md.

Запуск:  python -m ngk_sim run --variant A   (A, B, C, D)
"""
VARIANTS = {
    "A": "variants.a_fast",
    "B": "variants.b_careful",
    "C": "variants.c_balanced",
    "D": "variants.d_shortcut",
}
NAMES = {
    "A": "Подрядчик А «Быстрый обход»",
    "B": "Подрядчик Б «Надёжный»",
    "C": "Подрядчик В «Сбалансированный»",
    "D": "Подрядчик Г «Оптимальный маршрут»",
}
# русские буквы тоже принимаем
ALIASES = {"А": "A", "Б": "B", "В": "C", "Г": "D"}


def resolve(letter: str) -> str:
    key = ALIASES.get(letter.upper(), letter.upper())
    if key not in VARIANTS:
        raise SystemExit(f"Нет варианта {letter!r}. Доступны: A, B, C, D (или А, Б, В, Г)")
    return VARIANTS[key]
