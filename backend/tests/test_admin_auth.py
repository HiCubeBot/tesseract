"""SSO (OIDC) und Passkeys für die Admin-Anmeldung."""

import base64
import hashlib
import json
import struct
import time
from urllib.parse import parse_qs, urlsplit

import cbor2
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

ISSUER = "https://sso.example.org"
ORIGIN = "https://tesseract.example.org"
RP_ID = "tesseract.example.org"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


# ---------- nachgebauter OIDC-Anbieter ----------


class FakeIdP:
    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims: dict = {
            "sub": "u1",
            "preferred_username": "anna",
            "email": "anna@example.org",
            "groups": ["tesseract-admins"],
        }
        self.nonce = ""
        self.code_verifier = ""
        self.challenge = ""
        self.issuer_in_token = ISSUER

    def jwk(self) -> dict:
        k = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        return {**k, "kid": "k1", "use": "sig", "alg": "RS256"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                    "userinfo_endpoint": f"{ISSUER}/userinfo",
                },
            )
        if path == "/jwks":
            return httpx.Response(200, json={"keys": [self.jwk()]})
        if path == "/token":
            form = parse_qs(request.content.decode())
            verifier = form["code_verifier"][0]
            # PKCE prüfen wie ein echter Anbieter
            expect = b64u(hashlib.sha256(verifier.encode()).digest())
            if expect != self.challenge or form["code"][0] != "gut":
                return httpx.Response(400, json={"error": "invalid_grant"})
            now = int(time.time())
            token = jwt.encode(
                {
                    **self.claims,
                    "iss": self.issuer_in_token,
                    "aud": "tesseract",
                    "iat": now,
                    "exp": now + 300,
                    "nonce": self.nonce,
                },
                self.key,
                algorithm="RS256",
                headers={"kid": "k1"},
            )
            return httpx.Response(200, json={"id_token": token, "access_token": "at"})
        return httpx.Response(404)


@pytest.fixture
def idp(auth_client: TestClient) -> FakeIdP:
    fake = FakeIdP()
    auth_client.app.state.oidc.transport = httpx.MockTransport(fake.handler)
    return fake


def _enable_sso(c: TestClient, **kw) -> dict:
    body = {
        "oidc": {
            "enabled": True,
            "issuer": ISSUER,
            "client_id": "tesseract",
            "client_secret": "geheim",
            "admin_group": "tesseract-admins",
            **kw,
        }
    }
    r = c.put("/api/settings/admin-auth", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _sso_login(c: TestClient, idp: FakeIdP, code: str = "gut") -> httpx.Response:
    r = c.get("/api/auth/sso/start", follow_redirects=False)
    assert r.status_code == 303, r.text
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert q["code_challenge_method"] == ["S256"]
    idp.nonce, idp.challenge = q["nonce"][0], q["code_challenge"][0]
    return c.get(
        "/api/auth/sso/callback",
        params={"state": q["state"][0], "code": code},
        follow_redirects=False,
    )


def test_sso_login_creates_admin(auth_client: TestClient, idp: FakeIdP) -> None:
    out = _enable_sso(auth_client)
    assert out["oidc"]["client_secret_set"] is True and "client_secret_enc" not in out["oidc"]
    assert out["redirect_uri"] == "https://tesseract.example.org/api/auth/sso/callback"
    assert auth_client.get("/api/auth/methods").json()["sso"] == "Mit SSO anmelden"

    c = TestClient(auth_client.app)  # frischer Browser ohne Session
    r = _sso_login(c, idp)
    assert r.status_code == 303 and r.headers["location"] == "/#/"
    me = c.get("/api/auth/me").json()
    assert me == {"username": "anna", "password_from_env": False, "source": "oidc"}
    # Passwort ändern geht für SSO-Konten nicht
    r = c.post("/api/auth/password", json={"current_password": "x" * 12, "new_password": "y" * 12})
    assert r.status_code == 409
    # zweites Mal: gleiches Konto
    c2 = TestClient(auth_client.app)
    _sso_login(c2, idp)
    assert c2.get("/api/auth/me").json()["username"] == "anna"
    actions = [(e["actor"], e["action"]) for e in auth_client.get("/api/audit").json()]
    assert ("anna", "login") in actions


def test_sso_rejections(auth_client: TestClient, idp: FakeIdP) -> None:
    _enable_sso(auth_client)
    c = TestClient(auth_client.app)
    # nicht in der Admin-Gruppe
    idp.claims["groups"] = ["andere"]
    r = _sso_login(c, idp)
    assert r.status_code == 303 and "fehler=" in r.headers["location"]
    assert c.get("/api/auth/me").status_code == 401
    # freigegebene E-Mail reicht
    _enable_sso(auth_client, admin_group="", allowed_emails=["Anna@example.org"])
    assert _sso_login(c, idp).headers["location"] == "/#/"
    # falscher Aussteller im Token
    c = TestClient(auth_client.app)
    idp.issuer_in_token = "https://boese.example.org"
    assert "fehler=" in _sso_login(c, idp).headers["location"]
    # falscher Code / unbekannter state
    idp.issuer_in_token = ISSUER
    assert "fehler=" in _sso_login(c, idp, code="falsch").headers["location"]
    r = c.get(
        "/api/auth/sso/callback",
        params={"state": "gibtsnicht", "code": "gut"},
        follow_redirects=False,
    )
    assert "abgelaufen" in r.headers["location"] or "fehler=" in r.headers["location"]
    # Konfiguration ohne Regel, wer Admin wird
    bad = auth_client.put(
        "/api/settings/admin-auth",
        json={"oidc": {"enabled": True, "issuer": ISSUER, "client_id": "x"}},
    )
    assert bad.status_code == 422


def test_password_login_can_be_disabled_only_with_alternative(
    auth_client: TestClient, idp: FakeIdP
) -> None:
    r = auth_client.put("/api/settings/admin-auth", json={"password_login": False})
    assert r.status_code == 409
    _enable_sso(auth_client)
    assert (
        auth_client.put("/api/settings/admin-auth", json={"password_login": False}).status_code
        == 200
    )
    from tests.conftest import ADMIN_PASSWORD

    r = TestClient(auth_client.app).post(
        "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert r.status_code == 403
    assert auth_client.get("/api/auth/methods").json()["password"] is False


# ---------- Passkeys mit einem nachgebauten Authenticator ----------


class Authenticator:
    """Erzeugt echte WebAuthn-Antworten (Attestation „none“, ECDSA P-256)."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = b"\x01\x02" + bytes(range(30))
        self.count = 0
        self.user_handle = b""

    def _client_data(self, typ: str, challenge: str, origin: str = ORIGIN) -> bytes:
        return json.dumps(
            {"type": typ, "challenge": challenge, "origin": origin, "crossOrigin": False}
        ).encode()

    def create(self, options: dict) -> dict:
        nums = self.key.public_key().public_numbers()
        cose = cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")}
        )
        auth_data = (
            hashlib.sha256(RP_ID.encode()).digest()
            + bytes([0x45])
            + struct.pack(">I", 0)
            + bytes(16)
            + struct.pack(">H", len(self.cred_id))
            + self.cred_id
            + cose
        )
        self.user_handle = base64.urlsafe_b64decode(options["user"]["id"] + "==")
        att = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64u(self.cred_id),
            "rawId": b64u(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(self._client_data("webauthn.create", options["challenge"])),
                "attestationObject": b64u(att),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def get(self, options: dict, origin: str = ORIGIN) -> dict:
        self.count += 1
        auth_data = (
            hashlib.sha256(RP_ID.encode()).digest() + bytes([0x05]) + struct.pack(">I", self.count)
        )
        cd = self._client_data("webauthn.get", options["challenge"], origin)
        sig = self.key.sign(auth_data + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64u(self.cred_id),
            "rawId": b64u(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(cd),
                "authenticatorData": b64u(auth_data),
                "signature": b64u(sig),
                "userHandle": b64u(self.user_handle),
            },
            "clientExtensionResults": {},
        }


def _register(c: TestClient, a: Authenticator) -> dict:
    opts = c.post("/api/auth/passkeys/options").json()
    assert opts["options"]["rp"]["id"] == RP_ID
    assert opts["options"]["authenticatorSelection"]["residentKey"] == "required"
    r = c.post(
        "/api/auth/passkeys",
        json={"id": opts["id"], "credential": a.create(opts["options"]), "name": "YubiKey"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_passkey_register_and_login(auth_client: TestClient) -> None:
    a = Authenticator()
    pk = _register(auth_client, a)
    assert pk["name"] == "YubiKey"
    assert [p["name"] for p in auth_client.get("/api/auth/passkeys").json()] == ["YubiKey"]
    assert auth_client.get("/api/auth/methods").json()["passkey"] is True

    c = TestClient(auth_client.app)
    opts = c.post("/api/auth/passkey/options").json()
    r = c.post(
        "/api/auth/passkey/login", json={"id": opts["id"], "credential": a.get(opts["options"])}
    )
    assert r.status_code == 200, r.text
    assert c.get("/api/auth/me").json()["username"] == "admin"

    # Wiederholung derselben Challenge geht nicht
    r = c.post(
        "/api/auth/passkey/login", json={"id": opts["id"], "credential": a.get(opts["options"])}
    )
    assert r.status_code == 401
    # falsche Herkunft (Phishing-Seite) wird abgelehnt
    opts = c.post("/api/auth/passkey/options").json()
    r = c.post(
        "/api/auth/passkey/login",
        json={
            "id": opts["id"],
            "credential": a.get(opts["options"], origin="https://tesseract.example.org.evil"),
        },
    )
    assert r.status_code == 401
    # fremder Schlüssel
    other = Authenticator()
    other.cred_id = a.cred_id
    opts = c.post("/api/auth/passkey/options").json()
    r = c.post(
        "/api/auth/passkey/login", json={"id": opts["id"], "credential": other.get(opts["options"])}
    )
    assert r.status_code == 401


def test_passkey_delete_guard(auth_client: TestClient) -> None:
    a = Authenticator()
    pk = _register(auth_client, a)
    assert (
        auth_client.put("/api/settings/admin-auth", json={"password_login": False}).status_code
        == 200
    )
    # letzter Weg hinein – nicht löschbar
    assert auth_client.delete(f"/api/auth/passkeys/{pk['id']}").status_code == 409
    auth_client.put("/api/settings/admin-auth", json={"password_login": True})
    assert auth_client.delete(f"/api/auth/passkeys/{pk['id']}").status_code == 204
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert {"passkey_added", "passkey_removed"} <= set(actions)


def test_cli_password_login_on(auth_client: TestClient, idp: FakeIdP, monkeypatch) -> None:
    from tesseract import sso
    from tesseract.cli import run

    _enable_sso(auth_client)
    auth_client.put("/api/settings/admin-auth", json={"password_login": False})
    monkeypatch.setattr("tesseract.cli.get_settings", lambda: auth_client.app.state.settings)
    run(["admin", "password-login", "on"])
    with auth_client.app.state.db.sessionmaker() as db:
        assert sso.get_config(db)["password_login"] is True
