from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CheckResult, Site


async def create_site(session: AsyncSession, url: str, name: str | None) -> Site:
    site = Site(url=url, name=name)
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def get_site(session: AsyncSession, site_id: int) -> Site | None:
    return await session.get(Site, site_id)


async def get_site_by_url(session: AsyncSession, url: str) -> Site | None:
    return await session.scalar(select(Site).where(Site.url == url))


async def list_sites(session: AsyncSession) -> list[Site]:
    result = await session.scalars(select(Site).order_by(Site.id))
    return list(result)


async def delete_site(session: AsyncSession, site: Site) -> None:
    await session.delete(site)
    await session.commit()


async def list_active_sites(session: AsyncSession) -> list[Site]:
    # AM 22/Jul/26 - the scheduler polls only active sites. A disabled site
    # (is_active = False) keeps its history but is skipped on each round.
    # .is_(True) is the SQLAlchemy idiom for "== True" (plain == triggers linters).
    result = await session.scalars(select(Site).where(Site.is_active.is_(True)))
    return list(result)


async def save_check_result(
    session: AsyncSession,
    *,  # AM 22/Jul/26 - everything after * is keyword-only: callers must name the
    #                    args, so several same-typed values can't be mixed up by order
    site_id: int,
    is_up: bool,
    status_code: int | None,
    response_time_ms: float | None,
    error: str | None,
) -> None:
    # AM 22/Jul/26 - crud owns building the DB object. It takes plain values, NOT the
    # checker's CheckOutcome, so the DB layer stays independent of the network layer
    # (same boundary idea as converting HttpUrl -> str before it reaches crud).
    result = CheckResult(
        site_id=site_id,
        is_up=is_up,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error=error,
    )
    session.add(result)
    await session.commit()
