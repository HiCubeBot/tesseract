"""WAF-Regel-Katalog, Treffer und zentrale Ausnahmen (wafrules.py, api/waf.py)."""

import json
import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tesseract import wafrules
from tesseract.caddy.config import waf_directives
from tesseract.db.models import Host, LogEntry, Node, WafException, utcnow
from tests.conftest import FakeCaddy
from tests.test_mtls import HOST

ROOT = Path(__file__).resolve().parents[2]


def _directives(caddy: FakeCaddy, domain: str = "fotos.example.org") -> str:
    for r in caddy.last["apps"]["http"]["servers"]["https"]["routes"]:
        if r.get("match", [{}])[0].get("host") == [domain]:
            for x in r["handle"][0]["routes"]:
                for h in x.get("handle", []):
                    if h.get("handler") == "waf":
                        return h["directives"]
    raise AssertionError("kein WAF-Handler")


# ---------- Katalog ----------


def test_catalog_matches_caddy_image() -> None:
    """Der Katalog im Repository passt zur coraza-caddy-Version im Caddy-Image."""
    sys.path.insert(0, str(ROOT / "backend" / "scripts"))
    import crs_catalog

    cat = wafrules.catalog()
    assert cat["coraza_caddy"] == crs_catalog.coraza_caddy_version(), (
        "docker/caddy/Dockerfile hat eine andere CORAZA_CADDY_VERSION – "
        "python backend/scripts/crs_catalog.py ausführen"
    )
    rule = wafrules.rules_by_id()[942100]
    assert rule["category"] == "SQL-Injection" and rule["paranoia"] == 1
    assert "libinjection" in rule["msg"] and rule["severity"] == "CRITICAL"
    assert len(cat["rules"]) > 200


def test_catalog_parser() -> None:
    sys.path.insert(0, str(ROOT / "backend" / "scripts"))
    import crs_catalog

    text = (
        'SecRule ARGS "@detectSQLi" \\\n'
        '    "id:942100,\\\n    phase:2,\\\n    block,\\\n'
        "    msg:'SQL Injection Attack Detected via libinjection',\\\n"
        "    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\\\n"
        "    tag:'attack-sqli',\\\n    tag:'paranoia-level/1',\\\n    severity:'CRITICAL'\"\n"
        'SecRule TX:X "@eq 1" "id:942011,phase:1,pass,nolog,skipAfter:END"\n'
    )
    rules = crs_catalog.parse_rules(text, "REQUEST-942-APPLICATION-ATTACK-SQLI.conf")
    assert [r["id"] for r in rules] == [942100]  # Steuerregel ohne msg fällt weg
    assert rules[0]["tags"] == ["attack-sqli"] and rules[0]["phase"] == 2


# ---------- Direktiven ----------


def test_exception_directives() -> None:
    lines = wafrules.exception_directives(
        [
            (1, 942100, "ARGS:content", ""),
            (2, 941100, "", "/api/upload"),
            (3, 932100, "REQUEST_HEADERS:User-Agent", "/webdav"),
            (4, 920350, "", ""),  # ganze Ausnahme läuft über SecRuleRemoveById
        ]
    )
    assert lines == [
        'SecAction "id:10000001,phase:1,pass,nolog,ctl:ruleRemoveTargetById=942100;ARGS:content"',
        'SecRule REQUEST_FILENAME "@beginsWith /api/upload" '
        '"id:10000002,phase:1,pass,nolog,ctl:ruleRemoveById=941100"',
        'SecRule REQUEST_FILENAME "@beginsWith /webdav" '
        '"id:10000003,phase:1,pass,nolog,ctl:ruleRemoveTargetById=932100;REQUEST_HEADERS:User-Agent"',
    ]
    full = waf_directives("block", 1, [920350], [(1, 942100, "ARGS:content", "")])
    # gezielte Ausnahmen vor dem CRS, ganze danach
    assert full.index("ctl:ruleRemoveTargetById") < full.index("Include @owasp_crs/*.conf")
    assert full.index("SecRuleRemoveById 920350") > full.index("Include @owasp_crs/*.conf")


@pytest.mark.parametrize(
    "target",
    ['ARGS:q"', "ARGS:a,b", "ARGS:x;y", "ARGS:a b", "SecRule", "TX:anomaly", "ARGS:" + "x" * 200],
)
def test_bad_targets(target: str) -> None:
    with pytest.raises(ValueError):
        wafrules.clean_target(target)


def test_good_targets_and_paths() -> None:
    assert wafrules.clean_target(" ARGS:content ") == "ARGS:content"
    assert wafrules.clean_target("REQUEST_COOKIES:session_id") == "REQUEST_COOKIES:session_id"
    assert wafrules.clean_target("ARGS") == "ARGS"
    assert wafrules.clean_path("api/upload") == "/api/upload"
    for bad in ['/a"b', "/a b", "/a?x=1", "/a'b"]:
        with pytest.raises(ValueError):
            wafrules.clean_path(bad)


# ---------- Treffer und Log ----------


def _log(
    db,
    host: str,
    rules: list[int],
    uri: str = "/search?q=1",
    ago: timedelta = timedelta(0),
    targets=None,
):
    node = db.query(Node).first()
    db.add(
        LogEntry(
            ts=utcnow() - ago,
            node_id=node.id,
            host=host,
            uri=uri,
            ip="198.51.100.7",
            reason="waf",
            waf_rules=rules,
            waf_targets=targets,
        )
    )


def test_hits_and_detail(auth_client: TestClient) -> None:
    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        _log(db, "a.example.org", [942100, 949110], targets={"942100": "ARGS:q"})
        _log(db, "a.example.org", [942100], uri="/search?q=2", ago=timedelta(days=3))
        _log(db, "b.example.org", [942100, 941100], ago=timedelta(days=20))
        _log(db, "b.example.org", [942100], ago=timedelta(days=40))  # außerhalb
        db.commit()

    rules = {r["id"]: r for r in auth_client.get("/api/waf/rules").json()["rules"]}
    assert rules[942100]["hits"] == {"24h": 1, "7d": 2, "30d": 3}
    assert rules[941100]["hits"]["30d"] == 1
    assert 949110 not in rules or rules[949110]["hits"]["30d"] == 0  # Score-Regel zählt nicht

    d = auth_client.get("/api/waf/rules/942100").json()
    assert d["rule"]["category"] == "SQL-Injection"
    assert d["hosts"][0] == {"host": "a.example.org", "count": 2}
    assert d["paths"][0] == {"host": "a.example.org", "path": "/search", "count": 2}
    assert d["targets"] == [{"target": "ARGS:q", "count": 1}]
    assert auth_client.get("/api/waf/rules/123").status_code == 404


def test_log_keeps_target() -> None:
    from tesseract.logs import WafTracker
    from tests.test_logs import WAF_WARNING

    t = WafTracker()
    t.feed([WAF_WARNING])
    ev = next(iter(t.events.values()))
    assert ev.targets == {"942100": "ARGS:q"}


# ---------- Ausnahmen ----------


def test_targeted_exception_in_config(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host = auth_client.post("/api/hosts", json={**HOST, "waf_mode": "block"}).json()["host"]
    r = auth_client.post(
        "/api/waf/exceptions",
        json={
            "host_id": host["id"],
            "rule_id": 942100,
            "target": "ARGS:content",
            "path": "/wiki/edit",
            "comment": "Wiki-Editor",
        },
    )
    assert r.status_code == 201, r.text
    exc = r.json()["exception"]
    assert exc["created_by"] == "admin" and exc["hits_since"] == 0
    d = _directives(caddy)
    assert (
        f'SecRule REQUEST_FILENAME "@beginsWith /wiki/edit" "id:{10_000_000 + exc["id"]},'
        'phase:1,pass,nolog,ctl:ruleRemoveTargetById=942100;ARGS:content"'
    ) in d
    # Regel bleibt am Host sonst aktiv
    assert auth_client.get(f"/api/hosts/{host['id']}").json()["waf_exclusions"] == []

    listed = auth_client.get("/api/waf/exceptions").json()
    assert [x["comment"] for x in listed] == ["Wiki-Editor"]

    assert auth_client.delete(f"/api/waf/exceptions/{exc['id']}").json()["ok"] is True
    assert "ruleRemoveTargetById" not in _directives(caddy)
    actions = [e["action"] for e in auth_client.get("/api/audit?limit=5").json()]
    assert "waf_exception_deleted" in actions and "waf_exception_created" in actions


def test_whole_exception_with_meta(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host = auth_client.post(
        "/api/hosts", json={**HOST, "waf_mode": "block", "waf_exclusions": [920350]}
    ).json()["host"]
    # direkt am Host gesetzt: erscheint ohne Eintrag
    listed = auth_client.get("/api/waf/exceptions").json()
    assert listed[0]["id"] is None and listed[0]["rule_id"] == 920350

    # ganze Ausnahme mit Kommentar und Ablauf: landet auch in waf_exclusions (neue Version)
    soon = (utcnow() + timedelta(days=7)).isoformat()
    r = auth_client.post(
        "/api/waf/exceptions",
        json={"host_id": host["id"], "rule_id": 942100, "comment": "Fehlalarm", "expires_at": soon},
    )
    assert r.status_code == 201, r.text
    h = auth_client.get(f"/api/hosts/{host['id']}").json()
    assert h["waf_exclusions"] == [920350, 942100] and h["version"] == 2
    assert "SecRuleRemoveById 942100" in _directives(caddy)
    # doppelt geht nicht
    again = auth_client.post("/api/waf/exceptions", json={"host_id": host["id"], "rule_id": 942100})
    assert again.status_code == 409

    # Score-Regel und Vergangenheit abgelehnt
    assert (
        auth_client.post(
            "/api/waf/exceptions", json={"host_id": host["id"], "rule_id": 949110}
        ).status_code
        == 422
    )
    past = (utcnow() - timedelta(days=1)).isoformat()
    assert (
        auth_client.post(
            "/api/waf/exceptions",
            json={"host_id": host["id"], "rule_id": 941100, "expires_at": past},
        ).status_code
        == 422
    )

    # Ausnahme ohne Eintrag direkt entfernen
    r = auth_client.delete(f"/api/waf/hosts/{host['id']}/exclusions/920350")
    assert r.status_code == 200
    assert auth_client.get(f"/api/hosts/{host['id']}").json()["waf_exclusions"] == [942100]


def test_expiry(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host = auth_client.post("/api/hosts", json={**HOST, "waf_mode": "block"}).json()["host"]
    soon = (utcnow() + timedelta(hours=1)).isoformat()
    for body in (
        {"rule_id": 942100, "expires_at": soon},
        {"rule_id": 941100, "target": "ARGS:x", "expires_at": soon},
        {"rule_id": 932100, "target": "ARGS:y"},
    ):
        r = auth_client.post("/api/waf/exceptions", json={"host_id": host["id"], **body})
        assert r.status_code == 201, r.text

    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        n = wafrules.expire(
            db, app.state.settings, app.state.caddy_transport, now=utcnow() + timedelta(hours=2)
        )
        assert n == 2
        left = [(e.rule_id, e.target) for e in db.query(WafException)]
        assert left == [(932100, "ARGS:y")]
        h = db.get(Host, host["id"])
        assert h.waf_exclusions == []
    d = _directives(caddy)
    assert "SecRuleRemoveById 942100" not in d and "941100" not in d and "932100;ARGS:y" in d
    actions = [e["action"] for e in auth_client.get("/api/audit?limit=10").json()]
    assert actions.count("waf_exception_expired") == 2


def test_catalog_file_is_valid_json() -> None:
    data = json.loads(wafrules.CATALOG.read_text(encoding="utf-8"))
    assert re.match(r"^\d+\.\d+\.\d+$", data["crs"])
