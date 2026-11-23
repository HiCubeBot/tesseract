"""GeoIP-Datenbank automatisch herunterladen und aktuell halten (optional).

Mit `TESSERACT_GEOIP_AUTO=dbip` holt der Controller monatlich „IP to Country Lite“ von DB-IP
(ohne Konto, Lizenz CC BY 4.0 – Quellenangabe „IP Geolocation by DB-IP“) und übernimmt sie
ohne Neustart. Standard ist aus: Ohne diese Einstellung geht keine Anfrage nach außen, und die
Datenbank kommt wie bisher aus `TESSERACT_GEOIP_DB`.

- `dbip-city` statt `dbip`: „IP to City Lite“ (Land, Stadt, Koordinaten – für die Karte mit
  Städten; gut 100 MB statt 8 MB)
- `+asn` dazu (z. B. `dbip+asn`): „IP to ASN Lite“ für die Netzbetreiber
- Ablage: `<data_dir>/geoip/dbip-…-lite.mmdb` (+ `.json` mit Monat und Zeitpunkt)
- Anfang des Monats gibt es die neue Datei evtl. noch nicht – dann gilt die vom Vormonat.
- Schlägt ein Download fehl, bleibt die vorhandene Datenbank in Gebrauch.
"""

import gzip
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("tesseract.geoip")

URL = "https://download.db-ip.com/free/{name}-{month}.mmdb.gz"
# Art → Dateiname bei DB-IP
NAMES = {"country": "dbip-country-lite", "city": "dbip-city-lite", "asn": "dbip-asn-lite"}
FILE = "dbip-country-lite.mmdb"
SOURCES = ("dbip", "dbip-city")
ATTRIBUTION = "IP Geolocation by DB-IP"
CHECK_EVERY = 6 * 3600.0
MAX_SIZE = 200 * 1024 * 1024


class GeoIPError(Exception):
    pass


def directory(settings) -> Path:
    return Path(settings.data_dir) / "geoip"


def kinds(settings) -> list[str]:
    """Welche Dateien geholt werden: Land oder Stadt, wahlweise ASN dazu."""
    parts = (settings.geoip_auto or "").split(",")
    out = ["city" if "dbip-city" in parts else "country"] if parts[0] else []
    if "asn" in parts:
        out.append("asn")
    return out


def _file(kind: str) -> str:
    return NAMES[kind] + ".mmdb"


def path(settings, kind: str | None = None) -> Path:
    """Datei einer Art; ohne Angabe die Haupt-Datenbank (Land bzw. Stadt)."""
    if kind is None:
        k = kinds(settings)
        kind = k[0] if k else "country"
    return directory(settings) / _file(kind)


def asn_path(settings) -> Path | None:
    if "asn" in kinds(settings) and path(settings, "asn").exists():
        return path(settings, "asn")
    return settings.geoip_asn_db


def meta(settings, kind: str | None = None) -> dict[str, Any]:
    f = path(settings, kind).name + ".json"
    try:
        return json.loads((directory(settings) / f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _month(d: datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _previous(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def due(settings, now: datetime | None = None) -> bool:
    """Neu holen, wenn keine Datei da ist oder sie aus einem früheren Monat stammt."""
    now = now or datetime.now(UTC)
    for kind in kinds(settings):
        if not path(settings, kind).exists() or meta(settings, kind).get("month", "") < _month(now):
            return True
    return False


def _validate(data: bytes) -> None:
    """Öffnet die Datei probeweise (maxminddb liest aus Dateien – daher eine Temp-Datei)."""
    import tempfile

    import maxminddb

    with tempfile.NamedTemporaryFile(suffix=".mmdb", delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        reader = maxminddb.open_database(tmp)
        reader.close()
    except Exception as e:
        raise GeoIPError(f"Heruntergeladene Datei ist keine gültige Datenbank: {e}") from e
    finally:
        os.unlink(tmp)


def download(settings, transport: httpx.BaseTransport | None = None, now=None) -> dict[str, Any]:
    """Alle eingestellten Dateien holen; Rückgabe: Angaben zur Haupt-Datenbank."""
    now = now or datetime.now(UTC)
    infos = [_download(settings, kind, transport, now) for kind in kinds(settings) or ["country"]]
    return infos[0]


def _download(settings, kind: str, transport, now: datetime) -> dict[str, Any]:
    """Aktuelle (sonst die vom Vormonat) Datei holen, prüfen und atomar ablegen."""
    month = _month(now)
    last_error = ""
    with httpx.Client(transport=transport, timeout=120.0, follow_redirects=True) as c:
        for m in (month, _previous(month)):
            try:
                r = c.get(URL.format(name=NAMES[kind], month=m))
            except httpx.ConnectError as e:
                # häufigster Grund im Heimnetz: Pi-hole/AdGuard sperrt die Domain (0.0.0.0)
                raise GeoIPError(
                    f"DB-IP nicht erreichbar ({e}) – blockiert ein DNS-Filter wie Pi-hole oder "
                    "AdGuard download.db-ip.com? Dann dort freigeben"
                ) from e
            except httpx.HTTPError as e:
                raise GeoIPError(f"DB-IP nicht erreichbar: {e}") from e
            if r.status_code == 404:
                last_error = f"{m} noch nicht verfügbar"
                continue
            if r.status_code >= 300:
                raise GeoIPError(f"DB-IP antwortet {r.status_code}")
            try:
                data = gzip.decompress(r.content)
            except (OSError, EOFError) as e:
                raise GeoIPError("Download ist kein gültiges gzip") from e
            if len(data) > MAX_SIZE:
                raise GeoIPError("Datei ist unerwartet groß")
            _validate(data)
            d = directory(settings)
            d.mkdir(parents=True, exist_ok=True)
            target = path(settings, kind)
            tmp = d / (target.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
            info = {
                "source": "dbip",
                "kind": kind,
                # gilt als aktuell für den laufenden Monat, auch wenn es die vom Vormonat ist
                "month": month,
                "file_month": m,
                "at": now.isoformat(timespec="seconds"),
                "size": len(data),
            }
            (d / (target.name + ".json")).write_text(json.dumps(info), encoding="utf-8")
            log.info("GeoIP-Datenbank %s von DB-IP geladen (%s, %d Bytes)", kind, m, len(data))
            return info
    raise GeoIPError(f"Keine Datei bei DB-IP gefunden ({last_error})")


def initial_path(settings):
    """Welche Datenbank beim Start geladen wird: die automatische, sonst TESSERACT_GEOIP_DB."""
    if settings.geoip_auto and path(settings).exists():
        return path(settings)
    return settings.geoip_db


def status(app) -> dict[str, Any]:
    settings = app.state.settings
    st = getattr(app.state, "geoip_status", None) or {}
    m = meta(settings) if settings.geoip_auto else {}
    return {
        "auto": settings.geoip_auto or None,
        "updated_at": m.get("at"),
        "file_month": m.get("file_month"),
        "error": st.get("error"),
        "attribution": ATTRIBUTION if settings.geoip_auto else None,
        "kinds": kinds(settings),
    }


def _swap(app, p: Path) -> None:
    """Neue Datenbank ohne Neustart übernehmen."""
    from tesseract.logs import Geo

    new = Geo(p, asn_path(app.state.settings))
    if new.ready:
        # den alten Reader nicht schließen – ein laufender Abgleich könnte ihn noch nutzen;
        # er wird freigegeben, sobald niemand mehr darauf verweist
        app.state.logs.geo = new


def refresh(app, transport=None) -> dict[str, Any] | None:
    """Wenn fällig: herunterladen und übernehmen. Fehler landen im Status, nicht als Ausnahme."""
    settings = app.state.settings
    if not settings.geoip_auto:
        return None
    if not due(settings):
        if not app.state.logs.geo.ready and path(settings).exists():
            _swap(app, path(settings))
        return None
    try:
        info = download(settings, transport)
    except GeoIPError as e:
        app.state.geoip_status = {"error": str(e)}
        log.warning("GeoIP-Download: %s", e)
        return None
    app.state.geoip_status = {"error": None}
    _swap(app, path(settings))
    return info


async def watch(app, interval: float = CHECK_EVERY) -> None:
    import asyncio

    while True:
        try:
            await asyncio.to_thread(refresh, app, getattr(app.state, "geoip_transport", None))
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("GeoIP: Fehler beim Aktualisieren")
        await asyncio.sleep(interval)
