"""Statistik ab 1.16: Verdichtung, gesamter Zeitraum, Rekorde, Clients, Karte, GeoIP-Städte."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tesseract import geoip, rollup
from tesseract.clients import classify
from tesseract.config import Settings
from tesseract.db.models import LogEntry, StatsDaily, StatsHourly, VisitorIp, utcnow
from tesseract.logs import Geo
from tests.test_geoip import _enc, tiny_mmdb
from tests.test_stats import _add

CHROME = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"


def test_classify() -> None:
    assert classify(CHROME) == ("browser", "Chrome")
    assert classify("Mozilla/5.0 (iPhone) AppleWebKit/605 Version/17 Safari/604") == (
        "browser",
        "Safari",
    )
    assert classify("Prometheus/2.51") == ("app", "Prometheus")
    assert classify("curl/8.5") == ("app", "curl")
    assert classify("Mozilla/5.0 (compatible; Googlebot/2.1)") == ("bot", "Googlebot")
    assert classify("") == ("bot", "ohne Kennung")
    assert classify("Mozilla/5.0 zgrab/0.x") == ("bot", "zgrab")
    assert classify("MeinWerkzeug/1") == ("app", "Sonstige")


def test_rollup_and_all_range(auth_client: TestClient) -> None:
    day = 60 * 24
    _add(
        auth_client,
        [
            {"ago": 2 * day, "user_agent": CHROME, "proto": "2", "encoding": "gzip"},
            {"ago": 2 * day, "user_agent": CHROME, "ip": "192.0.2.11", "status": 502},
            {"ago": 2 * day, "status": 403, "reason": "waf", "ip": "198.51.100.1"},
            {"ago": day + 60, "user_agent": "curl/8", "proto": "3", "size": 5000},
            {"ago": 5, "user_agent": CHROME},  # heute
        ],
    )
    with auth_client.app.state.db.sessionmaker() as db:
        assert rollup.run(db) >= 2
        db.commit()
        rows = db.scalars(select(StatsDaily)).all()
        assert sum(r.requests for r in rows) == 4  # heute noch nicht verdichtet
        assert sum(r.waf for r in rows) == 1 and sum(r.s5xx for r in rows) == 1
        assert any(r.clients.get("browser:Chrome") for r in rows)
        assert db.scalar(select(VisitorIp).where(VisitorIp.ip == "192.0.2.11")) is not None
        assert db.scalars(select(StatsHourly)).all()
        # erneut: nichts mehr zu tun
        assert rollup.run(db) == 0
        # Einzeleinträge weg (Aufbewahrung) – Tageswerte bleiben
        db.query(LogEntry).filter(LogEntry.ts < utcnow() - timedelta(hours=12)).delete()
        db.commit()
    d = auth_client.get("/api/stats/traffic", params={"range": "all"}).json()
    assert d["range"] == "all" and d["kpi"]["requests"] == 5
    assert d["kpi"]["errors"] == 1 and d["days"] >= 3
    assert sum(m["requests"] for m in d["months"]) == 5
    assert d["mix"]["proto"]["3"] > 0
    names = {c["name"]: c["kind"] for c in d["clients"]}
    assert names["Chrome"] == "browser" and names["curl"] == "app"
    rec = auth_client.get("/api/stats/records").json()
    assert rec["day"]["requests"] == 3 and rec["denied_hour"]["denied"] == 1


def test_traffic_extra(auth_client: TestClient) -> None:
    _add(
        auth_client,
        [
            {"user_agent": CHROME, "uri": "/a?x=1", "proto": "2", "encoding": "br"},
            {"user_agent": CHROME, "uri": "/a", "status": 500},
            {"user_agent": "Googlebot", "uri": "/robots.txt", "status": 404},
            {"ago": 60 * 30, "user_agent": CHROME},
        ],
    )
    d = auth_client.get("/api/stats/traffic").json()
    k = d["kpi"]
    assert k["requests"] == 3 and k["requests_prev"] == 1
    assert k["visitors"] == 1 and k["errors"] == 1
    assert d["composition"]["server"] == 1  # alte Felder bleiben
    assert d["mix"]["clients"]["bot"] > 0
    codes = {c["code"]: c for c in d["status_codes"]}
    assert codes["500"]["text"] == "Serverfehler"
    assert d["paths_top"][0]["path"] == "/a" and d["paths_top"][0]["count"] == 2
    assert {p["path"] for p in d["paths_errors"]} == {"/a", "/robots.txt"}


def test_security_extra(auth_client: TestClient) -> None:
    r = auth_client.put("/api/settings/general", json={"internal_networks": ["10.0.0.0/8"]})
    assert r.status_code == 200, r.text
    _add(
        auth_client,
        [
            {"status": 403, "reason": "mtls", "ip": "10.0.0.20"},
            {"status": 403, "reason": "ip", "ip": "198.51.100.7", "country": "US"},
            {"waf_rules": [942100]},  # nur erkannt
            {"ago": 60 * 30, "status": 403, "reason": "waf", "ip": "198.51.100.8"},
        ],
    )
    d = auth_client.get("/api/stats/security").json()
    assert d["previous"]["denied"] == 1 and d["waf_detected"] == 1
    flags = {t["ip"]: t for t in d["top_ips_flagged"]}
    assert flags["10.0.0.20"]["internal"] is True and flags["198.51.100.7"]["internal"] is False
    assert any(h["denied"] for h in d["hourly_all"])


def test_geo_endpoint(auth_client: TestClient) -> None:
    _add(
        auth_client,
        [
            {
                "country": "DE",
                "city": "Karlsruhe",
                "lat": 49.01,
                "lon": 8.4,
                "asn": 3320,
                "as_org": "Deutsche Telekom AG",
            },
            {
                "country": "DE",
                "city": "Karlsruhe",
                "lat": 49.01,
                "lon": 8.4,
                "asn": 3320,
                "as_org": "Deutsche Telekom AG",
                "status": 403,
                "reason": "waf",
            },
            {"country": "US"},
            {"ip": "10.0.0.1"},
        ],
    )
    d = auth_client.get("/api/stats/geo").json()
    assert d["countries"][0] == {"country": "DE", "count": 2}
    assert d["cities"][0]["city"] == "Karlsruhe" and d["cities"][0]["count"] == 2
    assert d["asns"][0] == {"asn": 3320, "org": "Deutsche Telekom AG", "count": 2}
    assert d["unknown"] == 1
    den = auth_client.get("/api/stats/geo", params={"which": "denied"}).json()
    assert den["countries"] == [{"country": "DE", "count": 1}]


def _enc2(v) -> bytes:
    """Wie `_enc`, zusätzlich Kommazahlen (double) und längere Schlüssel."""
    import struct

    if isinstance(v, float):
        return bytes([0x60 | 8]) + struct.pack(">d", v)
    if isinstance(v, str) and len(v.encode()) >= 29:
        b = v.encode()
        return bytes([0x40 | 29, len(b) - 29]) + b
    if isinstance(v, dict):
        return bytes([0xE0 | len(v)]) + b"".join(_enc2(k) + _enc2(x) for k, x in v.items())
    return _enc(v)


def _mmdb(record: dict, db_type: str) -> bytes:
    raw = tiny_mmdb()
    old = _enc({"country": {"iso_code": "DE"}})
    new = _enc2(record)
    return raw.replace(old, new).replace(_enc("Test-Country"), _enc(db_type))


def test_geo_lookup_city_and_asn(tmp_path) -> None:
    city = tmp_path / "city.mmdb"
    city.write_bytes(
        _mmdb(
            {
                "country": {"iso_code": "DE"},
                "city": {"names": {"en": "Karlsruhe"}},
                "location": {"latitude": 49.0069, "longitude": 8.4037},
            },
            "DBIP-City-Lite",
        )
    )
    asn = tmp_path / "asn.mmdb"
    asn.write_bytes(
        _mmdb(
            {"autonomous_system_number": ("u32", 3320), "autonomous_system_organization": "DTAG"},
            "DBIP-ASN-Lite",
        )
    )
    g = Geo(city, asn)
    assert g.cities and g.asn
    w = g.lookup("185.1.2.3")
    assert w["country"] == "DE" and w["city"] == "Karlsruhe"
    assert w["asn"] == 3320 and w["as_org"] == "DTAG"
    assert g.lookup("10.0.0.1")["country"] is None


def test_geoip_auto_values(tmp_path) -> None:
    assert Settings(geoip_auto="dbip-city+asn").geoip_auto == "dbip-city,asn"
    assert Settings(geoip_auto="DBIP, asn").geoip_auto == "dbip,asn"
    with pytest.raises(ValueError):
        Settings(geoip_auto="dbip+city")
    s = Settings(data_dir=tmp_path, geoip_auto="dbip-city,asn")
    assert geoip.kinds(s) == ["city", "asn"]
    assert geoip.path(s).name == "dbip-city-lite.mmdb"
    assert geoip.path(Settings(data_dir=tmp_path, geoip_auto="dbip")).name == geoip.FILE


def test_geo_country_filter(auth_client: TestClient) -> None:
    _add(
        auth_client,
        [
            {
                "country": "DE",
                "city": "Berlin",
                "lat": 52.52,
                "lon": 13.4,
                "asn": 3320,
                "as_org": "DTAG",
                "host": "a.example.org",
            },
            {
                "country": "DE",
                "city": "Berlin",
                "lat": 52.52,
                "lon": 13.4,
                "status": 403,
                "reason": "mtls",
                "host": "b.example.org",
            },
            {
                "country": "US",
                "city": "Ashburn",
                "lat": 39.04,
                "lon": -77.49,
                "asn": 16509,
                "as_org": "Amazon",
            },
        ],
    )
    d = auth_client.get("/api/stats/geo", params={"country": "de"}).json()
    assert [c["city"] for c in d["cities"]] == ["Berlin"]
    assert [a["asn"] for a in d["asns"]] == [3320]
    sel = d["selected"]
    assert sel["country"] == "DE" and sel["requests"] == 2 and sel["denied"] == 1
    assert {h["host"] for h in sel["hosts"]} == {"a.example.org", "b.example.org"}
    assert auth_client.get("/api/stats/geo").json()["selected"] is None
    assert auth_client.get("/api/stats/geo", params={"country": "DEU"}).status_code == 422
