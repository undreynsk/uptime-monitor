from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    check_interval_seconds: int = 30
    request_timeout_seconds: float = 5.0
    max_concurrent_checks: int = 20
    # AM 18/Jul/26 - the app never creates this database itself,
    # it is created once by 'uv run python -m app.installation'
    database_url: str = "sqlite+aiosqlite:///./monitor.db"


settings = Settings()
