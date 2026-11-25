"""robots.txt pro Host: Vorlagen, Prüfung, Caddy-Route, Einstellungen, Docker-Label."""

import pytest
from fastapi.testclient import TestClient

from tesseract import robots
from tesseract.caddy.config import HostSpec, NodeSpec, build_config
from tesseract.dockerlabels import LabelError, parse
from tests.conftest import FakeCaddy
from tests.test_mtls import HOST, _setup


def _host_routes(caddy: FakeCaddy, domain: str) -> list[dict]:
    for r in caddy.last["apps"]["http"]["servers"]["https"]["routes"]:
        if r.get("match", [{}])[0].get("host") == [domain]:
            return r["handle"][0]["routes"]
    raise AssertionError(domain)


def _robots(routes: list[dict]) -> str | None:
    for r in routes:
        if r.get("match", [{}])[0].get("path") == ["/robots.txt"]:
            return r["handle"][0]["body"]
    return None


def test_templates() -> None:
    assert robots.render("off") == ""
    assert robots.render("deny") == "User-agent: *\nDisallow: /\n"
    assert robots.render("allow", sitemap="https://a.de/s.xml").endswith(
        "Allow: /\n\nSitemap: https://a.de/s.xml\n"
    )
    ai = robots.render("deny_ai", ai_bots=["GPTBot", "ClaudeBot"])
    assert ai.startswith("User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n")
    assert ai.rstrip().endswith("User-agent: *\nAllow: /")
    assert "GPTBot" in robots.render("deny_ai")  # Standardliste
    assert robots.render("paths", paths=["admin", "/api"]) == (
        "User-agent: *\nDisallow: /admin\nDisallow: /api\n"
    )
    assert robots.render("custom", text="User-agent: *\r\nDisallow: /x\n\n") == (
        "User-agent: *\nDisallow: /x\n"
    )


def test_check() -> None:
    ok = robots.check("# Kommentar\nUser-agent: *\nDisallow: /\nSitemap: https://a.de/s.xml\n")
    assert ok.errors == [] and ok.warnings == []
    bad = robots.check("Disallow: /\nkaputt\nUser-agent: *\nCrawl-delay: bald\nFoo: bar")
    assert any("vor dem ersten User-agent" in e for e in bad.errors)
    assert any("Zeile 2" in e for e in bad.errors)
    assert any("Crawl-delay" in e for e in bad.errors)
    assert any("Foo" in w for w in bad.warnings)
    assert robots.check("User-agent: *\nSitemap: /s.xml").errors


def test_caddy_route_first_and_internal_before() -> None:
    spec = NodeSpec(
        admin_listen="localhost:2019",
        hosts=[
            HostSpec(
                id=1,
                domain="a.example.org",
                upstream_scheme="http",
                upstream_host="10.0.0.1",
                upstream_port=80,
                robots="User-agent: *\nDisallow: /\n",
                internal=True,
            )
        ],
    )
    routes = build_config(spec)["apps"]["http"]["servers"]["https"]["routes"][0]["handle"][0][
        "routes"
    ]
    assert routes[0]["handle"][0].get("abort") is True  # „nur intern“ bleibt vorne
    assert routes[1]["match"][0]["path"] == ["/robots.txt"]
    assert routes[1]["handle"][0]["headers"]["Content-Type"] == ["text/plain; charset=utf-8"]


def test_host_api(auth_client: TestClient, caddy: FakeCaddy) -> None:
    r = auth_client.post("/api/hosts", json={**HOST, "robots": "deny_ai"})
    assert r.status_code == 201, r.text
    host = r.json()["host"]
    assert host["robots"] == "deny_ai"
    assert "User-agent: GPTBot" in _robots(_host_routes(caddy, "fotos.example.org"))

    # eigener Text mit Fehler → 422
    bad = {**HOST, "robots": "custom", "robots_text": "Disallow: /"}
    r = auth_client.put(f"/api/hosts/{host['id']}", json=bad)
    assert r.status_code == 422 and "User-agent" in r.text

    good = {**HOST, "robots": "custom", "robots_text": "User-agent: *\nDisallow: /privat"}
    r = auth_client.put(f"/api/hosts/{host['id']}", json=good)
    assert r.status_code == 200, r.text
    assert _robots(_host_routes(caddy, "fotos.example.org")) == "User-agent: *\nDisallow: /privat\n"

    # ohne Angabe bleibt der Modus beim Ändern unverändert
    r = auth_client.put(f"/api/hosts/{host['id']}", json={**HOST, "robots_text": "x"})
    assert r.json()["host"]["robots"] == "custom"

    r = auth_client.put(f"/api/hosts/{host['id']}", json={**HOST, "robots": "off"})
    assert _robots(_host_routes(caddy, "fotos.example.org")) is None


def test_preview(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/hosts/robots/preview", json={"robots": "paths", "robots_paths": ["/a"]}
    )
    assert r.json()["text"] == "User-agent: *\nDisallow: /a\n" and r.json()["errors"] == []
    r = auth_client.post("/api/hosts/robots/preview", json={"robots": "off", "access": "mtls"})
    assert r.json()["from_settings"] is True and "Disallow: /" in r.json()["text"]
    r = auth_client.post("/api/hosts/robots/preview", json={"robots": "custom", "robots_text": "?"})
    assert r.json()["errors"]


def test_settings_default_and_mtls(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    # Standard: mTLS-Hosts ohne eigene Einstellung bekommen „alles verbieten“
    r = auth_client.post(
        "/api/hosts",
        json={
            **HOST,
            "access": "mtls",
            "no_cert_action": "hint",
            "grant_person_ids": [ids["ben"]["id"]],
        },
    )
    assert r.status_code == 201, r.text
    assert _robots(_host_routes(caddy, "fotos.example.org")) == "User-agent: *\nDisallow: /\n"

    r = auth_client.put(
        "/api/settings/general",
        json={"robots_mtls_deny": False, "robots_default": "deny_ai", "robots_ai_bots": ["GPTBot"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["robots_ai_bots"] == ["GPTBot"] and r.json()["robots_default"] == "deny_ai"
    assert _robots(_host_routes(caddy, "fotos.example.org")) is None

    # neue Hosts bekommen den Standard aus den Einstellungen
    r = auth_client.post("/api/hosts", json={**HOST, "domain": "neu.example.org"})
    assert r.json()["host"]["robots"] == "deny_ai"
    assert _robots(_host_routes(caddy, "neu.example.org")) == (
        "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    )

    r = auth_client.put("/api/settings/general", json={"robots_ai_bots": ["Böser Bot"]})
    assert r.status_code == 422


def test_docker_label() -> None:
    c = {
        "name": "app",
        "ports": [80],
        "labels": {"tesseract.domain": "a.de", "tesseract.robots": "deny-ai"},
    }
    assert parse(c, {}, {})["robots"] == "deny_ai"
    c["labels"]["tesseract.robots"] = "vielleicht"
    with pytest.raises(LabelError):
        parse(c, {}, {})
