from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_session
from app.schemas import SiteCreate, SiteRead

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post("", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
async def create_site(
    data: SiteCreate, session: AsyncSession = Depends(get_session)
) -> SiteRead:
    url = str(data.url)
    if await crud.get_site_by_url(session, url) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Site with this URL already exists"
        )
    site = await crud.create_site(session, url=url, name=data.name)
    return site


@router.get("", response_model=list[SiteRead])
async def list_sites(session: AsyncSession = Depends(get_session)) -> list[SiteRead]:
    return await crud.list_sites(session)


@router.get("/{site_id}", response_model=SiteRead)
async def get_site(
    site_id: int, session: AsyncSession = Depends(get_session)
) -> SiteRead:
    site = await crud.get_site(session, site_id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    site = await crud.get_site(session, site_id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site not found")
    await crud.delete_site(session, site)
