from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.file import get_file_by_hash
from npo.database import get_session

metadata_router = APIRouter(
    prefix="/metadata",
    tags=["metadata"],
    responses={404: {"description": "Not found"}},
)


@metadata_router.get(
    "/{file_hash}",
    summary="Metadata by file hash",
)
async def get_metadata(file_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
    file_storage = await get_file_by_hash(file_hash, db)
    if file_storage:
        return file_storage.meta_data
    else:
        raise HTTPException(status_code=404, detail="Metadata not found")
