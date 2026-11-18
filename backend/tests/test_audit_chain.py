"""Phase 5: Audit-Log mit Prüfsummenkette, unveränderlich, Filter, CSV."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from tesseract import audit
from tesseract.db.models import AuditEntry


def test_chain_and_verify(auth_client: TestClient) -> None:
    auth_client.post("/api/hosts/check", json={"domain": "x.example.org"})
    with auth_client.app.state.db.sessionmaker() as db:
        audit.record(db, actor="system", action="ip_banned", target="198.51.100.1")
        audit.record(db, actor="Gast", action="enrollment_requested", target="Anna")
        db.commit()
    entries = auth_client.get("/api/audit").json()
    assert all(e["hash"] for e in entries)
    r = auth_client.get("/api/audit/verify").json()
    assert r["ok"] is True and r["checked"] == len(entries)

    with auth_client.app.state.db.sessionmaker() as db:
        e = db.get(AuditEntry, entries[0]["id"])
        e.target = "geändert"
        with pytest.raises(DatabaseError, match="unveränderlich"):
            db.commit()
        db.rollback()
        db.delete(db.get(AuditEntry, entries[0]["id"]))
        with pytest.raises(DatabaseError, match="unveränderlich"):
            db.commit()
        db.rollback()
        # Wer die Trigger umgeht (direkt in der Datei), fällt bei der Prüfung auf
        db.execute(text("DROP TRIGGER audit_log_no_update"))
        db.execute(
            text("UPDATE audit_log SET target = 'manipuliert' WHERE id = :id"),
            {"id": entries[-1]["id"]},
        )
        db.commit()
    r = auth_client.get("/api/audit/verify").json()
    assert r["ok"] is False and r["broken_id"] == entries[-1]["id"]


def test_kind_filter_and_csv(auth_client: TestClient) -> None:
    with auth_client.app.state.db.sessionmaker() as db:
        audit.record(db, actor="system", action="ip_banned", target="198.51.100.1")
        audit.record(db, actor="Gast", action="enrollment_requested", target="Anna Müller")
        db.commit()
    kinds = {
        k: auth_client.get("/api/audit", params={"kind": k}).json()
        for k in ("admin", "system", "guest")
    }
    assert {e["actor"] for e in kinds["admin"]} == {"admin"}
    assert [e["action"] for e in kinds["system"]] == ["ip_banned"]
    assert [e["target"] for e in kinds["guest"]] == ["Anna Müller"]
    r = auth_client.get("/api/audit/export.csv", params={"kind": "guest"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.content.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("id;zeit_utc;wer") and "Anna Müller" in lines[1]
    assert len(lines) == 2
