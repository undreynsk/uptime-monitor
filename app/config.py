from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    check_interval_seconds: int = 30
    request_timeout_seconds: float = 5.0
    max_concurrent_checks: int = 20
    # AM 23/Jul/26 - hard deadline for ONE check: a backstop above the httpx timeout.
    # httpx applies its timeout per phase (connect, read, ...), and its read timeout
    # only bounds the gap between chunks — so a slow or dripping server can stretch a
    # check far past request_timeout_seconds. Keep this comfortably larger than
    # request_timeout_seconds so httpx's own, more precise errors normally win.
    check_deadline_seconds: float = 15.0
    # AM 22/Jul/26 - hard upper bound for one whole round. Per-request timeouts alone
    # do not guarantee it: the httpx read timeout means "time between bytes", not total
    # time, and database calls have no timeout at all. A stuck round is cut off here
    # and the scheduler moves on to the next one.
    round_timeout_seconds: float = 120.0
    # AM 18/Jul/26 - the app never creates this database itself,
    # it is created once by 'uv run python -m app.installation'
    database_url: str = "sqlite+aiosqlite:///./monitor.db"


settings = Settings()
