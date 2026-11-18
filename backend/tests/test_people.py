import base64

from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi.testclient import TestClient

PASSPHRASE = "root-passphrase-123"


def _setup_ca(c: TestClient) -> dict:
    r = c.post("/api/ca/setup", json={"passphrase": PASSPHRASE})
    assert r.status_code == 200, r.text
    return r.json()


def _person(c: TestClient, name: str = "Anna", **kw) -> dict:
    r = c.post("/api/persons", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_ca_setup_once(auth_client: TestClient) -> None:
    assert auth_client.get("/api/ca").json()["configured"] is False
    out = _setup_ca(auth_client)
    assert "ENCRYPTED PRIVATE KEY" in out["root_key_pem"]
    status = auth_client.get("/api/ca").json()
    assert status["configured"] is True
    assert status["root"]["key_on_controller"] is False
    assert status["intermediate"]["key_on_controller"] is True
    assert auth_client.post("/api/ca/setup", json={"passphrase": PASSPHRASE}).status_code == 409
    assert "BEGIN CERTIFICATE" in auth_client.get("/api/ca/root.pem").text


def test_short_passphrase(auth_client: TestClient) -> None:
    assert auth_client.post("/api/ca/setup", json={"passphrase": "kurz"}).status_code == 422


def test_admin_group_exists(auth_client: TestClient) -> None:
    groups = auth_client.get("/api/groups").json()
    assert groups[0]["name"] == "Admin" and groups[0]["builtin"] is True
    assert auth_client.delete(f"/api/groups/{groups[0]['id']}").status_code == 409


def test_groups_and_persons(auth_client: TestClient) -> None:
    fam = auth_client.post("/api/groups", json={"name": "Familie"}).json()
    assert auth_client.post("/api/groups", json={"name": "Familie"}).status_code == 409
    anna = _person(auth_client, "  Anna   Beispiel ", group_ids=[fam["id"]], max_devices=2)
    assert anna["name"] == "Anna Beispiel"
    assert anna["groups"] == [{"id": fam["id"], "name": "Familie"}]
    assert auth_client.post("/api/persons", json={"name": "Anna Beispiel"}).status_code == 409
    assert (
        auth_client.post("/api/persons", json={"name": "X", "group_ids": [999]}).status_code == 422
    )

    r = auth_client.put(
        f"/api/persons/{anna['id']}",
        json={"name": "Anna Beispiel", "max_devices": 2, "group_ids": []},
    )
    assert r.json()["groups"] == []
    assert auth_client.get("/api/groups").json()[1]["members"] == 0


def test_issue_requires_ca(auth_client: TestClient) -> None:
    p = _person(auth_client)
    r = auth_client.post(f"/api/persons/{p['id']}/devices", json={"name": "iPhone"})
    assert r.status_code == 409
    assert "nicht eingerichtet" in r.json()["detail"]


def test_issue_revoke_and_limit(auth_client: TestClient) -> None:
    _setup_ca(auth_client)
    p = _person(auth_client, max_devices=1)
    r = auth_client.post(
        f"/api/persons/{p['id']}/devices", json={"name": "Annas iPhone", "platform": "ios"}
    )
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["filename"].endswith(".p12")
    key, cert, chain = pkcs12.load_key_and_certificates(
        base64.b64decode(out["p12_base64"]), out["password"].encode()
    )
    assert cert is not None and len(chain) == 2
    assert out["device"]["status"] == "active"

    # Limit: nur ein aktives Gerät erlaubt
    r = auth_client.post(f"/api/persons/{p['id']}/devices", json={"name": "Laptop"})
    assert r.status_code == 409

    dev_id = out["device"]["id"]
    r = auth_client.post(f"/api/devices/{dev_id}/revoke", json={"reason": "verloren"})
    assert r.json()["status"] == "revoked"
    assert auth_client.post(f"/api/devices/{dev_id}/revoke", json={}).status_code == 409

    # Gesperrtes Gerät zählt nicht mehr zum Limit
    r = auth_client.post(f"/api/persons/{p['id']}/devices", json={"name": "Laptop", "days": None})
    assert r.status_code == 201
    assert r.json()["device"]["unlimited"] is True

    csv = auth_client.get("/api/devices/revoked.csv").text
    assert "Annas iPhone" in csv and "verloren" in csv
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert {"ca_created", "device_issued", "device_revoked"} <= set(actions)


def test_disabled_person_cannot_get_device(auth_client: TestClient) -> None:
    _setup_ca(auth_client)
    p = _person(auth_client, disabled=True)
    r = auth_client.post(f"/api/persons/{p['id']}/devices", json={"name": "x"})
    assert r.status_code == 409


def test_secret_key_file_created(auth_client: TestClient, settings) -> None:
    assert (settings.data_dir / "secret.key").exists()


def test_delete_only_after_revoke(auth_client: TestClient) -> None:
    _setup_ca(auth_client)
    p = _person(auth_client)
    dev = auth_client.post(f"/api/persons/{p['id']}/devices", json={"name": "Pixel"}).json()[
        "device"
    ]
    r = auth_client.delete(f"/api/devices/{dev['id']}")
    assert r.status_code == 409 and "erst sperren" in r.json()["detail"]
    auth_client.post(f"/api/devices/{dev['id']}/revoke", json={})
    assert auth_client.delete(f"/api/devices/{dev['id']}").status_code == 204
    assert auth_client.get("/api/devices").json() == []
    assert auth_client.get(f"/api/persons/{p['id']}").json()["devices"] == []
    assert auth_client.get("/api/audit").json()[0]["action"] == "device_deleted"
    assert auth_client.delete(f"/api/devices/{dev['id']}").status_code == 404
