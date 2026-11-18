"""Phase 5: Prometheus-Metriken für Controller und alle Nodes (Textformat 0.0.4).

- Zähler aus den gesammelten Logs (seit Start des Controllers – Prometheus kommt mit
  Neustarts von Zählern zurecht), Zustand von Nodes, Hosts, Geräten, Sperren, CA.
- Optional die Caddy-Metriken jedes Nodes mit Label `node`: den lokalen Caddy fragt der
  Controller beim Abruf, die Agents schicken ihre mit der Statusmeldung.
"""

import re
import threading
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tesseract import __version__
from tesseract.db.models import Device, Host, Node, utcnow

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
CADDY_MAX_AGE = 300.0

# Beschreibung für die Einstellungen-Seite (Name, Typ, Bedeutung)
CATALOG = [
    ("tesseract_requests_total", "counter", "Anfragen pro Node, Host, Statusklasse und Grund"),
    ("tesseract_request_duration_seconds", "histogram", "Antwortzeit durchgelassener Anfragen"),
    ("tesseract_response_bytes_total", "counter", "Bytes an Clients pro Node und Host"),
    ("tesseract_waf_blocked_total", "counter", "Von Coraza blockierte Anfragen pro Node und Host"),
    ("tesseract_node_up", "gauge", "1 = Node erreichbar (Agent meldet sich bzw. Caddy antwortet)"),
    ("tesseract_node_last_seen_timestamp_seconds", "gauge", "Letzter Kontakt (Unix-Zeit)"),
    ("tesseract_node_config_in_sync", "gauge", "1 = Node hat den Stand des Controllers geladen"),
    ("tesseract_node_drift", "gauge", "1 = laufende Config weicht ab (lokal geändert)"),
    ("tesseract_hosts", "gauge", "Aktive Hosts pro Node"),
    ("tesseract_bans_active", "gauge", "Zurzeit gesperrte IPs"),
    ("tesseract_devices", "gauge", "Geräte nach Status"),
    ("tesseract_info", "gauge", "Version des Controllers"),
    ("caddy_*", "verschieden", "Metriken der Caddys mit Label node (wenn eingeschaltet)"),
]


def _esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**kw: Any) -> str:
    return "{" + ",".join(f'{k}="{_esc(v)}"' for k, v in kw.items()) + "}"


class Metrics:
    """Zähler im Speicher; gefüttert beim Einlesen der Logs."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: dict[tuple[str, str, str, str], int] = defaultdict(int)
        self.bytes: dict[tuple[str, str], int] = defaultdict(int)
        self.waf: dict[tuple[str, str], int] = defaultdict(int)
        self.hist: dict[tuple[str, str], list[float]] = {}
        # Caddy-Metriken der Agents: Node-Name → (Text, Zeitpunkt)
        self.caddy: dict[str, tuple[str, float]] = {}

    def observe(
        self, node: str, host: str, status: int, reason: str, duration_ms: float, size: int
    ) -> None:
        klass = f"{status // 100}xx" if status else "abgebrochen"
        with self.lock:
            self.requests[(node, host, klass, reason)] += 1
            self.bytes[(node, host)] += size
            if reason == "waf":
                self.waf[(node, host)] += 1
            if reason == "ok":
                h = self.hist.setdefault((node, host), [0.0] * (len(BUCKETS) + 2))
                sec = duration_ms / 1000
                for i, b in enumerate(BUCKETS):
                    if sec <= b:
                        h[i] += 1
                h[len(BUCKETS)] += 1  # count
                h[len(BUCKETS) + 1] += sec  # sum

    def set_caddy(self, node: str, text: str) -> None:
        with self.lock:
            self.caddy[node] = (text, time.monotonic())

    def render_counters(self) -> list[str]:
        out: list[str] = []
        with self.lock:
            out += [
                "# HELP tesseract_requests_total Anfragen aus den Zugriffs-Logs",
                "# TYPE tesseract_requests_total counter",
            ]
            for (node, host, klass, reason), n in sorted(self.requests.items()):
                lbl = _labels(node=node, host=host, status=klass, reason=reason)
                out.append(f"tesseract_requests_total{lbl} {n}")
            out += [
                "# HELP tesseract_response_bytes_total Bytes an Clients",
                "# TYPE tesseract_response_bytes_total counter",
            ]
            for (node, host), n in sorted(self.bytes.items()):
                out.append(f"tesseract_response_bytes_total{_labels(node=node, host=host)} {n}")
            out += [
                "# HELP tesseract_waf_blocked_total Von Coraza blockierte Anfragen",
                "# TYPE tesseract_waf_blocked_total counter",
            ]
            for (node, host), n in sorted(self.waf.items()):
                out.append(f"tesseract_waf_blocked_total{_labels(node=node, host=host)} {n}")
            out += [
                "# HELP tesseract_request_duration_seconds Antwortzeit durchgelassener Anfragen",
                "# TYPE tesseract_request_duration_seconds histogram",
            ]
            for (node, host), h in sorted(self.hist.items()):
                for i, b in enumerate(BUCKETS):
                    lbl = _labels(node=node, host=host, le=b)
                    out.append(f"tesseract_request_duration_seconds_bucket{lbl} {int(h[i])}")
                count = int(h[len(BUCKETS)])
                lbl = _labels(node=node, host=host, le="+Inf")
                out.append(f"tesseract_request_duration_seconds_bucket{lbl} {count}")
                base = _labels(node=node, host=host)
                out.append(f"tesseract_request_duration_seconds_count{base} {count}")
                out.append(
                    f"tesseract_request_duration_seconds_sum{base} {h[len(BUCKETS) + 1]:.6f}"
                )
        return out


def render_state(db: Session, settings: Any) -> list[str]:
    from tesseract import nodes as node_svc
    from tesseract.services import active_bans, node_in_sync

    now = utcnow()
    hosts = dict(
        db.execute(
            select(Host.node_id, func.count())
            .where(Host.enabled, Host.draft.is_(False))
            .group_by(Host.node_id)
        ).all()
    )
    out = [
        "# HELP tesseract_info Version des Controllers",
        "# TYPE tesseract_info gauge",
        f"tesseract_info{_labels(version=__version__)} 1",
    ]
    rows: dict[str, list[str]] = defaultdict(list)
    for n in db.scalars(select(Node).order_by(Node.name)):
        if not n.joined:
            continue
        lbl = _labels(node=n.name, kind=n.kind)
        state = node_svc.state(n, now)
        rows["tesseract_node_up"].append(f"tesseract_node_up{lbl} {int(state != 'offline')}")
        if n.last_seen_at:
            rows["tesseract_node_last_seen_timestamp_seconds"].append(
                f"tesseract_node_last_seen_timestamp_seconds{lbl} {n.last_seen_at.timestamp():.0f}"
            )
        sync = int(node_in_sync(db, n, settings))
        rows["tesseract_node_config_in_sync"].append(f"tesseract_node_config_in_sync{lbl} {sync}")
        rows["tesseract_node_drift"].append(f"tesseract_node_drift{lbl} {int(n.drift)}")
        rows["tesseract_hosts"].append(f"tesseract_hosts{lbl} {hosts.get(n.id, 0)}")
    for name, lines in rows.items():
        out += [f"# TYPE {name} gauge", *lines]
    out += [
        "# TYPE tesseract_bans_active gauge",
        f"tesseract_bans_active {len(active_bans(db))}",
    ]
    counts: dict[str, int] = defaultdict(int)
    for d in db.scalars(select(Device)):
        counts[d.status] += 1
    out.append("# TYPE tesseract_devices gauge")
    out += [f"tesseract_devices{_labels(status=s)} {n}" for s, n in sorted(counts.items())]
    return out


_LINE_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(.*)$")
_SUFFIXES = ("_bucket", "_sum", "_count")


def _family(name: str, known: set[str]) -> str:
    if name in known:
        return name
    for suf in _SUFFIXES:
        if name.endswith(suf) and name[: -len(suf)] in known:
            return name[: -len(suf)]
    return name


def relabel_caddy(text: str, node: str, families: dict[str, dict[str, list[str]]]) -> None:
    """Nur caddy_*-Metriken, mit Label node, nach Metrik-Familie einsortiert (das Textformat
    verlangt, dass alle Zeilen einer Familie zusammenstehen)."""
    known = {
        line.split()[2]
        for line in text.splitlines()
        if line.startswith("# TYPE caddy_") and len(line.split()) >= 4
    }
    for line in text.splitlines():
        if line.startswith(("# HELP caddy_", "# TYPE caddy_")):
            fam = families.setdefault(line.split()[2], {"meta": [], "values": []})
            if line not in fam["meta"]:
                fam["meta"].append(line)
            continue
        m = _LINE_RE.match(line)
        if not m or not m.group(1).startswith("caddy_"):
            continue
        name, labels, rest = m.groups()
        inner = labels[1:-1] if labels else ""
        new = f'node="{_esc(node)}"' + ("," + inner if inner else "")
        fam = families.setdefault(_family(name, known), {"meta": [], "values": []})
        fam["values"].append(f"{name}{{{new}}} {rest}")


def caddy_only(text: str) -> str:
    """Für den Agent: nur die caddy_*-Zeilen (kleiner)."""
    keep = [
        line
        for line in text.splitlines()
        if line.startswith(("caddy_", "# HELP caddy_", "# TYPE caddy_"))
    ]
    return chr(10).join(keep)


def render(
    db: Session, settings: Any, metrics: Metrics, caddy_local: dict[str, str] | None = None
) -> str:
    lines = render_state(db, settings) + metrics.render_counters()
    texts = dict(caddy_local or {})
    with metrics.lock:
        now = time.monotonic()
        for node, (text, ts) in metrics.caddy.items():
            if now - ts <= CADDY_MAX_AGE and node not in texts:
                texts[node] = text
    families: dict[str, dict[str, list[str]]] = {}
    for node, text in sorted(texts.items()):
        relabel_caddy(text, node, families)
    for fam in families.values():
        lines += fam["meta"] + fam["values"]
    return chr(10).join(lines) + chr(10)
