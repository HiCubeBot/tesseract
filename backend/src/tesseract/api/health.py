from fastapi import APIRouter
from pydantic import BaseModel

from tesseract import __version__

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: str
    version: str


@router.get("/health")
async def health() -> Health:
    return Health(status="ok", version=__version__)
