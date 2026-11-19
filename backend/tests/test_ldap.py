"""LDAP-Abgleich gegen ein Verzeichnis im Speicher (ldap3 MOCK_SYNC)."""

import ldap3
import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeCaddy

BASE = "dc=beispiel,dc=de"
USERS = f"ou=people,{BASE}"
GROUPS = f"ou=groups,{BASE}"


class Directory:
    """Hält die Einträge; jede Verbindung bekommt eine frische Mock-Kopie."""

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}
        self.password = "bind-geheim"

    def add_user(self, uid: str, name: str, mail: str = "", locked: bool = False) -> str:
        dn = f"uid={uid},{USERS}"
        attrs = {"objectClass": ["inetOrgPerson", "person"], "uid": uid, "cn": name}
        if mail:
            attrs["mail"] = mail
        if locked:
            attrs["nsAccountLock"] = "TRUE"
        self.entries[dn] = attrs
        return dn

    def add_group(self, cn: str, members: list[str]) -> None:
        self.entries[f"cn={cn},{GROUPS}"] = {
            "objectClass": ["groupOfNames"],
            "cn": cn,
            "member": members or [""],
        }

    def factory(self, cfg, password):
        server = ldap3.Server("mock")
        conn = ldap3.Connection(
            server,
            user=cfg["bind_dn"],
            password=password,
            client_strategy=ldap3.MOCK_SYNC,
        )
        conn.strategy.add_entry(
            cfg["bind_dn"], {"userPassword": self.password, "objectClass": "person"}
        )
        for dn, attrs in self.entries.items():
            conn.strategy.add_entry(dn, attrs)
        if not conn.bind():
            from ldap3.core.exceptions import LDAPBindError

            raise LDAPBindError("invalidCredentials")
        return conn


@pytest.fixture
def directory(auth_client: TestClient) -> Directory:
    d = Directory()
    auth_client.app.state.ldap_factory = d.factory
    return d


def _configure(c: TestClient, **kw) -> None:
    r = c.put(
        "/api/settings/ldap",
        json={
            "enabled": True,
            "url": "ldap://ldap.beispiel.de",
            "bind_dn": f"cn=admin,{BASE}",
            "bind_password": "bind-geheim",
            "user_base": USERS,
            "group_base": GROUPS,
            "disabled_filter": "(nsAccountLock=TRUE)",
            **kw,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["bind_password_set"] is True and "bind_password_enc" not in r.json()


def _sync(c: TestClient, **params) -> dict:
    r = c.post("/api/settings/ldap/sync", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_sync_creates_persons_and_groups(auth_client: TestClient, directory: Directory) -> None:
    anna = directory.add_user("anna", "Anna Muster", "anna@beispiel.de")
    ben = directory.add_user("ben", "Ben Beispiel")
    directory.add_group("familie", [anna, ben])
    directory.add_group("gaeste", [ben])
    _configure(auth_client)

    preview = _sync(auth_client, dry_run=True)
    assert preview["dry_run"] is True and sorted(preview["created"]) == [
        "Anna Muster",
        "Ben Beispiel",
    ]
    assert auth_client.get("/api/persons").json() == []  # Vorschau ändert nichts

    r = _sync(auth_client)
    assert r["ok"] is True and r["users"] == 2 and r["groups"] == 2
    persons = {p["name"]: p for p in auth_client.get("/api/persons").json()}
    assert set(persons) == {"Anna Muster", "Ben Beispiel"}
    groups = {g["name"]: g for g in auth_client.get("/api/groups").json()}
    assert {"familie", "gaeste", "Admin"} <= set(groups)
    # zweiter Lauf: keine Änderungen
    again = _sync(auth_client)
    assert again["created"] == [] and again["memberships_changed"] == 0


def test_disabled_or_removed_users_are_locked_with_devices(
    auth_client: TestClient, directory: Directory, caddy: FakeCaddy
) -> None:
    auth_client.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"})
    anna = directory.add_user("anna", "Anna")
    directory.add_user("ben", "Ben")
    directory.add_group("familie", [anna])
    _configure(auth_client)
    _sync(auth_client)
    anna_id = next(p["id"] for p in auth_client.get("/api/persons").json() if p["name"] == "Anna")
    dev = auth_client.post(f"/api/persons/{anna_id}/devices", json={"name": "iPhone"}).json()[
        "device"
    ]

    directory.entries[anna]["nsAccountLock"] = "TRUE"  # in LDAP deaktiviert
    loads = len(caddy.loaded)
    r = _sync(auth_client)
    assert r["disabled"] == ["Anna"] and r["revoked_devices"] == 1
    assert len(caddy.loaded) > loads  # Freigaben neu übertragen
    devs = {d["id"]: d for d in auth_client.get("/api/devices").json()}
    assert devs[dev["id"]]["status"] == "revoked"

    # Ben verschwindet aus LDAP → gesperrt
    del directory.entries[f"uid=ben,{USERS}"]
    assert _sync(auth_client)["disabled"] == ["Ben"]
    # Anna wieder aktiv → Person entsperrt (Geräte bleiben widerrufen)
    del directory.entries[anna]["nsAccountLock"]
    assert _sync(auth_client)["enabled"] == ["Anna"]


def test_safety_and_errors(auth_client: TestClient, directory: Directory) -> None:
    directory.add_user("anna", "Anna")
    _configure(auth_client)
    _sync(auth_client)
    # plötzlich keine Personen (falscher Filter) → nichts ändern
    _configure(auth_client, user_filter="(objectClass=gibtsnicht)")
    r = _sync(auth_client)
    assert r["ok"] is False and "nichts geändert" in r["error"]
    assert all(not p["disabled"] for p in auth_client.get("/api/persons").json())
    # falsches Passwort
    directory.password = "anders"
    _configure(auth_client)
    r = _sync(auth_client)
    assert r["ok"] is False and "fehlgeschlagen" in r["error"]
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert {"ldap_synced", "ldap_sync_failed"} <= set(actions)


def test_existing_manual_person_is_linked(auth_client: TestClient, directory: Directory) -> None:
    auth_client.post("/api/persons", json={"name": "Anna"})
    directory.add_user("anna", "Anna", "anna@beispiel.de")
    _configure(auth_client)
    r = _sync(auth_client)
    assert r["created"] == [] and r["updated"] == ["Anna"]
    assert len(auth_client.get("/api/persons").json()) == 1


def test_validation(auth_client: TestClient) -> None:
    r = auth_client.put("/api/settings/ldap", json={"enabled": True, "url": "http://x"})
    assert r.status_code == 422
