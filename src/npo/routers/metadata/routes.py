from fastapi import APIRouter


metadata_router = APIRouter(
    prefix="/metadata",
    tags=["metadata"],
    responses={404: {"description": "Not found"}},
)


@metadata_router.get(
    "{item_hash}",
    summary="App frontend settings",
)
async def get_metadata(item_hash: str):
    return item_hash
