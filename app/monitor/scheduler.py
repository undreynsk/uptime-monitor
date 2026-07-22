"""Background scheduler: periodically checks all active sites.

This is the ONE place where the network layer (checker) and the database
layer (crud) meet. Everything else stays unaware of the other side.
"""

import asyncio
import logging
import time

import httpx

from app import crud
from app.config import settings
from app.database import SessionFactory
from app.models import Site
from app.monitor.checker import CheckOutcome, check_site

# AM 22/Jul/26 - named logger for this module; configured in main.py
logger = logging.getLogger("uptime.scheduler")


async def _guarded_check(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, site: Site
) -> tuple[Site, CheckOutcome]:
    # AM 22/Jul/26 - the semaphore is a turnstile: only N checks run at the same time.
    # "async with semaphore" waits for a free slot, then releases it on exit.
    # This limits concurrent NETWORK requests (sockets), nothing to do with the DB.
    async with semaphore:
        outcome = await check_site(client, site.url)
    return site, outcome


async def _run_one_round(client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> None:
    # AM 22/Jul/26 - PHASE 1: read active sites. Short-lived session, just a read.
    async with SessionFactory() as session:
        sites = await crud.list_active_sites(session)

    if not sites:
        logger.info("No active sites to check")
        return

    # AM 22/Jul/26 - PHASE 2: check ALL sites concurrently, WITHOUT touching the DB.
    # gather runs the coroutines together on the event loop and waits for all of them.
    # No session is used here, so concurrency is safe.
    started = time.monotonic()
    results = await asyncio.gather(
        *(_guarded_check(client, semaphore, site) for site in sites)
    )
    elapsed = time.monotonic() - started

    # AM 22/Jul/26 - PHASE 3: write results SEQUENTIALLY with ONE session.
    # A SQLAlchemy session is NOT safe to share across concurrent coroutines,
    # so we intentionally write one by one here, after the concurrent phase is over.
    down = 0
    async with SessionFactory() as session:
        for site, outcome in results:
            if not outcome.is_up:
                down += 1
            await crud.save_check_result(
                session,
                site_id=site.id,
                is_up=outcome.is_up,
                status_code=outcome.status_code,
                response_time_ms=outcome.response_time_ms,
                error=outcome.error,
            )

    # AM 22/Jul/26 - the key proof of concurrency: 'elapsed' stays close to one timeout,
    # not the sum of all timeouts, even when several sites hang.
    logger.info(
        "Round done: %d checked, %d down, took %.2fs", len(sites), down, elapsed
    )


async def run_monitor() -> None:
    # AM 22/Jul/26 - ONE client for the whole lifetime: reuses TCP connections between
    # rounds (pooling) and carries the timeout, so check_site does not set it per call.
    # follow_redirects=True: follow 301/302 to judge the final destination.
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
    ) as client:
        # AM 22/Jul/26 - one shared semaphore for all rounds
        semaphore = asyncio.Semaphore(settings.max_concurrent_checks)
        logger.info(
            "Monitor started (interval=%ss, timeout=%ss, max_concurrent=%d)",
            settings.check_interval_seconds,
            settings.request_timeout_seconds,
            settings.max_concurrent_checks,
        )
        # AM 22/Jul/26 - the infinite loop. It never returns on its own; it is stopped
        # from outside by task.cancel() (see lifespan in main.py), which raises
        # CancelledError. CancelledError is a BaseException, NOT Exception, so the
        # "except Exception" below does not swallow it -> shutdown stays clean.
        while True:
            try:
                await _run_one_round(client, semaphore)
            except Exception:
                # AM 22/Jul/26 - a single failed round must NOT kill the scheduler;
                # log the traceback and keep going with the next round.
                logger.exception("Round failed")
            # AM 22/Jul/26 - async sleep = a cooperative pause: while we wait here,
            # the event loop is free to serve HTTP requests. NEVER use time.sleep here.
            logger.info("Sleeping for %ss until the next round...", settings.check_interval_seconds)
            await asyncio.sleep(settings.check_interval_seconds)
