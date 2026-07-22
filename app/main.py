import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import ensure_db_exists
from app.monitor.scheduler import run_monitor
from app.routers import sites

# AM 22/Jul/26 - configure logging once, so the scheduler's INFO logs show in the console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application is running, connecting to db...")
    ensure_db_exists()

    # AM 22/Jul/26 - start the scheduler as a BACKGROUND task. create_task (NOT await!)
    # schedules run_monitor alongside the app and returns at once, so startup can finish
    # and the API begins serving requests. await run_monitor() would hang here forever.
    monitor_task = asyncio.create_task(run_monitor())

    yield

    # AM 22/Jul/26 - on shutdown: ask the task to stop, then wait for it to actually end.
    # cancel() raises CancelledError inside run_monitor; we await it and swallow that
    # error, which is the normal, expected way the background task finishes.
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    print("Application finished, disconnecting from db...")



app = FastAPI(title="Uptime Monitor", lifespan=lifespan)
app.include_router(sites.router)
