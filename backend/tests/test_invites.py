import base64

from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi.testclient import TestClient

from tesseract.caddy.config import FINGERPRINT
from tests.conftest import FakeCaddy


def _prepare(c: TestClient, max_devices: int = 2) -> dict:
    assert c.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"}).status_code == 200
    fam = c.post("/api/groups", json={"name": "Familie"}).json()
    dana = c.post(
        "/api/persons", json={"name": "Dana", "group_ids": [fam["id"]], "max_devices": max_devices}
    ).json()
    c.post(
        "/api/hosts",
        json={
            "domain": "filme.example.org",
            "node_id": 1,
            "upstream_host": "10.0.1.20",
            "upstream_port": 8096,
            "access": "mtls",
            "grant_group_ids": [fam["id"]],
        },
    )
    invite = c.post(f"/api/persons/{dana['id']}/invites", json={"days": 7}).json()
    return {"dana": dana, "invite": invite, "token": invite["url"].rsplit("/e/", 1)[1]}


def _code(invite: dict) -> str:
    return invite["code"].replace(" ", "")


def test_full_flow(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ctx = _prepare(auth_client)
    inv, token = ctx["invite"], ctx["token"]
    assert inv["state"] == "open" and len(_code(inv)) == 6
    qr = auth_client.get(f"/api/invites/{inv['id']}/qr.svg").text
    # skalierbar: viewBox statt fester Größe (sonst schneidet der Browser den Code ab)
    assert qr.startswith("<svg") and "viewBox=" in qr and 'width="' not in qr

    # Gast sieht seine Einladung – ohne Anmeldung
    auth_client.cookies.clear()
    info = auth_client.get(f"/api/enroll/{token}").json()
    assert info["person_name"] == "Dana"
    assert info["services"] == ["filme.example.org"]
    assert info["slots_left"] == 2

    r = auth_client.post(
        f"/api/enroll/{token}/register",
        json={"device_name": "Danas iPhone", "platform": "ios", "code": inv["code"]},
    )
    assert r.status_code == 201, r.text
    req = r.json()
    headers = {"X-Enroll-Secret": req["secret"]}
    status_url = f"/api/enroll/{token}/requests/{req['enrollment_id']}"
    assert auth_client.get(status_url, headers=headers).json()["status"] == "pending"
    assert auth_client.get(status_url, headers={"X-Enroll-Secret": "falsch"}).status_code == 404
    # noch nicht freigegeben
    assert auth_client.post(status_url + "/certificate", headers=headers).status_code == 409

    # Admin gibt frei
    from tests.conftest import ADMIN_PASSWORD

    auth_client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    pending = auth_client.get(f"/api/invites/{inv['id']}").json()["enrollments"]
    assert pending[0]["status"] == "pending" and pending[0]["platform"] == "ios"
    assert auth_client.post(f"/api/enrollments/{req['enrollment_id']}/approve").status_code == 200
    auth_client.cookies.clear()

    assert auth_client.get(status_url, headers=headers).json()["status"] == "approved"
    cert = auth_client.post(status_url + "/certificate", headers=headers).json()
    key, c, chain = pkcs12.load_key_and_certificates(
        base64.b64decode(cert["p12_base64"]), cert["password"].encode()
    )
    assert c is not None and len(chain) == 2
    assert cert["services"] == ["filme.example.org"]
    assert cert["slots_left"] == 1
    assert cert["renew_url"] == "https://tesseract.example.org/v"
    # Nur einmal abholbar
    assert auth_client.post(status_url + "/certificate", headers=headers).status_code == 410

    # Das neue Gerät steht sofort in der Freigabeliste des Hosts
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    gate = next(r for r in routes if r["match"][0]["host"] == ["filme.example.org"])
    first = next(
        x
        for x in gate["handle"][0]["routes"]
        if x.get("match", [{}])[0].get("path") != ["/robots.txt"]
    )
    fps = first["match"][0]["not"][0]["vars"][FINGERPRINT]
    from tesseract import pki

    assert fps == [pki.fingerprint(c)]


def test_wrong_code_locks_invite(auth_client: TestClient) -> None:
    ctx = _prepare(auth_client)
    token = ctx["token"]
    auth_client.cookies.clear()
    for _ in range(5):
        r = auth_client.post(
            f"/api/enroll/{token}/register", json={"device_name": "x", "code": "000000"}
        )
        if _code(ctx["invite"]) == "000000":  # extrem unwahrscheinlich
            return
        assert r.status_code == 403
    assert "gesperrt" in r.json()["detail"]
    assert auth_client.get(f"/api/enroll/{token}").status_code == 404


def test_reject_and_slots(auth_client: TestClient) -> None:
    ctx = _prepare(auth_client, max_devices=1)
    inv, token = ctx["invite"], ctx["token"]
    from tests.conftest import ADMIN_PASSWORD

    auth_client.cookies.clear()
    first = auth_client.post(
        f"/api/enroll/{token}/register", json={"device_name": "A", "code": inv["code"]}
    ).json()
    # Platz durch offene Anfrage belegt
    r = auth_client.post(
        f"/api/enroll/{token}/register", json={"device_name": "B", "code": inv["code"]}
    )
    assert r.status_code == 409

    auth_client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert auth_client.post(f"/api/enrollments/{first['enrollment_id']}/reject").status_code == 200
    assert auth_client.post(f"/api/enrollments/{first['enrollment_id']}/approve").status_code == 409
    auth_client.cookies.clear()

    # Abgelehnt → Platz wieder frei
    r = auth_client.post(
        f"/api/enroll/{token}/register", json={"device_name": "B", "code": inv["code"]}
    )
    assert r.status_code == 201


def test_revoked_invite(auth_client: TestClient) -> None:
    ctx = _prepare(auth_client)
    auth_client.post(f"/api/invites/{ctx['invite']['id']}/revoke")
    assert auth_client.get("/api/invites").json() == []
    assert len(auth_client.get("/api/invites?all=true").json()) == 1
    auth_client.cookies.clear()
    assert auth_client.get(f"/api/enroll/{ctx['token']}").status_code == 404


def test_unknown_token_and_admin_endpoints_need_login(client: TestClient) -> None:
    assert client.get("/api/enroll/gibtesnicht").status_code == 404
    assert client.get("/api/invites").status_code == 401
    assert client.post("/api/enrollments/1/approve").status_code == 401


def test_invite_requires_ca(auth_client: TestClient) -> None:
    p = auth_client.post("/api/persons", json={"name": "Erik"}).json()
    r = auth_client.post(f"/api/persons/{p['id']}/invites", json={})
    assert r.status_code == 409
