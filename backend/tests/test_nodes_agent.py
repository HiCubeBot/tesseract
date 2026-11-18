"""Phase 4: Nodes mit Agent – Beitritt, Config-Verteilung, Status, Abweichung, WAF-Treffer."""

import base64
import json

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from fastapi.testclient import TestClient

from tesseract import pki
from tesseract.caddy.client import CaddyClient
from tesseract.caddy.config import CONTROLLER_PUBLIC_PATHS, FINGERPRINT_HEADER, config_hash
from tesseract.db.models import Node
from tesseract.nodes import check_local, json_diff, probe_modules
from tests.conftest import FakeCaddy


def _ca(c: TestClient) -> None:
    assert c.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"}).status_code == 200


def _csr(key: ec.EllipticCurvePrivateKey) -> str:
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pi")]))
        .sign(key, hashes.SHA256())
    )
    return csr.public_bytes(serialization.Encoding.PEM).decode()


class Agent:
    """Spielt den Agent: Beitritt, dann Anfragen mit Fingerabdruck (wie von Caddy) + Token."""

    def __init__(self, c: TestClient, token: str) -> None:
        self.c = c
        self.key = ec.generate_private_key(ec.SECP256R1())
        r = c.post(
            "/api/agent/join",
            json={"token": token, "csr": _csr(self.key), "hostname": "raspberrypi"},
        )
        assert r.status_code == 200, r.text
        self.join = r.json()
        self.headers: dict[str, str] = {}

    def pickup(self) -> httpx.Response:
        return self.c.get(
            f"/api/agent/join/{self.join['node_id']}",
            headers={"X-Join-Secret": self.join["secret"]},
        )

    def connect(self) -> dict:
        r = self.pickup()
        assert r.status_code == 200, r.text
        data = r.json()
        cert = x509.load_pem_x509_certificate(data["cert_pem"].encode())
        self.headers = {
            FINGERPRINT_HEADER: pki.fingerprint(cert),
            "Authorization": f"Bearer {data['agent_token']}",
        }
        return data

    def get(self, path: str, **kw) -> httpx.Response:
        return self.c.get(path, headers=self.headers, **kw)

    def post(self, path: str, body: dict) -> httpx.Response:
        return self.c.post(path, json=body, headers=self.headers)


def _new_node(c: TestClient, name: str = "pi-eltern") -> dict:
    r = c.post("/api/nodes", json={"name": name, "location": "Elternhaus"})
    assert r.status_code == 201, r.text
    return r.json()


def _joined(c: TestClient) -> tuple[Agent, dict]:
    _ca(c)
    created = _new_node(c)
    agent = Agent(c, created["join"]["token"])
    node_id = created["node"]["id"]
    assert c.post(f"/api/nodes/{node_id}/approve").status_code == 200
    agent.connect()
    return agent, created


def _node(c: TestClient, node_id: int) -> dict:
    return next(n for n in c.get("/api/nodes").json() if n["id"] == node_id)


def test_create_requires_ca_and_valid_name(auth_client: TestClient) -> None:
    r = auth_client.post("/api/nodes", json={"name": "pi"})
    assert r.status_code == 409 and "Zertifizierungsstelle" in r.json()["detail"]
    _ca(auth_client)
    assert auth_client.post("/api/nodes", json={"name": "Pi Eltern!"}).status_code == 422
    created = _new_node(auth_client, "Pi-Eltern")
    assert created["node"]["name"] == "pi-eltern"
    assert created["node"]["state"] == "pending" and created["node"]["join_open"] is True
    assert created["join"]["command"].startswith(
        "tesseract-agent join --controller https://tesseract.example.org --token "
    )
    assert auth_client.post("/api/nodes", json={"name": "pi-eltern"}).status_code == 409


def test_join_flow(auth_client: TestClient) -> None:
    _ca(auth_client)
    created = _new_node(auth_client)
    token, node_id = created["join"]["token"], created["node"]["id"]

    r = auth_client.post("/api/agent/join", json={"token": "falsch", "csr": "x"})
    assert r.status_code == 403
    r = auth_client.post("/api/agent/join", json={"token": token, "csr": "kein csr"})
    assert r.status_code == 422

    agent = Agent(auth_client, token)
    assert agent.join["name"] == "pi-eltern"
    # Token ist verbraucht
    again = auth_client.post(
        "/api/agent/join",
        json={"token": token, "csr": _csr(ec.generate_private_key(ec.SECP256R1()))},
    )
    assert again.status_code == 403

    node = _node(auth_client, node_id)
    assert node["join_state"] == "pending" and node["join_hostname"] == "raspberrypi"
    assert node["join_key_fingerprint"] == pki.public_key_fingerprint(agent.key.public_key())
    assert agent.pickup().status_code == 202
    wrong = auth_client.get(f"/api/agent/join/{node_id}", headers={"X-Join-Secret": "nein"})
    assert wrong.status_code == 404

    assert auth_client.post(f"/api/nodes/{node_id}/approve").status_code == 200
    data = agent.connect()
    cert = x509.load_pem_x509_certificate(data["cert_pem"].encode())
    assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "node:pi-eltern"
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert ExtendedKeyUsageOID.CLIENT_AUTH in eku
    assert cert.public_key().public_numbers() == agent.key.public_key().public_numbers()
    assert "BEGIN CERTIFICATE" in data["chain_pem"]
    # nur einmal abholbar
    assert agent.pickup().status_code == 404

    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert {"node_created", "node_join_requested", "node_approved", "node_joined"} <= set(actions)


def test_reject(auth_client: TestClient) -> None:
    _ca(auth_client)
    created = _new_node(auth_client)
    agent = Agent(auth_client, created["join"]["token"])
    assert auth_client.post(f"/api/nodes/{created['node']['id']}/reject").status_code == 200
    assert agent.pickup().status_code == 403
    assert auth_client.post(f"/api/nodes/{created['node']['id']}/approve").status_code == 409


def test_agent_auth_needs_certificate_and_token(auth_client: TestClient) -> None:
    agent, _ = _joined(auth_client)
    assert agent.get("/api/agent/config").status_code == 200
    no_cert = {"Authorization": agent.headers["Authorization"]}
    assert auth_client.get("/api/agent/config", headers=no_cert).status_code == 401
    bad_token = {**agent.headers, "Authorization": "Bearer falsch"}
    assert auth_client.get("/api/agent/config", headers=bad_token).status_code == 401


def test_config_distribution(auth_client: TestClient, caddy: FakeCaddy) -> None:
    agent, created = _joined(auth_client)
    node_id = created["node"]["id"]
    local_loads = len(caddy.loaded)

    host = {
        "domain": "home.example.org",
        "node_id": node_id,
        "upstream_scheme": "http",
        "upstream_host": "192.168.178.5",
        "upstream_port": 8123,
    }
    r = auth_client.post("/api/hosts", json=host)
    assert r.status_code == 201 and r.json()["apply"]["ok"] is True
    # Der lokale Caddy bekommt den Host nicht
    assert all("home.example.org" not in json.dumps(cfg) for cfg in caddy.loaded[local_loads:])

    r = agent.get("/api/agent/config")
    body = r.json()
    domains = json.dumps(body["config"])
    assert "home.example.org" in domains
    # keine Route für die Oberfläche auf fremden Nodes
    assert "tesseract.example.org" not in domains
    assert body["config"]["admin"]["listen"] == "0.0.0.0:2019"
    assert body["hash"] == config_hash(body["config"])

    # bekannt → 204 (Long-Polling endet ohne Änderung)
    r = agent.get("/api/agent/config", params={"known": body["hash"], "force": body["force"]})
    assert r.status_code == 204
    assert _node(auth_client, node_id)["in_sync"] is False

    status = {"agent_version": "0.1.0", "loaded_hash": body["hash"], "running_hash": body["hash"]}
    status["modules"] = ["http.handlers.waf"]
    assert agent.post("/api/agent/status", status).status_code == 200
    node = _node(auth_client, node_id)
    assert node["in_sync"] is True and node["state"] == "online"
    assert node["modules"] == ["http.handlers.waf"] and node["hosts"] == 1


def test_drift_overwrite_and_accept(auth_client: TestClient) -> None:
    agent, created = _joined(auth_client)
    node_id = created["node"]["id"]
    body = agent.get("/api/agent/config").json()
    h, force = body["hash"], body["force"]

    changed = json.loads(json.dumps(body["config"]))
    changed["admin"]["listen"] = "0.0.0.0:2020"
    status = {
        "loaded_hash": h,
        "running_hash": config_hash(changed),
        "running_config_b64": base64.b64encode(json.dumps(changed).encode()).decode(),
    }
    assert agent.post("/api/agent/status", status).status_code == 200
    node = _node(auth_client, node_id)
    assert node["drift"] is True and node["state"] == "drift"
    drift = auth_client.get(f"/api/nodes/{node_id}/drift").json()
    assert drift["changes"] == [
        {
            "path": "admin.listen",
            "before": "0.0.0.0:2019",
            "after": "0.0.0.0:2020",
            "kind": "changed",
            "host": None,
        }
    ]

    # Überschreiben: der Agent bekommt die Config erneut (force steigt)
    assert auth_client.post(f"/api/nodes/{node_id}/overwrite").json()["ok"] is True
    again = agent.get("/api/agent/config", params={"known": h, "force": force})
    assert again.status_code == 200 and again.json()["force"] == force + 1

    # Übernehmen: Abweichung gilt als in Ordnung
    assert agent.post("/api/agent/status", status).status_code == 200
    r = auth_client.post(f"/api/nodes/{node_id}/accept")
    assert r.status_code == 200 and r.json()["drift"] is False and r.json()["accepted"] is True
    assert auth_client.get(f"/api/nodes/{node_id}/drift").json()["drift"] is False
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert {"node_drift_detected", "node_drift_overwritten", "node_drift_accepted"} <= set(actions)


def test_waf_hits_from_agent_ban(auth_client: TestClient, caddy: FakeCaddy) -> None:
    agent, _ = _joined(auth_client)
    auth_client.put("/api/settings/general", json={"autoban_hits": 3})
    line = json.dumps(
        {"msg": "WAF rule violation detected", "client_ip": "203.0.113.7", "hostname": "x"}
    )
    r = agent.post("/api/agent/waf", {"lines": [line] * 3 + ["kein json"]})
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 3
    bans = auth_client.get("/api/bans").json()
    assert any(b["ip"] == "203.0.113.7" for b in bans)


def test_delete_and_new_token(auth_client: TestClient) -> None:
    _, created = _joined(auth_client)
    node_id = created["node"]["id"]
    r = auth_client.post(f"/api/nodes/{node_id}/token")
    assert r.status_code == 200 and r.json()["token"]
    assert auth_client.post("/api/nodes/1/token").status_code == 409  # lokaler Node
    host = {
        "domain": "x.example.org",
        "node_id": node_id,
        "upstream_scheme": "http",
        "upstream_host": "10.0.0.1",
        "upstream_port": 80,
    }
    hid = auth_client.post("/api/hosts", json=host).json()["host"]["id"]
    assert auth_client.delete(f"/api/nodes/{node_id}").status_code == 409
    assert auth_client.delete(f"/api/hosts/{hid}").status_code in (200, 204)
    assert auth_client.delete(f"/api/nodes/{node_id}").status_code == 204
    assert auth_client.delete("/api/nodes/1").status_code == 409


def test_agent_path_public_on_protected_controller() -> None:
    assert "/api/agent/*" in CONTROLLER_PUBLIC_PATHS


def test_local_drift_and_modules(auth_client: TestClient, caddy: FakeCaddy) -> None:
    auth_client.post("/api/nodes/1/apply")
    running = json.loads(json.dumps(caddy.last))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/config/":
            return httpx.Response(200, json=running)
        if request.url.path == "/adapt":
            return httpx.Response(200 if b"coraza" in request.content else 400, json={})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    assert probe_modules(CaddyClient("http://caddy", transport=transport)) == ["http.handlers.waf"]
    db = auth_client.app.state.db.sessionmaker()
    node = db.get(Node, 1)
    check_local(db, node, transport, modules=True)
    db.commit()
    assert node.drift is False and node.modules == ["http.handlers.waf"]
    running["admin"]["listen"] = "0.0.0.0:9999"
    check_local(db, node, transport)
    db.commit()
    assert node.drift is True
    db.close()
    assert _node(auth_client, 1)["state"] == "drift"
    # Überschreiben beim lokalen Node = erneut laden
    assert auth_client.post("/api/nodes/1/overwrite").json()["ok"] is True
    assert _node(auth_client, 1)["drift"] is False


def test_json_diff() -> None:
    a = {"x": 1, "l": [1, 2], "d": {"k": "v"}}
    b = {"x": 2, "l": [1, 3], "n": True, "d": {}}
    assert json_diff(a, b) == [
        {"path": "d.k", "before": "v", "after": None, "kind": "removed"},
        {"path": "l[1]", "before": 2, "after": 3, "kind": "changed"},
        {"path": "n", "before": None, "after": True, "kind": "added"},
        {"path": "x", "before": 1, "after": 2, "kind": "changed"},
    ]


def test_internal_controller_domain_gets_local_certificate() -> None:
    from tesseract.caddy.config import NodeSpec, build_config

    cfg = build_config(
        NodeSpec(admin_listen="x", controller_domain="tesseract.lan", controller_upstream="t:8000")
    )
    policies = cfg["apps"]["tls"]["automation"]["policies"]
    assert {"subjects": ["tesseract.lan"], "issuers": [{"module": "internal"}]} in policies


def test_route_host() -> None:
    from tesseract.nodes import route_host

    cfg = {"apps": {"http": {"servers": {"https": {"routes": [{"match": [{"host": ["a.b"]}]}]}}}}}
    assert route_host(cfg, "apps.http.servers.https.routes[0].handle[0]") == "a.b"
    assert route_host(cfg, "apps.http.servers.https.routes[5]") is None
    assert route_host(cfg, "admin.listen") is None


def test_agent_renews_certificate(auth_client: TestClient) -> None:
    agent, created = _joined(auth_client)
    old_fp = agent.headers[FINGERPRINT_HEADER]
    key = ec.generate_private_key(ec.SECP256R1())
    r = agent.post("/api/agent/renew", {"csr": _csr(key)})
    assert r.status_code == 200, r.text
    cert = x509.load_pem_x509_certificate(r.json()["cert_pem"].encode())
    assert cert.public_key().public_numbers() == key.public_key().public_numbers()
    # altes Zertifikat gilt nicht mehr, neues schon
    assert agent.get("/api/agent/config").status_code == 401
    agent.headers[FINGERPRINT_HEADER] = pki.fingerprint(cert)
    assert agent.get("/api/agent/config").status_code == 200
    assert old_fp != agent.headers[FINGERPRINT_HEADER]


def _serve_tasks(agent: Agent, answer, rounds: int = 20) -> list[dict]:
    """Holt Aufgaben wie ein Agent ab und beantwortet sie mit answer(task)."""
    seen = []
    body = agent.get("/api/agent/config").json()
    for _ in range(rounds):
        r = agent.get(
            "/api/agent/config",
            params={"known": body["hash"], "force": body["force"], "wait": 1, "tasks": 1},
        )
        if r.status_code == 200 and r.json().get("tasks"):
            assert r.json()["config"] is None  # Config unverändert → nicht mitschicken
            for t in r.json()["tasks"]:
                seen.append(t)
                agent.post(f"/api/agent/tasks/{t['id']}", {"result": answer(t)})
            return seen
    return seen


def test_upstream_check_from_node(auth_client: TestClient) -> None:
    import threading

    agent, created = _joined(auth_client)
    node_id = created["node"]["id"]
    body = {
        "domain": "home.example.org",
        "node_id": node_id,
        "upstream_host": "192.168.178.5",
        "upstream_port": 8123,
    }
    # Agent 1.0: keine Aufgaben → Hinweis, Prüfung vom Controller
    agent.post("/api/agent/status", {"agent_version": "1.0.0"})
    r = auth_client.post("/api/hosts/check", json=body).json()
    up = next(c for c in r if c["key"] == "upstream")
    assert up["status"] == "info" and "älter als 1.1" in up["detail"]

    agent.post("/api/agent/status", {"agent_version": "1.1.0"})
    out: dict = {}
    t = threading.Thread(
        target=lambda: out.update(r=auth_client.post("/api/hosts/check", json=body).json())
    )
    t.start()
    seen = _serve_tasks(agent, lambda task: {"ok": True, "ms": 3})
    t.join(timeout=15)
    assert seen and seen[0]["kind"] == "tcp" and seen[0]["params"]["host"] == "192.168.178.5"
    up = next(c for c in out["r"] if c["key"] == "upstream")
    assert up["status"] == "ok" and "pi-eltern" in up["detail"]


def test_certificates_from_agent_node(auth_client: TestClient) -> None:
    import threading

    from tests.test_certificates import _cert

    agent, created = _joined(auth_client)
    agent.post("/api/agent/status", {"agent_version": "1.1.0"})
    host = {
        "domain": "home.example.org",
        "node_id": created["node"]["id"],
        "upstream_scheme": "http",
        "upstream_host": "10.0.0.1",
        "upstream_port": 80,
    }
    assert auth_client.post("/api/hosts", json=host).status_code == 201
    pem, _ = _cert(["home.example.org"], "R11", 60)
    der = x509.load_pem_x509_certificate(pem).public_bytes(serialization.Encoding.DER)
    out: dict = {}
    t = threading.Thread(
        target=lambda: out.update(
            r=auth_client.get("/api/certificates", params={"refresh": True}).json()
        )
    )
    t.start()
    seen = _serve_tasks(
        agent,
        lambda task: {
            "certs": {n: {"der": base64.b64encode(der).decode()} for n in task["params"]["names"]}
        },
    )
    t.join(timeout=30)
    assert seen[0]["kind"] == "certs" and seen[0]["params"]["names"] == ["home.example.org"]
    certs = out["r"]["certificates"]
    mine = [c for c in certs if "home.example.org" in c["hosts"]]
    assert mine and mine[0]["node"] == "pi-eltern"
