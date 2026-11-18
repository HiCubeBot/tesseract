import ipaddress

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from tesseract import __version__, audit
from tesseract.db.models import Node
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import apply_node, get_general, set_general

router = APIRouter(prefix="/settings", tags=["settings"])


class GeneralIn(BaseModel):
    acme_email: EmailStr | None = None
    public_ips: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("public_ips")
    @classmethod
    def _ips(cls, v: list[str]) -> list[str]:
        return [str(ipaddress.ip_address(ip.strip())) for ip in v if ip.strip()]


class GeneralOut(BaseModel):
    acme_email: str
    public_ips: list[str]
    # nur lesbar – kommen aus der Umgebung
    controller_domain: str
    version: str


@router.get("/general")
def get_settings_general(db: DB, _: CurrentActor, settings: AppSettings) -> GeneralOut:
    g = get_general(db)
    return GeneralOut(
        acme_email=g["acme_email"],
        public_ips=g["public_ips"],
        controller_domain=settings.controller_domain,
        version=__version__,
    )


@router.put("/general")
def put_settings_general(
    body: GeneralIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> GeneralOut:
    before = get_general(db)
    value = {"acme_email": body.acme_email or "", "public_ips": body.public_ips}
    set_general(db, value)
    audit.record(
        db,
        actor=actor.name,
        action="settings_changed",
        target="general",
        details={"before": before, "after": value},
        ip=actor.ip,
    )
    db.commit()
    if before["acme_email"] != value["acme_email"]:
        for node in db.scalars(select(Node)):
            apply_node(db, node, settings, request.app.state.caddy_transport)
        db.commit()
    return get_settings_general(db, actor, settings)
