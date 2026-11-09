# Инспекционный MVP для объекта НГК · ворота Go/No-Go

Практическое занятие курса «Газпром нефти» в СПбПУ. Робот-инспектор обходит упрощённую насосную станцию, снимает показания манометров и «тепловизора», ищет аномалию и пишет отчёт. В конце команда выходит на ворота: по KPI решает, допускать ли MVP к пилоту.

**Без ROS.** Всё работает на чистом Python под Windows, macOS и Linux. Имена топиков и API навигатора — как в ROS 2 / Nav2, поэтому дома код переносится на настоящий стек (папка `ros2_homework/`).

![Миссия робота: эталонное решение на seed 19](docs/mission.gif)

![Как всё работает](docs/how-it-works.png)

📘 **Лекция:** [docs/LECTURE.md](docs/LECTURE.md) · 🛠 **Практика пошагово:** [docs/PRACTICE.md](docs/PRACTICE.md) · 🗺 [карта объекта](docs/world.png)

## Быстрый старт (5 минут)

Нужен Python 3.10+ и терминал.

```bash
git clone <ссылка на репозиторий>
cd ngk-inspection-mvp
pip install -e .            # numpy, matplotlib, pytest
python check_env.py         # всё должно быть зелёным
python -m ngk_sim run       # миссия seed 19 с анимацией
```

Окно не открылось? Запустите `python -m ngk_sim run --no-viz` и откройте `out/seed_19/map.png` и `out/seed_19/report.md`.
Нет `git` — скачайте ZIP кнопкой **Code → Download ZIP**.

## Что вы увидите в baseline

```
❌ Покрытие точек контроля      0.83   порог >= 0.9
❌ Ложные тревоги                  2   порог <= 1
❌ Отчёт не прошёл проверку формата
```

Baseline работает, но на воротах получает No-Go. Ваша задача — довести его до Go.

## Задания на занятии

| Шаг | Время | Файл | Что сделать | Проверка |
|---|---|---|---|---|
| C0 | 5 мин | — | Запустить миссию, найти в выводе причины No-Go | `python -m ngk_sim run` |
| C1 | 10 мин | `student/mission.py` | Повторять недоступную точку; если не вышло — публиковать `UNKNOWN` | `pytest tests/test_c1_mission.py` |
| C2 | 12 мин | `student/inspector.py` | Несколько замеров, медиана, «пятно» вместо одного пикселя | `pytest tests/test_c2_inspector.py` |
| C3 | 8 мин | `student/report.py`, `student/team.py` | Сводка отчёта и таблица Markdown, название команды | `pytest tests/test_c3_report.py` |
| ✓ | 4 мин | — | Приёмка на скрытых seed (их назовёт преподаватель) | `python -m ngk_sim accept --seeds A B C` |
| G | 14 мин | `templates/gate_review.md` | Заполнить чек-лист ворот и защитить решение | — |

Каждый TODO в коде подписан номером (C1.1, C2.2…). Подсказки — в `hints/` (раскрывайте по одной). Все тесты сразу: `pytest`.

## Как устроен репозиторий

```
ngk-inspection-mvp/
├── student/                ← ВЫ РАБОТАЕТЕ ЗДЕСЬ
│   ├── mission.py          C1: очередь точек, повторные попытки
│   ├── inspector.py        C2: замеры, решение OK / ANOMALY / UNKNOWN, тревога
│   ├── report.py           C3: отчёт JSON + Markdown
│   └── team.py             название команды
├── ngk_sim/                симулятор (менять не нужно)
│   ├── world.py            карта, точки K1–K6, Ex-зона, техника на проезде
│   ├── planner.py          A* с keepout для Ex-зоны (как в Nav2)
│   ├── sim.py              навигатор (API как BasicNavigator), датчики, оператор
│   ├── bus.py              шина «публикация–подписка» (как топики ROS 2)
│   ├── evaluate.py         KPI по эталону и проверка порогов ворот
│   └── report_schema.py    проверка формата отчёта
├── configs/gate_thresholds.json   пороги ворот
├── tests/                  автопроверка заданий
├── hints/                  подсказки C1–C3
├── templates/              gate_review.md, kpi_table.md
├── ros2_homework/          домашнее задание на ROS 2
└── .github/workflows/ci.yml       GitHub Actions: тесты на каждый push
```

## Как это соотносится с ROS 2

| ROS 2 / Nav2 | Здесь |
|---|---|
| узел rclpy | модуль в `student/` |
| `publisher.publish(msg)` в `/inspection/result` | `ctx.bus.publish(Topics.RESULT, msg)` |
| `BasicNavigator.goToPose()` / `isTaskComplete()` / `getResult()` | `ctx.nav.goToPose()` / `isTaskComplete()` / `getResult()` |
| keepout-фильтр Nav2 | Ex-зона непроходима в планировщике |
| `ros2 bag record` (MCAP) | `out/seed_N/mission.jsonl` |

## Что доступно вашему коду (`ctx`)

| | |
|---|---|
| `ctx.world.checkpoints` | паспорт точек: `id`, `name`, `x`, `y`, `p_min`, `p_max`, `temp_limit_c`, `tag_id`, `pose` |
| `ctx.nav` | навигатор: `goToPose(pose)`, `isTaskComplete()`, `getResult()`, `getFeedback()`, `cancelTask()`, `getPose()` |
| `ctx.sensors.capture(cp_id)` | один замер (4 с): `gauge_bar` (может быть `None`), `thermal` 8×8 °C, `tag_id` |
| `ctx.operator.manual_reading(cp_id)` | точный замер оператором — **+1 ручное вмешательство** и 60 с |
| `ctx.bus.publish(topic, msg)` | опубликовать сообщение |
| `ctx.wait(s)`, `ctx.now()`, `ctx.log(text)` | подождать, время, лог |

## KPI и ворота

KPI считает симулятор **по эталону**, а не по вашему отчёту. Пороги — в `configs/gate_thresholds.json`:

| Критерий | Порог | Тип |
|---|---|---|
| Нарушения Ex-зон | 0 | обязательный |
| Покрытие точек контроля | ≥ 90% | обязательный |
| Аномалия найдена | да | обязательный |
| Ложные тревоги | ≤ 1 | обязательный |
| Ручные вмешательства | 0 | обязательный |
| Сбой запуска | нет | обязательный |
| Точность показаний (±0,15 бар) | ≥ 80% точек | желательный |
| Время миссии | ≤ 360 с | желательный |

Автопроверка только сравнивает цифры с порогами. Решение Go / Kill / Hold / Recycle и его обоснование — за командой.

## Как сдавать

1. Сделайте форк репозитория и закоммитьте изменения в `student/`.
2. Убедитесь, что GitHub Actions зелёный (вкладка **Actions**).
3. Положите заполненный `templates/gate_review.md` и `out/accept/gate_kpi.md` в папку `submission/`.
4. Пришлите ссылку на форк преподавателю.

## Если что-то не работает

| Проблема | Решение |
|---|---|
| `pip install -e .` ругается | `pip install numpy matplotlib pytest` и запускайте из корня репозитория |
| Нет интернета | преподаватель раздаст папку `wheels/`: `pip install --no-index --find-links wheels numpy matplotlib pytest` |
| Окно анимации пустое или не открывается | `--no-viz`, результаты в `out/seed_19/` |
| Анимация медленная | `--speed 5` (перерисовка реже) |
| Нужно видео без окна | `python -m ngk_sim record --out mission.mp4` (нужен ffmpeg) или `--out mission.gif` |
| `ModuleNotFoundError: student` | запускайте команды из корня репозитория |
