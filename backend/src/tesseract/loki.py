"""Loki oder VictoriaLogs als zusätzlicher Log-Speicher.

Die zentrale Log-Ansicht und die Statistik arbeiten weiter mit SQLite (Aufbewahrung
`logs_days`). Ist eine Loki-URL eingestellt, schickt der Controller jeden neuen Eintrag
zusätzlich an Loki (Push-API). Dort lassen sich die Logs beliebig lange aufbewahren und in
Grafana mit LogQL auswerten.

Labels (wenige Werte, damit Loki schnell bleibt): `job="tesseract"`, `node`, `host`, `reason`.
Alles andere steht als JSON in der Zeile – in Grafana z. B.
`{job="tesseract"} | json | status >= 500`.

VictoriaLogs (`loki_kind = "victorialogs"`) bekommt dieselben Einträge über seine eigene
JSON-Lines-Schnittstelle (`/insert/jsonline`): die Labels als Stream-Felder, alle anderen Werte
als einzelne Felder, `_msg` als kurze Zusammenfassung. Abfrage z. B. mit LogsQL
`{job="tesseract", reason="waf"} status:>=400`. Mandant: `AccountID` oder `AccountID:ProjectID`.
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger("tesseract.loki")

PUSH_PATH = "/loki/api/v1/push"
VL_PATH = "/insert/jsonline"
VL_PARAMS = {
    "_stream_fields": "job,node,host,reason",
    "_time_field": "_time",
    "_msg_field": "_msg",
}
LABEL = {"loki": "Loki", "victorialogs": "VictoriaLogs"}
MAX_QUEUE = 50_000
BATCH = 2_000
INTERVAL = 2.0
# nach einem Fehler länger warten, höchstens so lange
MAX_BACKOFF = 60.0


def push_url(base: str, kind: str = "loki") -> str:
    base = base.strip().rstrip("/")
    path = VL_PATH if kind == "victorialogs" else PUSH_PATH
    return base if base.endswith(path) else base + path


def _ns(ts: datetime) -> str:
    return str(int(ts.timestamp() * 1_000_000_000))


class LokiShipper:
    """Puffert neue Log-Einträge im Speicher und schickt sie gebündelt an Loki.

    Ist Loki nicht erreichbar, bleiben die Einträge im Puffer (höchstens `MAX_QUEUE`, die
    ältesten fallen dann heraus und werden als verworfen gezählt)."""

    def __init__(self, max_queue: int = MAX_QUEUE) -> None:
        self.queue: deque[dict[str, Any]] = deque()
        self.max_queue = max_queue
        self.pushed = 0
        self.dropped = 0
        self.last_push_at: datetime | None = None
        self.last_error: str | None = None
        self.enabled = False

    def add(self, entry: dict[str, Any]) -> None:
        if not self.enabled:
            return
        if len(self.queue) >= self.max_queue:
            self.queue.popleft()
            self.dropped += 1
        self.queue.append(entry)

    def take(self, n: int = BATCH) -> list[dict[str, Any]]:
        return [self.queue.popleft() for _ in range(min(n, len(self.queue)))]

    def requeue(self, batch: list[dict[str, Any]]) -> None:
        """Fehlgeschlagenen Stapel wieder vorne einreihen (Reihenfolge bleibt erhalten)."""
        room = self.max_queue - len(self.queue)
        keep = batch[-room:] if room > 0 else []
        self.dropped += len(batch) - len(keep)
        self.queue.extendleft(reversed(keep))

    def status(self) -> dict[str, Any]:
        return {
            "queued": len(self.queue),
            "pushed": self.pushed,
            "dropped": self.dropped,
            "last_push_at": self.last_push_at,
            "last_error": self.last_error,
        }


def payload(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Einträge nach Labels gruppiert im Format der Loki-Push-API."""
    streams: dict[tuple[str, str, str], list[list[str]]] = {}
    for e in entries:
        key = (e["node"], e["host"] or "-", e["reason"])
        line = {k: v for k, v in e.items() if k not in ("ts", "node", "host", "reason")}
        line = {k: v for k, v in line.items() if v not in (None, "", [])}
        streams.setdefault(key, []).append(
            [_ns(e["ts"]), json.dumps(line, ensure_ascii=False, separators=(",", ":"))]
        )
    return {
        "streams": [
            {
                "stream": {"job": "tesseract", "node": n, "host": h, "reason": r},
                "values": sorted(values, key=lambda v: int(v[0])),
            }
            for (n, h, r), values in streams.items()
        ]
    }


def _summary(e: dict[str, Any]) -> str:
    if e.get("msg"):
        return str(e["msg"])
    text = f"{e.get('method') or '-'} {e['host'] or '-'}{e.get('uri') or ''} {e.get('status', '')}"
    if e.get("waf_msg"):
        text += f" – {e['waf_msg']}"
    return text.strip()


def jsonlines(entries: list[dict[str, Any]]) -> str:
    """Einträge als JSON-Zeilen für VictoriaLogs (`/insert/jsonline`)."""
    out = []
    for e in entries:
        row: dict[str, Any] = {
            "_time": e["ts"].isoformat().replace("+00:00", "Z"),
            "_msg": _summary(e),
            "job": "tesseract",
            "node": e["node"],
            "host": e["host"] or "-",
            "reason": e["reason"],
        }
        for k, v in e.items():
            if k not in ("ts", "node", "host", "reason", "msg") and v not in (None, "", []):
                row[k] = v
        out.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(out) + "\n"


def _vl_headers(tenant: str) -> dict[str, str]:
    if not tenant:
        return {}
    account, _, project = tenant.partition(":")
    headers = {"AccountID": account.strip()}
    if project.strip():
        headers["ProjectID"] = project.strip()
    return headers


def send(
    url: str,
    entries: list[dict[str, Any]],
    tenant: str = "",
    transport: httpx.BaseTransport | None = None,
    kind: str = "loki",
) -> None:
    """Schickt einen Stapel an Loki bzw. VictoriaLogs. Wirft `httpx.HTTPError` bzw.
    `ValueError` bei Fehlern."""
    with httpx.Client(transport=transport, timeout=10.0) as client:
        if kind == "victorialogs":
            r = client.post(
                push_url(url, kind),
                params=VL_PARAMS,
                content=jsonlines(entries).encode(),
                headers={"Content-Type": "application/stream+json", **_vl_headers(tenant)},
            )
        else:
            headers = {"X-Scope-OrgID": tenant} if tenant else {}
            r = client.post(push_url(url), json=payload(entries), headers=headers)
    if r.status_code >= 300:
        raise ValueError(f"{LABEL.get(kind, 'Loki')} antwortet {r.status_code}: {r.text[:200]}")


def ready(
    url: str,
    tenant: str = "",
    transport: httpx.BaseTransport | None = None,
    kind: str = "loki",
) -> str | None:
    """Verbindungstest: schickt einen Test-Eintrag. Gibt eine Fehlermeldung oder None zurück."""
    from tesseract.db.models import utcnow

    entry = {"ts": utcnow(), "node": "tesseract", "host": "-", "reason": "test"}
    try:
        send(url, [{**entry, "msg": "Verbindungstest"}], tenant, transport, kind)
    except (httpx.HTTPError, ValueError) as e:
        return str(e) or e.__class__.__name__
    return None


def flush(
    shipper: LokiShipper, url: str, tenant: str = "", transport=None, kind: str = "loki"
) -> bool:
    """Einen Stapel senden. True = gesendet (oder nichts zu tun)."""
    batch = shipper.take()
    if not batch:
        return True
    try:
        send(url, batch, tenant, transport, kind)
    except (httpx.HTTPError, ValueError) as e:
        shipper.requeue(batch)
        msg = str(e) or e.__class__.__name__
        if msg != shipper.last_error:
            log.warning("%s nicht erreichbar: %s", LABEL.get(kind, "Loki"), msg)
        shipper.last_error = msg
        return False
    from tesseract.db.models import utcnow

    shipper.pushed += len(batch)
    shipper.last_push_at = utcnow()
    shipper.last_error = None
    return True


async def watch(app) -> None:
    """Hintergrund-Aufgabe: Puffer regelmäßig an Loki bzw. VictoriaLogs übertragen."""
    from tesseract.services import get_general

    shipper: LokiShipper = app.state.logs.loki
    backoff = INTERVAL
    while True:
        try:
            with app.state.db.sessionmaker() as db:
                g = get_general(db)
            url, tenant, kind = g["loki_url"], g["loki_tenant"], g["loki_kind"]
            shipper.enabled = bool(url)
            if not url:
                shipper.queue.clear()
                backoff = INTERVAL
            else:
                ok = True
                start = time.monotonic()
                # alles Aufgelaufene senden, aber höchstens ein paar Sekunden am Stück
                while shipper.queue and ok and time.monotonic() - start < 10:
                    ok = await asyncio.to_thread(
                        flush,
                        shipper,
                        url,
                        tenant,
                        getattr(app.state, "loki_transport", None),
                        kind,
                    )
                backoff = INTERVAL if ok else min(MAX_BACKOFF, backoff * 2)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Loki: Fehler beim Übertragen")
        await asyncio.sleep(backoff)
