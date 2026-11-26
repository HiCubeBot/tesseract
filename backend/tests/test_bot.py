"""Bot-Schutz mit Anubis: Caddy-Routen, Ausnahmen, Einstellungen, Statistik."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tesseract.caddy.config import (
    ANUBIS_CHECK,
    FINGERPRINT,
    BotContext,
    HostSpec,
    NodeSpec,
    anubis_routes,
    build_config,
)
from tesseract.db.models import LogEntry, Node, utcnow
from tesseract.dockerlabels import parse
from tests.conftest import FakeCaddy
from tests.test_mtls import HOST

ROOT = Path(__file__).resolve().parents[2]


def _spec(**kw) -> HostSpec:
    return HostSpec(
        id=1,
        domain="blog.example.org",
        upstream_scheme="http",
        upstream_host="10.0.0.5",
        upstream_port=80,
        **{"bot_protection": True, **kw},
    )


def test_routes_forward_auth() -> None:
    ctx = BotContext(url="http://anubis:8923")
    assets, guarded = anubis_routes(_spec(), ctx)
    # Prüfseite und Skripte gehen direkt an Anubis
    assert assets["match"] == [{"path": ["/.within.website/*"]}]
    assert assets["handle"][0]["upstreams"] == [{"dial": "anubis:8923"}]
    check = guarded["handle"][0]
    assert check["rewrite"] == {"method": "GET", "uri": ANUBIS_CHECK}
    sets = check["headers"]["request"]["set"]
    assert sets["X-Forwarded-Uri"] == ["{http.request.uri}"]
    assert sets["X-Real-Ip"] == ["{http.vars.client_ip}"]
    responses = {json.dumps(r["match"]): r for r in check["handle_response"]}
    # 401 → Prüfseite, mit Grund „bot“ im Log
    challenge = responses['{"status_code": [401]}']["routes"][0]["handle"][0]
    assert challenge["status_code"] == 307
    assert challenge["headers"]["Location"] == ["/.within.website/?redir={http.request.uri}"]
    assert challenge["_tesseract_reason"] == "bot"
    # 2xx → weiter zum Dienst (keine eigene Antwort)
    assert responses['{"status_code": [2]}']["routes"][0]["handle"] == [{"handler": "vars"}]
    # 403 & Co. → Anubis' Antwort an den Client
    deny = responses['{"status_code": [4, 5]}']["routes"][0]["handle"][0]
    assert deny["handler"] == "copy_response"
    assert "match" not in guarded  # ohne Ausnahmen gilt der Schutz für alles


def test_routes_exceptions() -> None:
    ctx = BotContext(
        url="https://anubis.example.org",
        allow_agents=("Uptime-Kuma", "Googlebot"),
        skip_networks=("192.168.178.0/24",),
    )
    spec = _spec(
        bot_paths=("/blog",),
        bot_exempt=("/api", "/feed.xml"),
        allowed=(("ab" * 32, "PEM"),),
    )
    _, guarded = anubis_routes(spec, ctx)
    m = guarded["match"][0]
    assert m["path"] == ["/blog", "/blog/*"]
    skip = m["not"]
    assert {"path": ["/api", "/api/*", "/feed.xml", "/feed.xml/*"]} in skip
    assert {"vars": {FINGERPRINT: ["ab" * 32]}} in skip
    assert {"remote_ip": {"ranges": ["192.168.178.0/24"]}} in skip
    assert {"header_regexp": {"User-Agent": {"pattern": "(?i)(Uptime\\-Kuma|Googlebot)"}}} in skip
    # https-Anubis über TLS
    assert guarded["handle"][0]["transport"] == {"protocol": "http", "tls": {}}


def test_missing_anubis_fails_closed() -> None:
    (route,) = anubis_routes(_spec(), BotContext())
    assert route["handle"][0]["status_code"] == 503 and route["terminal"]
    assert anubis_routes(_spec(bot_protection=False), BotContext(url="http://a:1")) == []


def test_chain_order() -> None:
    """IP-Filter → Zertifikat → WAF → Bot-Schutz → Authelia → Dienst."""
    spec = NodeSpec(
        admin_listen="x",
        hosts=[_spec(waf_mode="block", authelia=True)],
        anubis_url="http://anubis:8923",
        authelia_url="http://authelia:9091",
    )
    routes = build_config(spec)["apps"]["http"]["servers"]["https"]["routes"][0]["handle"][0][
        "routes"
    ]
    kinds = []
    for r in routes:
        h = r["handle"][-1]
        uri = h.get("rewrite", {}).get("uri", "")
        kinds.append(
            "waf"
            if h["handler"] == "waf"
            else "anubis"
            if uri == ANUBIS_CHECK or r.get("match") == [{"path": ["/.within.website/*"]}]
            else "authelia"
            if "authz" in uri
            else h["handler"]
        )
    assert kinds.index("waf") < kinds.index("anubis") < kinds.index("authelia")


def test_host_api_and_settings(auth_client: TestClient, caddy: FakeCaddy) -> None:
    # ohne Anubis-Adresse lässt sich der Schutz nicht einschalten
    r = auth_client.post("/api/hosts", json={**HOST, "bot_protection": True})
    assert r.status_code == 409 and "Anubis" in r.text

    r = auth_client.put(
        "/api/settings/general",
        json={
            "anubis_url": "http://anubis:8923/",
            "bot_allow_agents": ["Uptime-Kuma"],
            "bot_skip_internal": False,
        },
    )
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["anubis_url"] == "http://anubis:8923" and g["bot_allow_agents"] == ["Uptime-Kuma"]
    assert g["bot_skip_internal"] is False
    bad = auth_client.put("/api/settings/general", json={"anubis_url": "anubis; rm -rf"})
    assert bad.status_code == 422

    r = auth_client.post(
        "/api/hosts",
        json={**HOST, "bot_protection": True, "bot_exempt": ["api", "/webdav"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["host"]["bot_exempt"] == ["/api", "/webdav"]
    text = json.dumps(caddy.last)
    assert ANUBIS_CHECK in text and "Uptime" in text


def test_docker_label() -> None:
    c = {
        "name": "app",
        "ports": [80],
        "labels": {"tesseract.domain": "a.de", "tesseract.bot": "true"},
    }
    assert parse(c, {}, {})["bot_protection"] is True


def test_security_stats_bot(auth_client: TestClient) -> None:
    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        node = db.query(Node).first()

        def log(uri: str, status: int, reason: str) -> None:
            db.add(
                LogEntry(
                    ts=utcnow(),
                    node_id=node.id,
                    host="blog.example.org",
                    uri=uri,
                    status=status,
                    ip="198.51.100.9",
                    reason=reason,
                    waf_rules=[],
                )
            )

        log("/", 307, "bot")
        log("/x", 307, "bot")
        log("/", 403, "bot")
        log("/.within.website/x/cmd/anubis/api/pass-challenge?result=x", 302, "ok")
        db.commit()
    s = auth_client.get("/api/stats/security?range=24h").json()
    assert s["bot"] == {"challenged": 2, "denied": 1, "passed": 1}
    assert s["denied"] == 3


def test_compose_has_anubis_with_deny_403() -> None:
    for f in (ROOT / "compose.yaml", ROOT / "backend/src/tesseract/install/node-compose.yaml"):
        text = f.read_text(encoding="utf-8")
        assert "ghcr.io/techarohq/anubis:" in text and 'TARGET: " "' in text
        assert "DENY: 403" in text and "DENY: 200" not in text
        # Inline-Config (configs: content) geht nicht in einen read_only-Container
        service = text.split("  anubis:\n", 1)[1].split("    configs:", 1)[0]
        assert "read_only: true" not in service


def test_bot_statistics(auth_client: TestClient) -> None:
    from datetime import timedelta

    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        node = db.query(Node).first()

        def log(ip, uri, status, reason, ua="Mozilla/5.0 Firefox", host="blog.example.org", ago=0):
            db.add(
                LogEntry(
                    ts=utcnow() - timedelta(hours=ago),
                    node_id=node.id,
                    host=host,
                    uri=uri,
                    status=status,
                    ip=ip,
                    reason=reason,
                    waf_rules=[],
                    user_agent=ua,
                    country="DE",
                )
            )

        pas = "/.within.website/x/cmd/anubis/api/pass-challenge?result=x"
        log("198.51.100.1", "/", 307, "bot")  # Mensch: geprüft …
        log("198.51.100.1", pas, 302, "ok")  # … und bestanden
        log("198.51.100.2", "/", 307, "bot")  # nie bestanden
        log("198.51.100.2", "/x", 307, "bot")
        db.add(
            LogEntry(
                ts=utcnow(),
                node_id=node.id,
                host="blog.example.org",
                uri="/y",
                status=307,
                ip="198.51.100.2",
                reason="bot",
                waf_rules=[],
                user_agent="Mozilla/5.0 Firefox",
                country="NL",
            )
        )
        log("198.51.100.3", "/", 403, "bot", ua="GPTBot/1.2")  # abgewiesen
        log("198.51.100.4", pas, 403, "ok")  # Lösung falsch
        log("198.51.100.9", "/", 307, "bot", ago=30)  # Vorzeitraum
        db.commit()

    s = auth_client.get("/api/stats/bots?range=24h").json()
    assert s["totals"] == {"challenged": 4, "denied": 1, "passed": 1, "failed": 1}
    assert s["previous"]["challenged"] == 1
    assert s["pass_rate"] == 25.0
    assert s["visitors"] == {"challenged": 2, "passed": 1, "never_passed": 1, "denied": 1}
    assert s["by_host"][0]["host"] == "blog.example.org" and s["by_host"][0]["passed"] == 1
    gpt = next(a for a in s["agents"] if a["user_agent"].startswith("GPTBot"))
    assert gpt["denied"] == 1 and gpt["kind"] == "bot"
    assert s["countries"] == [{"country": "DE", "count": 4}, {"country": "NL", "count": 1}]
    assert {i["ip"]: i["passed"] for i in s["top_ips"]}["198.51.100.1"] is True
    assert s["anubis"] is False and s["protected_hosts"] == []
    assert len(s["hourly"]) >= 1
    # je IP nur ein Eintrag, auch wenn das Land wechselt
    ips = [i["ip"] for i in s["top_ips"]]
    assert len(ips) == len(set(ips))
