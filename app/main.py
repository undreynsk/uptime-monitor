from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import ensure_db_exists
from app.routers import sites


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application is running, connecting to db...")
    ensure_db_exists() 
    yield
    print("Application finished, disconnecting from db...")



app = FastAPI(title="Uptime Monitor", lifespan=lifespan)
app.include_router(sites.router)
