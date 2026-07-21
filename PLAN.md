# Uptime Monitor — план реализации (3 дня)

Асинхронный сервис на FastAPI: конкурентный опрос сайтов через httpx,
фоновый планировщик на asyncio, REST API со статистикой, тесты с моками сети.

## Стек

| Что | Версия/пакет | Зачем |
|---|---|---|
| Python | 3.12+ | |
| FastAPI | `fastapi` | API, Swagger из коробки |
| Uvicorn | `uvicorn[standard]` | ASGI-сервер |
| httpx | `httpx` | async HTTP-клиент для проверок |
| SQLAlchemy 2.0 | `sqlalchemy[asyncio]` + `aiosqlite` | async-работа с SQLite |
| pydantic-settings | `pydantic-settings` | конфиг из переменных окружения |
| Тесты | `pytest`, `pytest-asyncio` | |
| Пакеты/окружение | `uv` | зависимости, venv и запуск одной командой |

## Конвенции проекта

- Все комментарии в коде — на английском, с префиксом автора и даты написания
  в формате `AM DD/Mmm/YY`: `# AM 19/Jul/26 - enable foreign keys for SQLite`.
  Docstrings — на английском.
- Все сообщения вывода программы (print, логи, тексты ошибок) — на английском.
- База создаётся ТОЛЬКО командой `uv run python -m app.installation`
  (`--force` — пересоздать с потерей данных). Приложение при старте
  проверяет базу (fail-fast) и падает с подсказкой, если её нет.

## Структура проекта

```
uptime-monitor/
├── app/
│   ├── __init__.py
│   ├── main.py            # создание FastAPI-приложения, lifespan (старт/стоп планировщика)
│   ├── config.py          # Settings: интервал проверок, таймаут, лимит параллелизма, путь к БД
│   ├── installation.py    # установка/развёртывание: создание таблиц (--force — пересоздать)
│   ├── database.py        # async engine, session-фабрика, зависимость get_session
│   ├── models.py          # SQLAlchemy-модели: Site, CheckResult
│   ├── schemas.py         # Pydantic-схемы: SiteCreate, SiteRead, CheckRead, SiteStats
│   ├── crud.py            # функции доступа к БД (create_site, list_sites, save_result, ...)
│   ├── routers/
│   │   ├── __init__.py
│   │   └── sites.py       # все эндпоинты /sites...
│   └── monitor/
│       ├── __init__.py
│       ├── checker.py     # check_site(client, url) — проверка ОДНОГО сайта
│       └── scheduler.py   # run_monitor() — бесконечный цикл: собрать сайты, опросить, записать
├── tests/
│   ├── conftest.py        # фикстуры: тестовая БД в памяти, тестовый клиент API
│   ├── test_checker.py    # checker с MockTransport (таймаут, 500, connect error, успех)
│   └── test_api.py        # CRUD-эндпоинты через httpx.ASGITransport
├── pyproject.toml         # декларация зависимостей (создаёт uv)
├── uv.lock                # точные версии (создаёт uv, коммитится в git)
├── .gitignore             # .venv/, __pycache__/, *.db
└── README.md
```

Логика разделения: `checker.py` не знает про БД, `crud.py` не знает про HTTP,
`scheduler.py` — единственное место, где они соединяются. Роутеры тонкие:
принял запрос → вызвал crud → вернул схему.

## Модель данных

**Site** — что мониторим:
- `id: int` (PK)
- `url: str` (unique, not null)
- `name: str | None` — человекочитаемое имя
- `is_active: bool` (default True) — можно выключить проверки, не удаляя историю
- `created_at: datetime`

**CheckResult** — одна проверка:
- `id: int` (PK)
- `site_id: int` (FK → Site, ondelete=CASCADE)
- `checked_at: datetime`
- `is_up: bool`
- `status_code: int | None` — None, если ответа не было вообще
- `response_time_ms: float | None`
- `error: str | None` — "timeout" / "connect_error" / "http_500" / None

Правило: is_up = (ответ получен) И (status_code < 500). 4xx считаем «жив»:
сервер работает, просто ресурс не найден/запрещён. Это решение зафиксировать в README.

## Контракт API

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/sites` | добавить сайт `{url, name?}` → 201 + SiteRead; дубль URL → 409 |
| GET | `/sites` | список сайтов + последний статус каждого |
| GET | `/sites/{id}` | один сайт; нет → 404 |
| DELETE | `/sites/{id}` | удалить сайт вместе с историей → 204 |
| GET | `/sites/{id}/checks?limit=50` | последние N проверок |
| GET | `/sites/{id}/stats?hours=24` | статистика за период |

`SiteStats`: `uptime_percent`, `avg_response_time_ms`, `checks_total`,
`checks_failed`, `period_hours`.

## Конфиг (config.py)

```
CHECK_INTERVAL_SECONDS = 30    # пауза между раундами проверок
REQUEST_TIMEOUT_SECONDS = 5    # таймаут одного запроса
MAX_CONCURRENT_CHECKS = 20     # размер семафора
DATABASE_URL = "sqlite+aiosqlite:///./monitor.db"
```

Через `pydantic-settings` (класс `Settings(BaseSettings)`), чтобы можно было
переопределять переменными окружения — плюс в копилку «12-factor».

---

## День 1 — API и база (без асинхронной магии)

1. **Окружение** (uv сам создаёт и обслуживает venv):
   ```
   uv init
   uv add fastapi "uvicorn[standard]" httpx "sqlalchemy[asyncio]" aiosqlite pydantic-settings
   uv add --dev pytest pytest-asyncio
   git init
   ```
   Запуск сервера: `uv run uvicorn app.main:app --reload`, тесты: `uv run pytest`.
   Если uv не установлен: `winget install astral-sh.uv` (или установщик с astral.sh/uv).
2. **config.py** — Settings.
3. **models.py** — Site, CheckResult (SQLAlchemy 2.0-стиль: `Mapped`, `mapped_column`).
4. **database.py** — `create_async_engine`, `async_sessionmaker`,
   зависимость `get_session` (async-генератор с yield), `ensure_db_exists()` —
   fail-fast-проверка базы при старте (файл + таблица sites).
   Создание таблиц — только в **installation.py** (create_all — Alembic
   не берём, не тот масштаб).
5. **schemas.py** — SiteCreate (валидация URL через `HttpUrl`), SiteRead, CheckRead.
6. **crud.py** — create_site, get_site, list_sites, delete_site.
7. **routers/sites.py** — CRUD-эндпоинты (пока без /stats и /checks).
8. **main.py** — приложение, подключение роутера, init_db в lifespan.

**Чекпоинт дня 1**: `uvicorn app.main:app --reload` → в Swagger
(http://127.0.0.1:8000/docs) создать сайт, увидеть его в списке, удалить.
Перезапустить сервер — данные на месте. Невалидный URL → 422, дубль → 409.

## День 2 — ядро: конкурентные проверки

1. **monitor/checker.py** — датакласс `CheckOutcome(is_up, status_code,
   response_time_ms, error)` и функция `check_site(client, url) -> CheckOutcome`:
   `client.get` в try/except, замер времени через `time.monotonic()`,
   ветки: успех / TimeoutException / ConnectError / прочие httpx-ошибки.
   Никакой БД внутри — чистая функция, легко тестировать.
2. **crud.py** — добавить `save_check_result`, `list_active_sites`.
3. **monitor/scheduler.py** — `run_monitor(engine)`: бесконечный цикл —
   загрузить активные сайты → `asyncio.gather(*[guarded_check(s) for s in sites])`,
   где guarded_check оборачивает check_site в `asyncio.Semaphore` →
   записать результаты одной сессией → `asyncio.sleep(interval)`.
   Один общий `httpx.AsyncClient` на всё время жизни планировщика.
   Весь цикл в try/except с логированием — упавший раунд не убивает планировщик.
4. **main.py** — в lifespan: `task = asyncio.create_task(run_monitor(...))`
   на старте, `task.cancel()` + подавление CancelledError на остановке.
5. **Логирование** — модуль `logging`, в каждом раунде: сколько сайтов
   проверено, сколько лежит, длительность раунда.

**Чекпоинт дня 2**: добавить через API нормальный сайт, `https://10.255.255.1`
(таймаут), несуществующий домен, `http://localhost:9999` (refused),
`https://httpbin.org/status/500`. Подождать 2–3 раунда: в логах видны раунды,
в БД копятся CheckResult с правильными error. Раунд с висящим сайтом длится
~timeout, а не сумму всех — доказательство конкурентности.

## День 3 — статистика, тесты, README

1. **crud.py + routers** — `get_site_stats` (агрегация func.count/func.avg
   по CheckResult за период), эндпоинты `/checks` и `/stats`,
   в `GET /sites` подмешать последний статус.
2. **tests/conftest.py** — фикстуры: engine на `sqlite+aiosqlite:///:memory:`,
   переопределение get_session через `app.dependency_overrides`,
   API-клиент `httpx.AsyncClient(transport=ASGITransport(app=app))`.
3. **tests/test_checker.py** — 4 теста через `httpx.MockTransport`:
   200 → is_up=True; ConnectTimeout → is_up=False, error="timeout";
   ConnectError → error="connect_error"; ответ 500 → is_up=False, code=500.
4. **tests/test_api.py** — создание сайта, 409 на дубль, 422 на кривой URL,
   404 на чужой id, удаление, stats на пустой истории (не делит на ноль!).
5. **README.md** — что это, стек, как запустить, скриншот Swagger,
   раздел «Почему async» с замером (50 URL последовательно vs конкурентно),
   принятые решения (4xx = жив, SQLite, без Alembic — и почему).
6. Финальный прогон: pytest зелёный, сервис работает с чистой БД.

**Опционально, если останется время** (именно в этом порядке):
- `GET /health` — health-check самого сервиса (стандарт индустрии, 10 минут);
- WebSocket `/ws/status` — живые обновления статусов.

## День 4 (опционально) — Docker

Только после того, как чекпоинт дня 3 пройден: тесты зелёные, сервис работает.
Если Docker Desktop не установлен — установка (через WSL2 на Windows 10 Home)
считается отдельным временем, не входит в «пару часов».

1. **Dockerfile**: `python:3.12-slim` + бинарник uv из официального образа
   (`COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/`); сначала COPY
   pyproject.toml + uv.lock и `RUN uv sync --frozen --no-dev`, потом COPY app/
   (порядок важен — кэширование слоёв), CMD `uv run uvicorn ...` на 0.0.0.0.
2. **.dockerignore**: .venv/, __pycache__/, *.db, .git/, tests/.
3. **Volume для БД**: путь к SQLite вынести в /app/data/monitor.db;
   разовая инициализация волюма:
   `docker run --rm -v ./data:/app/data uptime-monitor uv run python -m app.installation`,
   запуск: `docker run -p 8000:8000 -v ./data:/app/data uptime-monitor`.
   Без volume база умирает вместе с контейнером — проверить это руками
   (остановить/удалить контейнер, запустить заново).
4. **README**: раздел «Запуск в Docker» (build + run одной командой).

Что НЕ делать: docker-compose с Postgres — это расширение для отдельного
захода, не для первой версии.

## Типичные грабли (заглядывать сюда при отладке)

- **`asyncio.gather` без обработки ошибок**: одно исключение — и весь раунд
  рухнул. Ловим ошибки внутри check_site, gather получает только результаты.
- **Одна AsyncSession из параллельных корутин** — нельзя, сессия не
  потокобезопасна. Проверки сети делаем параллельно БЕЗ сессии,
  потом записываем результаты последовательно одной сессией.
- **Забытый await** — корутина «не работает» молча. Смотреть warnings.
- **SQLite + параллельная запись** — «database is locked»; лечится тем же
  паттерном «пишем последовательно» и это ок для пет-проекта.
- **datetime.utcnow() устарел** — использовать `datetime.now(timezone.utc)`.
- **Тесты видят боевую БД** — значит, dependency_overrides не сработал;
  проверить, что переопределяется именно та функция, что в Depends.
