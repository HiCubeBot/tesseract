"""Zugriff auf Tesseract für einzelne Personen – nur per Gerätezertifikat (uiaccess.py)."""

from fastapi.testclient import TestClient

from tesseract import uiaccess
from tesseract.caddy.config import FINGERPRINT_HEADER
from tests.conftest import FakeCaddy
from tests.test_mtls import HOST, _fp, _issue, _setup


def _person(c: TestClient, person: dict, role: str) -> None:
    body = {
        "name": person["name"],
        "group_ids": [g["id"] for g in person["groups"]],
        "ui_role": role,
    }
    r = c.put(f"/api/persons/{person['id']}", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["ui_role"] == role


def _as(c: TestClient, fp: str, method: str, url: str, **kw):
    """Anfrage ohne Sitzung, nur mit dem Fingerabdruck, den Caddy durchreicht."""
    c.cookies.clear()
    return c.request(method, url, headers={FINGERPRINT_HEADER: fp}, **kw)


def test_policy() -> None:
    assert uiaccess.allowed("admin", "DELETE", "/api/hosts/1")
    assert uiaccess.allowed("read", "GET", "/api/stats/traffic")
    assert uiaccess.allowed("read", "GET", "/api/hosts/3/versions/2")
    assert not uiaccess.allowed("read", "POST", "/api/hosts")
    assert not uiaccess.allowed("read", "GET", "/api/devices/3/certificate")
    assert not uiaccess.allowed("read", "GET", "/api/settings/general")
    assert not uiaccess.allowed("read", "GET", "/api/backups")
    assert uiaccess.allowed("own", "GET", "/api/stats/host")
    assert not uiaccess.allowed("own", "GET", "/api/stats/traffic")
    assert not uiaccess.allowed("own", "GET", "/api/logs")
    assert uiaccess.allowed("read", "POST", "/api/auth/logout")
    assert not uiaccess.allowed("none", "GET", "/api/hosts")


def test_roles(client: TestClient, caddy: FakeCaddy) -> None:
    from tests.conftest import ADMIN_PASSWORD

    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
        ).status_code
        == 200
    )
    ids = _setup(client)
    anna, ben = ids["anna"], ids["ben"]
    fp_anna = _fp(_issue(client, anna["id"], "laptop"))
    fp_ben = _fp(_issue(client, ben["id"], "handy"))
    # Fotos für die Familie (Anna), Filme nur für niemanden
    r = client.post("/api/hosts", json={**HOST, "grant_group_ids": [ids["fam"]["id"]]})
    fotos = r.json()["host"]["id"]
    filme = client.post("/api/hosts", json={**HOST, "domain": "filme.example.org"}).json()["host"][
        "id"
    ]

    # Ohne Rolle: kein Zugriff, auch mit gültigem Gerät
    assert _as(client, fp_anna, "GET", "/api/hosts").status_code == 401

    # Lesen
    client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    _person(client, client.get(f"/api/persons/{anna['id']}").json(), "read")
    me = _as(client, fp_anna, "GET", "/api/auth/me").json()
    assert me["source"] == "mtls" and me["role"] == "read" and me["device"] == "laptop"
    assert len(_as(client, fp_anna, "GET", "/api/hosts").json()) == 2
    r = _as(client, fp_anna, "PUT", f"/api/hosts/{fotos}", json=HOST)
    assert r.status_code == 403 and "Lesen" in r.text
    assert _as(client, fp_anna, "GET", "/api/settings/general").status_code == 403
    assert _as(client, fp_anna, "POST", "/api/auth/password", json={}).status_code == 403

    # Eigene Dienste: nur der freigegebene Host
    client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    _person(client, client.get(f"/api/persons/{anna['id']}").json(), "own")
    hosts = _as(client, fp_anna, "GET", "/api/hosts").json()
    assert [h["id"] for h in hosts] == [fotos]
    assert _as(client, fp_anna, "GET", f"/api/hosts/{filme}").status_code == 404
    assert _as(client, fp_anna, "GET", f"/api/hosts/{fotos}/versions").status_code == 200
    r = _as(client, fp_anna, "GET", "/api/stats/host", params={"domain": "filme.example.org"})
    assert r.status_code == 404
    mine = _as(client, fp_anna, "GET", "/api/me/devices").json()
    assert mine["hosts"] == ["fotos.example.org"] and mine["current_device"] == "laptop"
    assert _as(client, fp_anna, "GET", "/api/logs").status_code == 403

    # Admin per Zertifikat: darf ändern, Audit zeigt Person und Gerät
    client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    _person(client, client.get(f"/api/persons/{ben['id']}").json(), "admin")
    r = _as(client, fp_ben, "POST", "/api/groups", json={"name": "Neu"})
    assert r.status_code == 201, r.text
    client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    audit = client.get("/api/audit?limit=5").json()
    entries = audit["entries"] if isinstance(audit, dict) else audit
    assert any(e["actor"] == "Ben (handy)" for e in entries)
    # Konto-Funktionen gibt es nur für Admin-Konten
    r = _as(
        client,
        fp_ben,
        "POST",
        "/api/auth/password",
        json={"current_password": "x", "new_password": "y" * 12},
    )
    assert r.status_code == 409

    # Gerät gesperrt → sofort kein Zugriff mehr
    client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    dev = next(d for d in client.get(f"/api/persons/{ben['id']}").json()["devices"])
    assert client.post(f"/api/devices/{dev['id']}/revoke", json={}).status_code in (200, 204)
    assert _as(client, fp_ben, "GET", "/api/hosts").status_code == 401

    # Person gesperrt → kein Zugriff
    client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    p = client.get(f"/api/persons/{anna['id']}").json()
    body = {"name": p["name"], "group_ids": [g["id"] for g in p["groups"]], "disabled": True}
    assert client.put(f"/api/persons/{anna['id']}", json=body).status_code == 200
    assert _as(client, fp_anna, "GET", "/api/hosts").status_code == 401


def test_admin_mtls_allows_ui_devices(auth_client: TestClient, caddy: FakeCaddy) -> None:
    """„Nur mit Admin-Zertifikat“: Geräte von Personen mit Zugriff kommen auch durch."""
    ids = _setup(auth_client)
    anna = ids["anna"]
    fp = _fp(_issue(auth_client, anna["id"], "laptop"))
    _person(auth_client, auth_client.get(f"/api/persons/{anna['id']}").json(), "read")
    from tesseract.services import node_config

    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        from tesseract.db.models import Node
        from tesseract.services import set_general

        set_general(db, {"admin_mtls": True})
        node = db.query(Node).first()
        cfg = node_config(db, node, app.state.settings)
    text = str(cfg)
    assert fp in text


def test_cert_users_listed_for_admin_networks(auth_client: TestClient, caddy: FakeCaddy) -> None:
    """Nur Geräte von Personen mit Rolle stehen in der Ausnahme von TESSERACT_ADMIN_NETWORKS."""
    import json

    from tesseract.db.models import Node
    from tesseract.services import node_config

    ids = _setup(auth_client)
    anna, ben = ids["anna"], ids["ben"]
    fp_anna = _fp(_issue(auth_client, anna["id"], "laptop"))
    fp_ben = _fp(_issue(auth_client, ben["id"], "handy"))
    _person(auth_client, auth_client.get(f"/api/persons/{anna['id']}").json(), "read")

    app = auth_client.app
    settings = app.state.settings.model_copy(
        update={"admin_networks": "192.168.178.0/24", "controller_domain": "tesseract.example.org"}
    )
    with app.state.db.sessionmaker() as db:
        node = db.query(Node).filter(Node.kind == "local").first()
        cfg = node_config(db, node, settings)
    route = next(
        r for r in cfg["apps"]["http"]["servers"]["https"]["routes"] if r.get("@id") == "controller"
    )
    gate = json.dumps(route["handle"][0]["routes"][0])
    assert '"abort": true' in gate and fp_anna in gate and fp_ben not in gate
