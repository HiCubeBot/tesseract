"""DNS-Einträge für Hosts automatisch bei Cloudflare anlegen, ändern und löschen.

Pro Domain (Zone) steht in den Einstellungen, wie Hosts darunter standardmäßig eingetragen
werden (`dns_zones`):

```json
{"zone": "beispiel.de", "type": "cname", "cname_target": "home.beispiel.de",
 "ip_source": "node", "ips": [], "proxied": false}
```

- `type`: `cname` (CNAME auf `cname_target`, z. B. den DDNS-Namen) oder `address`
  (A für IPv4, AAAA für IPv6)
- `ip_source` bei `address`: `node` = öffentliche IPs des Nodes, auf dem der Host läuft
  (Nodes › Bearbeiten), `custom` = die IPs aus `ips`
- `proxied`: über den Cloudflare-Proxy (orange Wolke)

Pro Host: `dns_type` (None = kein Eintrag, `cname`, `address`), `dns_target` (leer = Wert der
Zone; bei `address` IPs kommagetrennt), `dns_proxied`. Tesseract merkt sich die IDs der
Einträge, die es selbst angelegt hat (`dns_records`), und fasst nur diese an – fremde Einträge
mit demselben Namen werden nicht überschrieben, außer sie haben schon den gewünschten Wert.

Der Cloudflare-Token braucht „Zone › Zone › Lesen“ und „Zone › DNS › Bearbeiten“ (dieselben
Rechte wie für DNS-01).
"""

import ipaddress
import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("tesseract.dns")

API = "https://api.cloudflare.com/client/v4"
COMMENT = "Tesseract"
TYPES = ("cname", "address")


class DnsError(Exception):
    pass


@dataclass(frozen=True)
class Record:
    type: str  # CNAME | A | AAAA
    name: str
    content: str
    proxied: bool


# ---------- Zonen ----------


def zone_for(domain: str, zones: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Passende Zone (längste Übereinstimmung), z. B. musik.home.beispiel.de → beispiel.de."""
    name = domain.lower().removeprefix("*.").rstrip(".")
    best = None
    for z in zones:
        zn = z["zone"].lower().rstrip(".")
        if (name == zn or name.endswith("." + zn)) and (
            best is None or len(zn) > len(best["zone"])
        ):
            best = z
    return best


def normalize_zone(z: dict[str, Any]) -> dict[str, Any]:
    """Eingabe prüfen und vereinheitlichen. Wirft ValueError mit verständlicher Meldung."""
    zone = str(z.get("zone", "")).strip().lower().rstrip(".")
    if not zone or "." not in zone or " " in zone:
        raise ValueError(f"„{zone}“ ist keine Domain")
    kind = z.get("type", "cname")
    if kind not in TYPES:
        raise ValueError(f"{zone}: Typ cname oder address")
    target = str(z.get("cname_target", "") or "").strip().lower().rstrip(".")
    if kind == "cname" and not target:
        raise ValueError(f"{zone}: Ziel für den CNAME angeben (z. B. der DDNS-Name)")
    source = z.get("ip_source", "node")
    if source not in ("node", "custom"):
        raise ValueError(f"{zone}: IPs vom Node oder eigene")
    ips = _ips(z.get("ips") or [], zone)
    if kind == "address" and source == "custom" and not ips:
        raise ValueError(f"{zone}: mindestens eine IP angeben")
    return {
        "zone": zone,
        "type": kind,
        "cname_target": target,
        "ip_source": source,
        "ips": ips,
        "proxied": bool(z.get("proxied", False)),
    }


def _ips(values, where: str) -> list[str]:
    out = []
    for raw in values:
        v = str(raw).strip()
        if not v:
            continue
        try:
            ip = str(ipaddress.ip_address(v))
        except ValueError as e:
            raise ValueError(f"{where}: „{v}“ ist keine IP-Adresse") from e
        if ip not in out:
            out.append(ip)
    return out


# ---------- Soll-Zustand ----------


def desired(host, zone: dict[str, Any] | None, node_ips: list[str]) -> list[Record]:
    """Welche Einträge der Host haben soll. Wirft DnsError, wenn etwas fehlt."""
    kind = host.dns_type
    if not kind:
        return []
    if zone is None:
        raise DnsError(
            f"Für {host.domain} ist keine Domain unter Einstellungen › Integrationen › "
            "DNS-Einträge eingerichtet"
        )
    name = host.domain.lower()
    proxied = bool(host.dns_proxied)
    target = (host.dns_target or "").strip()
    if kind == "cname":
        content = (target or zone["cname_target"]).lower().rstrip(".")
        if not content:
            raise DnsError(f"{name}: Ziel für den CNAME fehlt")
        if content == name:
            raise DnsError(f"{name}: CNAME kann nicht auf sich selbst zeigen")
        return [Record("CNAME", name, content, proxied)]
    if target:
        try:
            ips = _ips(target.replace(";", ",").split(","), name)
        except ValueError as e:
            raise DnsError(str(e)) from e
    elif zone["ip_source"] == "custom":
        ips = zone["ips"]
    else:
        ips = list(node_ips)
    if not ips:
        raise DnsError(
            f"{name}: keine IP – am Node unter Nodes › Bearbeiten öffentliche IPs eintragen "
            "oder beim Host bzw. der Domain eigene angeben"
        )
    return [
        Record("AAAA" if ipaddress.ip_address(ip).version == 6 else "A", name, ip, proxied)
        for ip in ips
    ]


# ---------- Cloudflare ----------


class Cloudflare:
    def __init__(self, token: str, transport: httpx.BaseTransport | None = None) -> None:
        if not token:
            raise DnsError(
                "Kein Cloudflare-Token – unter Einstellungen › Integrationen oder "
                "TESSERACT_CLOUDFLARE_TOKEN eintragen"
            )
        self.token = token
        self.transport = transport
        self._zones: dict[str, str] = {}

    def _call(self, method: str, path: str, **kw) -> Any:
        try:
            with httpx.Client(transport=self.transport, timeout=20.0) as c:
                r = c.request(
                    method, API + path, headers={"Authorization": f"Bearer {self.token}"}, **kw
                )
        except httpx.HTTPError as e:
            raise DnsError(f"Cloudflare nicht erreichbar: {e}") from e
        try:
            data = r.json()
        except ValueError as e:
            raise DnsError(f"Cloudflare antwortet {r.status_code}") from e
        if not data.get("success", False):
            errs = "; ".join(
                f"{x.get('message', '')} ({x.get('code', '')})" for x in data.get("errors") or []
            )
            raise DnsError(f"Cloudflare: {errs or r.status_code}")
        return data.get("result")

    def zone_id(self, zone: str) -> str:
        if zone not in self._zones:
            result = self._call("GET", "/zones", params={"name": zone})
            if not result:
                raise DnsError(
                    f"Zone {zone} nicht gefunden – gehört sie zu diesem Cloudflare-Konto und darf "
                    "der Token sie lesen?"
                )
            self._zones[zone] = result[0]["id"]
        return self._zones[zone]

    def records(self, zid: str, name: str) -> list[dict[str, Any]]:
        return (
            self._call("GET", f"/zones/{zid}/dns_records", params={"name": name, "per_page": 100})
            or []
        )

    def create(self, zid: str, rec: Record, comment: str) -> dict[str, Any]:
        return self._call("POST", f"/zones/{zid}/dns_records", json=self._body(rec, comment))

    def update(self, zid: str, rid: str, rec: Record, comment: str) -> dict[str, Any]:
        return self._call("PATCH", f"/zones/{zid}/dns_records/{rid}", json=self._body(rec, comment))

    def delete(self, zid: str, rid: str) -> None:
        self._call("DELETE", f"/zones/{zid}/dns_records/{rid}")

    @staticmethod
    def _body(rec: Record, comment: str) -> dict[str, Any]:
        return {
            "type": rec.type,
            "name": rec.name,
            "content": rec.content,
            "proxied": rec.proxied,
            "ttl": 1,  # automatisch
            "comment": comment,
        }


# ---------- Abgleich ----------


def _same(r: dict[str, Any], rec: Record) -> bool:
    return (
        r.get("type") == rec.type
        and str(r.get("content", "")).lower().rstrip(".") == rec.content
        and bool(r.get("proxied")) == rec.proxied
    )


def sync(cf: Cloudflare, host, zone: dict[str, Any] | None, node_ips: list[str]) -> list[dict]:
    """Einträge des Hosts bei Cloudflare angleichen. Gibt die nun von Tesseract verwalteten
    Einträge zurück (für `host.dns_records`). Wirft DnsError – dann bleibt alles, wie es war,
    soweit nichts geändert wurde."""
    tracked: list[dict[str, Any]] = list(host.dns_records or [])
    want = [] if (host.draft or not host.dns_type) else desired(host, zone, node_ips)
    comment = f"{COMMENT}: {host.domain}"
    kept: list[dict[str, Any]] = []

    # Zone(n) der bisherigen Einträge – bei geänderter Domain evtl. eine andere
    if want:
        zid = cf.zone_id(zone["zone"])
        existing = cf.records(zid, want[0].name)
        mine = {t["id"] for t in tracked}
        free = [r for r in existing if r["id"] not in mine]
        used: set[str] = set()
        for rec in want:
            # 1. eigener Eintrag gleichen Typs → anpassen
            own = next(
                (
                    t
                    for t in tracked
                    if t["type"] == rec.type and t["name"] == rec.name and t["id"] not in used
                ),
                None,
            )
            if own is not None:
                current = next((r for r in existing if r["id"] == own["id"]), None)
                if current is None:  # bei Cloudflare von Hand gelöscht → neu
                    res = cf.create(zid, rec, comment)
                elif _same(current, rec):
                    res = current
                else:
                    res = cf.update(zid, own["id"], rec, comment)
                used.add(own["id"])
                kept.append(_entry(res, zone["zone"], zid))
                continue
            # 2. fremder Eintrag mit genau diesem Wert → übernehmen
            same = next((r for r in free if _same(r, rec)), None)
            if same is not None:
                free.remove(same)
                kept.append(_entry(same, zone["zone"], zid))
                continue
            # 3. Konflikt: CNAME verträgt sich mit nichts, A/AAAA nicht mit CNAME
            clash = [
                r
                for r in free
                if rec.type == "CNAME"
                or r.get("type") == "CNAME"
                or (r.get("type") == rec.type and rec.type in ("A", "AAAA") and len(want) == 1)
            ]
            if clash:
                c = clash[0]
                raise DnsError(
                    f"Bei Cloudflare gibt es schon {c.get('type')} {c.get('name')} → "
                    f"{c.get('content')} (nicht von Tesseract angelegt). Erst dort löschen, "
                    "dann erneut speichern"
                )
            kept.append(_entry(cf.create(zid, rec, comment), zone["zone"], zid))

    # nicht mehr gewünschte eigene Einträge löschen
    keep_ids = {k["id"] for k in kept}
    for t in tracked:
        if t["id"] in keep_ids:
            continue
        try:
            cf.delete(t.get("zone_id") or cf.zone_id(t["zone"]), t["id"])
        except DnsError as e:
            if "not found" not in str(e).lower() and "(81044)" not in str(e):
                raise
    return kept


def _entry(r: dict[str, Any], zone: str, zid: str) -> dict[str, Any]:
    return {
        "id": r["id"],
        "type": r.get("type"),
        "name": str(r.get("name", "")).lower(),
        "content": r.get("content"),
        "proxied": bool(r.get("proxied")),
        "zone": zone,
        "zone_id": zid,
    }


def apply_host(db, host, settings, transport=None) -> dict[str, Any]:
    """Abgleich für einen Host samt Speichern des Ergebnisses. Fehler stehen im Ergebnis, die
    Host-Änderung selbst bleibt gültig."""
    from tesseract.services import cloudflare_token, get_general

    if not host.dns_type and not host.dns_records:
        return {"ok": True, "skipped": True, "error": None, "records": []}
    general = get_general(db)
    zone = zone_for(host.domain, general.get("dns_zones") or [])
    node_ips = list(host.node.public_ips or []) if host.node else []
    try:
        cf = Cloudflare(cloudflare_token(db, settings), transport)
        kept = sync(cf, host, zone, node_ips)
    except DnsError as e:
        host.dns_error = str(e)
        db.commit()
        log.warning("DNS für %s: %s", host.domain, e)
        return {"ok": False, "skipped": False, "error": str(e), "records": host.dns_records or []}
    host.dns_records = kept
    host.dns_error = None
    db.commit()
    return {"ok": True, "skipped": False, "error": None, "records": kept}


def remove_host(db, records: list[dict[str, Any]], settings, transport=None) -> str | None:
    """Beim Löschen eines Hosts: dessen Einträge bei Cloudflare entfernen."""
    from tesseract.services import cloudflare_token

    if not records:
        return None
    try:
        cf = Cloudflare(cloudflare_token(db, settings), transport)
        for t in records:
            try:
                cf.delete(t.get("zone_id") or cf.zone_id(t["zone"]), t["id"])
            except DnsError as e:
                if "(81044)" not in str(e):
                    raise
    except DnsError as e:
        return str(e)
    return None


def check_zone(zone: str, token: str, transport=None) -> str | None:
    """Prüfen, ob der Token die Zone lesen kann. Fehlermeldung oder None."""
    try:
        Cloudflare(token, transport).zone_id(zone)
    except DnsError as e:
        return str(e)
    return None
