from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Site


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
