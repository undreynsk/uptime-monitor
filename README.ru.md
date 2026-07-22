# Uptime Monitor

[English](README.md) | **Русский**

> Английская версия ([README.md](README.md)) — основная. Русская может немного отставать.

Асинхронный сервис мониторинга доступности веб-сайтов на **FastAPI** и **asyncio**.

Ты регистрируешь сайты через REST API. Фоновый планировщик затем конкурентно
опрашивает их все с фиксированным интервалом (через `httpx`) и сохраняет историю
каждой проверки — код ответа, время отклика и был ли сайт доступен.

> MVP, построенный вокруг настоящего асинхронного ввода-вывода: конкурентные сетевые
> проверки с ограничением параллелизма, фоновая задача внутри жизненного цикла
> приложения, слоистая архитектура и внедрение зависимостей.

---

## Стек

| Область | Выбор |
| --- | --- |
| Язык | Python 3.14 |
| Веб-фреймворк | FastAPI + Uvicorn (ASGI) |
| Документация API | Swagger UI / OpenAPI (генерируется автоматически) |
| HTTP-клиент | httpx (async) |
| База данных | SQLite через SQLAlchemy 2.0 (async) + aiosqlite |
| Валидация / настройки | Pydantic v2, pydantic-settings |
| Тесты | pytest, pytest-asyncio |
| Пакеты | uv |

---

## Структура проекта

```
app/
  main.py            # Приложение FastAPI + lifespan (запускает фоновый планировщик)
  config.py          # Настройки (переопределяются переменными окружения)
  database.py        # Async-движок, фабрика сессий, fail-fast проверка базы
  models.py          # Модели SQLAlchemy: Site, CheckResult
  schemas.py         # Pydantic-схемы (вход/выход API)
  crud.py            # Операции с базой (не знает про HTTP)
  installation.py    # Разовая настройка базы (создание таблиц)
  routers/
    sites.py         # Эндпоинты /sites
  monitor/
    checker.py       # check_site(): проверка ОДНОГО сайта (чистая сеть, без базы)
    scheduler.py     # run_monitor(): фоновый цикл, конкурентные проверки
tests/
  test_database.py   # тесты fail-fast проверки базы
```

Слои разделены: `checker` знает про сеть, но не про базу; `crud` знает про базу,
но не про HTTP; `scheduler` — единственное место, где они встречаются.

---

## Установка

Требуется [uv](https://docs.astral.sh/uv/). Установка зависимостей:

```bash
uv sync
```

Команда создаёт локальное виртуальное окружение (`.venv`) и ставит всё из `uv.lock`.

> **Запускай все команды из корня проекта.** Путь к базе относительный, поэтому запуск
> из другой папки заставит приложение искать базу не там — и оно откажется стартовать,
> а не создаст пустую.

---

## База данных

Приложение никогда не создаёт базу само (fail-fast: если базы нет, оно отказывается
запускаться, а не создаёт молча пустую). Создай её один раз командой установки:

```bash
uv run python -m app.installation
```

Удалить и пересоздать все таблицы (**стирает все данные**):

```bash
uv run python -m app.installation --force
```

---

## Запуск сервера

```bash
uv run uvicorn app.main:app --reload
```

Затем открой интерактивную документацию API (Swagger UI):

```
http://127.0.0.1:8000/docs
```

При старте фоновый планировщик начинает опрашивать активные сайты. Сводка по каждому
раунду пишется в консоль, например:

```
Round done: 6 checked, 4 down, took 5.02s
```

---

## Настройки

У всех настроек есть значения по умолчанию, их можно переопределить переменными
окружения:

| Переменная | По умолчанию | Смысл |
| --- | --- | --- |
| `CHECK_INTERVAL_SECONDS` | `30` | Пауза между раундами проверок |
| `REQUEST_TIMEOUT_SECONDS` | `5` | Таймаут одной проверки сайта |
| `MAX_CONCURRENT_CHECKS` | `20` | Максимум одновременных проверок |
| `DATABASE_URL` | `sqlite+aiosqlite:///./monitor.db` | Строка подключения к базе |

Пример (Windows PowerShell):

```powershell
$env:CHECK_INTERVAL_SECONDS = 10
uv run uvicorn app.main:app
```

---

## API

| Метод | Путь | Описание |
| --- | --- | --- |
| `POST` | `/sites` | Добавить сайт: `{ "url": "...", "name": "..." }` |
| `GET` | `/sites` | Список всех сайтов |
| `GET` | `/sites/{id}` | Получить один сайт |
| `DELETE` | `/sites/{id}` | Удалить сайт и его историю |

Сайт считается **доступным (up)**, если он ответил и код ответа меньше 500. Код
`4xx` тоже считается up (сервер здоров, проблема в запросе); только таймауты,
ошибки соединения и `5xx` считаются down.

---

## Как попробовать одну проверку

`checker.py` — это модуль-библиотека (без точки входа из командной строки). Чтобы
попробовать одну проверку интерактивно, используй Python REPL:

```bash
uv run python
```

```python
import asyncio, httpx
from app.monitor.checker import check_site

async def try_url(url):
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        return await check_site(client, url)

asyncio.run(try_url("https://example.com"))
# CheckOutcome(is_up=True, status_code=200, response_time_ms=120.4, error=None)

asyncio.run(try_url("https://httpbin.org/status/500"))
# CheckOutcome(is_up=False, status_code=500, response_time_ms=310.0, error='http_500')
```

---

## Тесты

```bash
uv run pytest
```

---

## Планы (Roadmap)

- `GET /sites/{id}/checks` — недавняя история проверок
- `GET /sites/{id}/stats` — процент доступности и среднее время отклика за период
- Модульные тесты для `check_site` через `httpx.MockTransport`
- Docker-образ
