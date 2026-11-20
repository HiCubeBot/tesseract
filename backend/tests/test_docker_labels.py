"""Hosts aus Docker-Labels."""

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from tesseract import dockerlabels as dl
from tesseract.db.models import Node


def _container(name="navidrome", state="running", **labels):
    return {
        "id": "abc",
        "name": name,
        "state": state,
        "labels": {f"tesseract.{k}": v for k, v in labels.items()},
        "ports": [4533],
    }


def _sync(client: TestClient, containers):
    app = client.app
    with app.state.db.sessionmaker() as db:
        node = db.scalar(select(Node).where(Node.kind == "local"))
        return dl.run_sync(app, db, node, containers)


def _host(client: TestClient, domain: str):
    return next((h for h in client.get("/api/hosts").json() if h["domain"] == domain), None)


def test_parse() -> None:
    groups, persons = {"Familie": 1}, {"Ben": 2}
    spec = dl.parse(
        _container(domain="musik.example.org", access="mtls", grants="Familie, Ben", waf="block"),
        groups,
        persons,
    )
    assert spec == {
        "domain": "musik.example.org",
        "upstream_port": 4533,  # einziger Port des Containers
        "upstream_host": "navidrome",
        "access": "mtls",
        "waf_mode": "block",
        "grant_group_ids": [1],
        "grant_person_ids": [2],
    }
    assert dl.parse(_container(domain="x.example.org", enable="false"), {}, {}) is None
    for bad in (
        {"grants": "Fremde"},
        {"access": "alle"},
        {"port": "99999"},
        {"internal": "vielleicht"},
    ):
        try:
            dl.parse(_container(domain="x.example.org", **bad), groups, persons)
        except dl.LabelError:
            continue
        raise AssertionError(bad)
    no_port = {**_container(domain="x.example.org"), "ports": [80, 443]}
    try:
        dl.parse(no_port, {}, {})
        raise AssertionError("Port fehlt")
    except dl.LabelError as e:
        assert "tesseract.port" in str(e)


def test_read_containers() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["filters"] = request.url.params["filters"]
        return httpx.Response(
            200,
            json=[
                {
                    "Id": "0123456789abcdef",
                    "Names": ["/wiki"],
                    "State": "exited",
                    "Labels": {"tesseract.domain": "wiki.example.org", "com.docker.x": "y"},
                    "Ports": [{"PrivatePort": 3000, "Type": "tcp"}],
                }
            ],
        )

    out = dl.read_containers("tcp://proxy:2375", httpx.MockTransport(handler))
    assert out == [
        {
            "id": "0123456789ab",
            "name": "wiki",
            "state": "exited",
            "labels": {"tesseract.domain": "wiki.example.org"},
            "ports": [3000],
        }
    ]
    assert "tesseract.domain" in seen["filters"]


def test_sync_lifecycle(auth_client: TestClient) -> None:
    gid = auth_client.post("/api/groups", json={"name": "Familie"}).json()["id"]
    c = _container(domain="musik.example.org", access="mtls", grants="Familie")

    # neu → Entwurf, Gruppe zugeordnet, als Docker-Host markiert
    r = _sync(auth_client, [c])
    assert r["created"] == ["musik.example.org"] and not r["errors"]
    h = _host(auth_client, "musik.example.org")
    assert h["draft"] and h["source"] == "docker" and h["access"] == "mtls"
    assert [g["id"] for g in h["grants"]] == [gid]

    # gleiche Labels → nichts zu tun
    r = _sync(auth_client, [c])
    assert not (r["created"] or r["updated"] or r["disabled"])

    # Änderung in der Oberfläche bleibt, solange die Labels gleich sind
    from tesseract.api.hosts import HostIn  # noqa: F401 – nur Schema-Bezug

    edited = {**h, "compression": True, "node_id": h["node"]["id"], "draft": False}
    for k in (
        "id",
        "node",
        "grants",
        "granted_persons",
        "allowed_devices",
        "wildcard_cert",
        "version",
        "created_at",
        "updated_at",
        "source",
        "source_ref",
        "source_disabled",
    ):
        edited.pop(k, None)
    edited["grant_group_ids"], edited["grant_person_ids"] = [gid], []
    edited["areas"] = []
    assert auth_client.put(f"/api/hosts/{h['id']}", json=edited).status_code == 200
    _sync(auth_client, [c])
    assert _host(auth_client, "musik.example.org")["compression"] is True

    # Labels geändert → gilt, neue Version vom Akteur „docker“
    c2 = _container(domain="musik.example.org", access="public", port="8080")
    r = _sync(auth_client, [c2])
    assert r["updated"] == ["musik.example.org"]
    h = _host(auth_client, "musik.example.org")
    assert h["access"] == "public" and h["upstream_port"] == 8080 and h["compression"] is True
    versions = auth_client.get(f"/api/hosts/{h['id']}/versions").json()
    assert versions[0]["actor"] == "docker"

    # Container gestoppt → deaktiviert; läuft wieder → aktiviert
    r = _sync(auth_client, [{**c2, "state": "exited"}])
    assert r["disabled"] == ["musik.example.org"]
    assert _host(auth_client, "musik.example.org")["enabled"] is False
    r = _sync(auth_client, [c2])
    assert r["enabled"] == ["musik.example.org"]

    # Container entfernt → deaktiviert, nicht gelöscht
    r = _sync(auth_client, [])
    assert r["disabled"] == ["musik.example.org"]
    h = _host(auth_client, "musik.example.org")
    assert h is not None and h["enabled"] is False and h["source_disabled"] is True


def test_sync_rules(auth_client: TestClient) -> None:
    # Domain eines manuellen Hosts wird nicht übernommen
    node_id = auth_client.get("/api/nodes").json()[0]["id"]
    manual = {
        "domain": "wiki.example.org",
        "node_id": node_id,
        "upstream_host": "10.0.0.5",
        "upstream_port": 80,
    }
    assert auth_client.post("/api/hosts", json=manual).status_code == 201
    r = _sync(auth_client, [_container(name="wiki", domain="wiki.example.org")])
    assert r["errors"] and "gibt es schon" in r["errors"][0]["error"]
    assert _host(auth_client, "wiki.example.org")["source"] == "ui"

    # unbekannte Freigabe → Fehler, kein Host
    r = _sync(auth_client, [_container(name="x", domain="x.example.org", grants="Niemand")])
    assert r["errors"] and _host(auth_client, "x.example.org") is None

    # „direkt übertragen“ → kein Entwurf
    auth_client.put(
        "/api/settings/general", json={"docker_enabled": True, "docker_auto_activate": True}
    )
    g = auth_client.get("/api/settings/general").json()
    assert g["docker_enabled"] and g["docker_auto_activate"] and g["docker_local"] is False
    _sync(auth_client, [_container(name="git", domain="git.example.org", port="3000")])
    h = _host(auth_client, "git.example.org")
    assert h["draft"] is False and h["enabled"] is True

    assert dl.normalize_report(
        [
            {
                "name": "a",
                "labels": {"tesseract.domain": "a.example.org", "other": "x"},
                "ports": ["80", "x"],
            }
        ]
    ) == [
        {
            "id": "",
            "name": "a",
            "state": "",
            "labels": {"tesseract.domain": "a.example.org"},
            "ports": [80],
        }
    ]


def test_agent_reports_containers(auth_client: TestClient) -> None:
    from tests.test_nodes_agent import _joined

    agent, _ = _joined(auth_client)
    containers = [
        {
            "id": "1",
            "name": "fotos",
            "state": "running",
            "labels": {"tesseract.domain": "fotos.example.org", "tesseract.port": "2342"},
            "ports": [],
        }
    ]
    # ausgeschaltet → nichts passiert
    assert agent.post("/api/agent/status", {"containers": containers}).status_code == 200
    assert _host(auth_client, "fotos.example.org") is None
    auth_client.put("/api/settings/general", json={"docker_enabled": True})
    assert agent.post("/api/agent/status", {"containers": containers}).status_code == 200
    h = _host(auth_client, "fotos.example.org")
    assert h["node"]["name"] != "local" and h["upstream_host"] == "fotos" and h["draft"]
    agent.post("/api/agent/status", {"docker_error": "Docker nicht erreichbar"})
    status = auth_client.get("/api/settings/docker").json()
    node = next(n for n in status["nodes"] if n["node"] == h["node"]["name"])
    assert "nicht erreichbar" in node["errors"][0]["error"]
