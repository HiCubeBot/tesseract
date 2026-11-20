"""GeoIP-Datenbank automatisch herunterladen (TESSERACT_GEOIP_AUTO=dbip)."""

import gzip
import struct
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from tesseract import geoip
from tesseract.config import Settings


def _enc(v) -> bytes:
    """Minimaler MaxMind-DB-Encoder (Strings, Zahlen mit Typ, Maps, Listen)."""
    if isinstance(v, str):
        b = v.encode()
        return bytes([0x40 | len(b)]) + b
    if isinstance(v, tuple):  # (Typ, Zahl) – die Metadaten verlangen feste Typen
        kind, n = v
        b = n.to_bytes(max(1, (n.bit_length() + 7) // 8), "big") if n else b""
        return {
            "u16": bytes([0xA0 | len(b)]),
            "u32": bytes([0xC0 | len(b)]),
            "u64": bytes([0x00 | len(b), 0x02]),
        }[kind] + b
    if isinstance(v, dict):
        return bytes([0xE0 | len(v)]) + b"".join(_enc(k) + _enc(x) for k, x in v.items())
    if isinstance(v, list):
        return bytes([0x00 | len(v), 0x04]) + b"".join(_enc(x) for x in v)
    raise TypeError(v)


def tiny_mmdb() -> bytes:
    """Gültige IPv4-Datenbank mit einem Knoten: 0.0.0.0/1 unbekannt, 128.0.0.0/1 → DE."""
    data = _enc({"country": {"iso_code": "DE"}})
    # Zweig 0 → node_count (= nicht gefunden), Zweig 1 → Daten (node_count + 16 + Offset 0)
    tree = struct.pack(">I", 1)[1:] + struct.pack(">I", 1 + 16)[1:]
    meta = {
        "node_count": ("u32", 1),
        "record_size": ("u16", 24),
        "ip_version": ("u16", 4),
        "database_type": "Test-Country",
        "languages": ["de"],
        "binary_format_major_version": ("u16", 2),
        "binary_format_minor_version": ("u16", 0),
        "build_epoch": ("u64", 1_700_000_000),
        "description": {"de": "Test"},
    }
    return tree + b"\x00" * 16 + data + b"\xab\xcd\xefMaxMind.com" + _enc(meta)


def test_settings() -> None:
    assert Settings(geoip_auto="DBIP").geoip_auto == "dbip"
    assert Settings(geoip_auto="aus").geoip_auto == ""
    with pytest.raises(ValueError):
        Settings(geoip_auto="maxmind")


def test_download_falls_back_to_previous_month(tmp_path) -> None:
    s = Settings(data_dir=tmp_path, geoip_auto="dbip")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if "2026-12" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, content=gzip.compress(tiny_mmdb()))

    now = datetime(2026, 12, 1, tzinfo=UTC)
    assert geoip.due(s, now)
    info = geoip.download(s, httpx.MockTransport(handler), now)
    assert seen == [
        "/free/dbip-country-lite-2026-12.mmdb.gz",
        "/free/dbip-country-lite-2026-11.mmdb.gz",
    ]
    assert info["month"] == "2026-12" and info["file_month"] == "2026-11"
    assert geoip.path(s).exists() and not geoip.due(s, now)
    assert geoip.due(s, datetime(2027, 1, 2, tzinfo=UTC))
    assert geoip.initial_path(s) == geoip.path(s)


def test_broken_download_keeps_old_file(tmp_path) -> None:
    s = Settings(data_dir=tmp_path, geoip_auto="dbip")
    ok = httpx.MockTransport(lambda r: httpx.Response(200, content=gzip.compress(tiny_mmdb())))
    geoip.download(s, ok, datetime(2026, 11, 5, tzinfo=UTC))
    before = geoip.path(s).read_bytes()
    bad = httpx.MockTransport(lambda r: httpx.Response(200, content=gzip.compress(b"kaputt")))
    with pytest.raises(geoip.GeoIPError, match="keine gültige Datenbank"):
        geoip.download(s, bad, datetime(2026, 12, 5, tzinfo=UTC))
    assert geoip.path(s).read_bytes() == before
    with pytest.raises(geoip.GeoIPError, match="gzip"):
        geoip.download(s, httpx.MockTransport(lambda r: httpx.Response(200, content=b"x")))


def test_api_update_and_status(auth_client: TestClient, tmp_path) -> None:
    app = auth_client.app
    r = auth_client.post("/api/settings/observability/geoip-update")
    assert r.status_code == 409  # ohne TESSERACT_GEOIP_AUTO
    obs = auth_client.get("/api/settings/observability").json()
    assert obs["geoip"] is False and obs["geoip_auto"]["auto"] is None

    app.state.settings.geoip_auto = "dbip"
    app.state.geoip_transport = httpx.MockTransport(
        lambda r: httpx.Response(200, content=gzip.compress(tiny_mmdb()))
    )
    r = auth_client.post("/api/settings/observability/geoip-update")
    assert r.status_code == 200, r.text
    obs = auth_client.get("/api/settings/observability").json()
    # ohne Neustart übernommen
    assert obs["geoip"] is True
    assert app.state.logs.geo.country("200.1.2.3") == "DE"
    assert obs["geoip_auto"]["attribution"] == "IP Geolocation by DB-IP"
    assert obs["geoip_auto"]["updated_at"]

    app.state.geoip_transport = httpx.MockTransport(lambda r: httpx.Response(500))
    assert auth_client.post("/api/settings/observability/geoip-update").status_code == 502
    obs = auth_client.get("/api/settings/observability").json()
    assert "500" in obs["geoip_auto"]["error"] and obs["geoip"] is True


def test_dns_filter_hint(tmp_path) -> None:
    s = Settings(data_dir=tmp_path, geoip_auto="dbip")

    def blocked(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("getaddrinfo failed")

    with pytest.raises(geoip.GeoIPError, match="AdGuard"):
        geoip.download(s, httpx.MockTransport(blocked))
