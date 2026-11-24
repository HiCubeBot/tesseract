"""Client-Zertifikat des Controllers selbst.

Damit kommt Tesseract durch die mTLS-Prüfung eigener Hosts, ohne an einer IP oder einem
Docker-Netz zu hängen – z. B. für Benachrichtigungen an ntfy oder Webhooks hinter Tesseract.
Freigegeben wird es pro Host („Tesseract selbst darf zugreifen“).

- Ausgestellt vom aktiven Zwischenzertifikat (wie Gerätezertifikate), 1 Jahr gültig
- Neu ausgestellt, wenn es fehlt, in 30 Tagen abläuft oder das Zwischenzertifikat gewechselt hat
- Schlüssel verschlüsselt in der Datenbank; für ausgehende Verbindungen zusätzlich als Dateien
  unter `<data_dir>/controller-client/` (nur für den Controller lesbar)
"""

import asyncio
import logging
import os
import ssl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from tesseract import pki
from tesseract.db.models import Setting, utcnow
from tesseract.identity import CAError, active_authority, intermediate_keypair
from tesseract.secretbox import SecretBox

log = logging.getLogger("tesseract.controllercert")

SETTING = "controller_client"
KEY_CONTEXT = "controller-client-key"
VALID_DAYS = 365
RENEW_DAYS = 30
CN = "Tesseract Controller"


def stored(db: Session) -> dict[str, Any] | None:
    row = db.get(Setting, SETTING)
    return dict(row.value) if row and row.value else None


def allowed_entry(db: Session) -> tuple[str, str] | None:
    """(Fingerabdruck, PEM) für die Freigabe in Caddy – None, solange es keins gibt."""
    s = stored(db)
    return (s["fingerprint"], s["cert_pem"]) if s else None


def _due(db: Session, s: dict[str, Any] | None, now: datetime) -> bool:
    if not s:
        return True
    inter = active_authority(db, "intermediate")
    if inter is None:
        return False
    if s.get("issuer_fp") != pki.fingerprint(pki.load_cert(inter.cert_pem)):
        return True
    return datetime.fromisoformat(s["not_after"]) - now < timedelta(days=RENEW_DAYS)


def directory(settings) -> Path:
    return Path(settings.data_dir) / "controller-client"


def _write_files(settings, cert_pem: str, key_pem: str) -> None:
    d = directory(settings)
    d.mkdir(parents=True, exist_ok=True)
    for name, data in (("cert.pem", cert_pem), ("key.pem", key_pem)):
        p = d / name
        tmp = d / (name + ".part")
        tmp.write_text(data, encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(p)


def ensure(db: Session, box: SecretBox, settings, now: datetime | None = None) -> bool:
    """Bei Bedarf (neu) ausstellen und die Dateien schreiben. True = neues Zertifikat.
    Ohne eingerichtete Zertifizierungsstelle passiert nichts. Commit macht der Aufrufer."""
    now = now or utcnow()
    s = stored(db)
    if not _due(db, s, now):
        if s and not (directory(settings) / "key.pem").exists():
            key = box.decrypt(s["key_enc"], KEY_CONTEXT).decode()
            _write_files(settings, s["cert_pem"], key)
        return False
    try:
        issuer = intermediate_keypair(db, box)
    except CAError:
        return False
    kp = pki.issue_client(
        issuer, cn=CN, org_unit="Controller", not_after=now + timedelta(days=VALID_DAYS), now=now
    )
    cert_pem = pki.cert_pem(kp.cert)
    key_pem = pki.key_pem(kp.key)
    value = {
        "cert_pem": cert_pem,
        "key_enc": box.encrypt(key_pem.encode(), KEY_CONTEXT),
        "fingerprint": pki.fingerprint(kp.cert),
        "not_after": kp.cert.not_valid_after_utc.isoformat(),
        "issuer_fp": pki.fingerprint(issuer.cert),
    }
    row = db.get(Setting, SETTING)
    if row is None:
        db.add(Setting(key=SETTING, value=value))
    else:
        row.value = value
    _write_files(settings, cert_pem, key_pem)
    log.info("Controller-Zertifikat ausgestellt (gültig bis %s)", value["not_after"][:10])
    return True


def ssl_context(settings) -> ssl.SSLContext | bool:
    """Für ausgehende HTTPS-Verbindungen: Standard-Prüfung plus eigenes Client-Zertifikat,
    falls vorhanden (sonst True = normale Prüfung ohne Zertifikat)."""
    d = directory(settings)
    cert, key = d / "cert.pem", d / "key.pem"
    if not (cert.exists() and key.exists()):
        return True
    ctx = ssl.create_default_context()
    try:
        ctx.load_cert_chain(str(cert), str(key))
    except (OSError, ssl.SSLError) as e:
        log.warning("Controller-Zertifikat nicht lesbar: %s", e)
        return True
    return ctx


async def watch(app, interval: float = 6 * 3600) -> None:
    """Regelmäßig prüfen und erneuern; ändert sich das Zertifikat, Config neu verteilen."""
    from tesseract.services import apply_all

    while True:
        try:
            with app.state.db.sessionmaker() as db:
                if ensure(db, app.state.secretbox, app.state.settings):
                    db.commit()
                    await asyncio.to_thread(
                        apply_all, db, app.state.settings, app.state.caddy_transport
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Controller-Zertifikat: Fehler")
        await asyncio.sleep(interval)
