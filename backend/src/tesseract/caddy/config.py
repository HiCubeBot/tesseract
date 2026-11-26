"""Erzeugt die vollständige Caddy-JSON-Config für einen Node.

Aufbau:
- Server `https` (:443): eine Route pro Host + Controller-Route. Automatische
  HTTP→HTTPS-Umleitung ist aus – das regelt der Server `http` pro Host.
- Server `http` (:80): pro Host Umleitung auf HTTPS oder direkt der Proxy.
  ACME-HTTP-01-Prüfungen beantwortet Caddy auf diesem Port selbst.

mTLS (Phase 2):
- Pro geschütztem Host eine TLS-Verbindungsrichtlinie (per SNI) mit der Geräte-CA.
  "require_and_verify" + Liste erlaubter Zertifikate, wenn der ganze Host geschützt ist
  und ohne Zertifikat abgelehnt werden soll → gesperrte Geräte scheitern im Handshake.
  Sonst "verify_if_given" (Hinweisseite, Zugriff pro Pfad).
- Zusätzlich prüft eine Sperr-Route auf HTTP-Ebene den Fingerabdruck des
  Client-Zertifikats gegen die Freigabeliste – auch pro Pfad.
"""

import copy
import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, field, replace
from typing import Any

JSON = dict[str, Any]

FINGERPRINT = "{http.request.tls.client.fingerprint}"
# Header, mit dem Caddy dem Controller den Fingerabdruck des Client-Zertifikats mitteilt
FINGERPRINT_HEADER = "X-Tesseract-Client-Fingerprint"
# Schnittstelle für Nodes (Agents) – bei TESSERACT_ADMIN_NETWORKS wahlweise ausgenommen
AGENT_PATHS = ("/api/agent/*", "/install/*")
# Statusseite: nur öffentlich, wenn in den Einstellungen eingeschaltet
STATUS_PATHS = ("/status", "/api/status")
# Auf der Controller-Domain immer ohne Admin-Zertifikat erreichbar (Einladung, Agents, Dateien)
# Agents melden sich mit eigenem Node-Zertifikat – das prüft der Controller selbst
CONTROLLER_PUBLIC_PATHS = (
    "/e/*",
    "/api/enroll/*",
    # Gäste verlängern ihr Gerät selbst (Ausweis: das Gerätezertifikat)
    "/v",
    "/api/renew",
    # kurzlebiger Download-Link für eine hinterlegte .p12 (z. B. per QR-Code aufs Handy)
    "/api/dl/*",
    "/api/agent/*",
    "/assets/*",
    "/api/health",
    # öffentliche Statusseite des Uptime-Monitors (nur, wenn eingeschaltet)
    "/status",
    "/api/status",
    "/favicon.ico",
    "/favicon.svg",
    # Prometheus: Schutz (Token, Admin-Zertifikat oder IP-Liste) prüft der Controller
    "/metrics",
    # Installationsskript für Nodes – enthält keine Geheimnisse
    "/install/*",
)


@dataclass(frozen=True)
class AreaSpec:
    """Pfade mit abweichenden Regeln. None = wie beim Host."""

    paths: tuple[str, ...]
    access: str | None = None  # "public" | "mtls"
    # eigene Freigaben (None = die des Hosts)
    allowed: tuple[tuple[str, str], ...] | None = None
    waf_mode: str | None = None
    waf_exclusions: tuple[int, ...] = ()
    authelia: bool | None = None
    ip_mode: str | None = None
    ip_ranges: tuple[str, ...] = ()


@dataclass(frozen=True)
class HostSpec:
    """Alles, was die Config für einen Host braucht (entkoppelt vom DB-Modell)."""

    id: int
    domain: str
    upstream_scheme: str
    upstream_host: str
    upstream_port: int
    upstream_insecure: bool = False
    websockets: bool = True
    force_https: bool = True
    compression: bool = False
    access: str = "public"  # "public" | "mtls"
    no_cert_action: str = "reject"  # "reject" | "hint"
    # bei "public": geschützte Pfade · bei "mtls": öffentliche Pfade
    paths: tuple[str, ...] = ()
    # erlaubte Geräte: (Fingerabdruck SHA-256 hex, Zertifikat als PEM)
    allowed: tuple[tuple[str, str], ...] = ()
    # Fingerabdruck als Header ans Ziel weiterreichen (nur für den Controller)
    pass_fingerprint: bool = False
    # Client-Zertifikat erfragen, auch wenn nichts geschützt ist (Geräteerkennung)
    ask_client_cert: bool = False
    # Coraza WAF: "off" | "detect" | "block"
    waf_mode: str = "off"
    waf_paranoia: int = 1
    waf_exclusions: tuple[int, ...] = ()
    # gezielte Ausnahmen (id, Regel, Ziel, Pfad) – siehe wafrules.py
    waf_exceptions: tuple[tuple[int, int, str, str], ...] = ()
    # Bot-Schutz mit Anubis: an/aus, nur diese Pfade (leer = alle), diese Pfade nie
    bot_protection: bool = False
    bot_paths: tuple[str, ...] = ()
    bot_exempt: tuple[str, ...] = ()
    # IP-Filter: "off" | "block" | "allow", aufgelöste Netze (CIDR)
    ip_mode: str = "off"
    ip_ranges: tuple[str, ...] = ()
    # Login über Authelia (forward_auth); greift nur mit gesetzter Authelia-Adresse
    authelia: bool = False
    # ACME-Prüfung: "http" (HTTP-01) oder "dns" (DNS-01 über Cloudflare)
    tls_challenge: str = "http"
    areas: tuple[AreaSpec, ...] = ()
    # Nur aus internen Netzen – alle anderen: Verbindung ohne Antwort abbrechen
    internal: bool = False
    # Netze, aus denen geschützte Bereiche auch ohne Client-Zertifikat erreichbar sind
    # (Option „aus internen Netzen ohne Zertifikat“)
    cert_free_networks: tuple[str, ...] = ()
    # Eigenes Zertifikat (ID aus custom_certs) statt automatisch
    custom_cert: int | None = None
    # robots.txt direkt von Caddy (leer = Anfrage geht an den Dienst)
    robots: str = ""

    @property
    def needs_client_auth(self) -> bool:
        return (
            self.access == "mtls" or bool(self.paths) or any(a.access == "mtls" for a in self.areas)
        )

    @property
    def all_allowed(self) -> tuple[tuple[str, str], ...]:
        """Alle Geräte, die irgendwo auf diesem Host durchdürfen (für den Handshake)."""
        seen = dict(self.allowed)
        for a in self.areas:
            for fp, pem in a.allowed or ():
                seen.setdefault(fp, pem)
        return tuple(seen.items())

    @property
    def wants_tls_policy(self) -> bool:
        return self.needs_client_auth or self.ask_client_cert or self.custom_cert is not None

    @property
    def strict(self) -> bool:
        """Ganzer Host geschützt, ohne Zertifikat den Handshake ablehnen."""
        return (
            self.access == "mtls"
            and not self.paths
            and self.no_cert_action == "reject"
            and not any(a.access == "public" for a in self.areas)
            # aus internen Netzen ohne Zertifikat → Handshake muss ohne gehen
            and not self.cert_free_networks
        )


@dataclass(frozen=True)
class NodeSpec:
    admin_listen: str
    hosts: list[HostSpec] = field(default_factory=list)
    controller_domain: str = ""
    controller_upstream: str = ""
    # Oberfläche nur mit Admin-Zertifikat (Einladungsseite bleibt öffentlich)
    controller_protected: bool = False
    controller_allowed: tuple[tuple[str, str], ...] = ()
    controller_waf_mode: str = "off"
    # Netze, aus denen die Oberfläche erreichbar ist; leer = alle (TESSERACT_ADMIN_NETWORKS)
    controller_networks: tuple[str, ...] = ()
    # Fingerabdrücke der Geräte von Personen mit Zugriff auf Tesseract (uiaccess.py) – sie
    # kommen auch von außerhalb der controller_networks durch (Anmeldung nur per Zertifikat)
    controller_cert_users: tuple[str, ...] = ()
    # Node-Schnittstelle von controller_networks ausnehmen (TESSERACT_AGENT_API_PUBLIC)
    controller_agents_open: bool = True
    # Öffentliche Statusseite eingeschaltet (Einstellungen › Allgemein)
    controller_status_open: bool = False
    # Vertrauenswürdige Proxys davor (z. B. Cloudflare) – nur dann zählt X-Forwarded-For
    trusted_proxies: tuple[str, ...] = ()
    # Authelia-Instanz, z. B. "http://authelia:9091" oder "https://auth.example.org"
    authelia_url: str = ""
    # Bot-Schutz: Anubis vom Node aus (leer = aus), erwünschte Bots (User-Agent-Teilstrings),
    # interne Netze ohne Prüfung
    anubis_url: str = ""
    bot_allow_agents: tuple[str, ...] = ()
    bot_skip_internal: bool = True
    authelia_headers: tuple[str, ...] = (
        "Remote-User",
        "Remote-Groups",
        "Remote-Email",
        "Remote-Name",
    )
    acme_email: str = ""
    # API-Token für DNS-01 bei Cloudflare (Zone:DNS:Edit)
    cloudflare_token: str = ""
    # Gesperrte IPs/Netze (Auto-Sperre und von Hand) – gelten für alle Hosts
    banned: tuple[str, ...] = ()
    # Interne Netze (LAN, VPN) für Hosts mit „Nur intern“
    internal_networks: tuple[str, ...] = ()
    # Geteilte Wildcard-Zertifikate (per DNS-01), z. B. "*.home.example.org"
    wildcard_certs: tuple[str, ...] = ()
    # Eigene Zertifikate: (ID, Zertifikat-PEM inkl. Kette, Schlüssel-PEM)
    custom_certs: tuple[tuple[int, str, str], ...] = ()
    # Datei, in die Caddy WAF-Treffer schreibt (Pfad im Caddy-Container); leer = aus
    waf_log_file: str = ""
    # Zugriffs-Log (Phase 5): Pfad im Caddy-Container, leer = keins
    access_log_file: str = ""
    # Geräte-Zwischenzertifikat (DER, Base64) – Vertrauensanker für Client-Zertifikate
    # Zwischenzertifikat(e) für Client-Zertifikate, Base64-DER. Nach einem CA-Wechsel stehen
    # hier das neue und das alte, bis die alten Geräte verlängert sind.
    client_ca_der_b64: str | tuple[str, ...] = ""


# Hinweisseite für Anfragen ohne freigegebenes Gerätezertifikat. Caddy setzt die Platzhalter
# beim Ausliefern ein (Dienst, echte Client-IP, Zeit, Verarbeitungszeit, Anfrage-ID).
HINT_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Kein Zugang</title>
<style>
:root{--bg:#f4f5f8;--card:#fff;--line:#e4e6ec;--fg:#14161b;--muted:#5b6170;--key:#5b6170;
--accent:#7c6cf0;--accent-bg:#f1effe}
@media (prefers-color-scheme:dark){:root{--bg:#0e1014;--card:#161920;--line:#262b36;--fg:#eceef3;
--muted:#a0a7b4;--key:#8a91a0;--accent:#a99cff;--accent-bg:#221f3a}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:var(--bg);color:var(--fg);font:16px/1.6 Inter,system-ui,-apple-system,sans-serif;
padding:24px}
main{width:100%;max-width:500px;padding:28px 32px;border:1px solid var(--line);border-radius:16px;
background:var(--card)}
.badge{display:inline-block;padding:2px 12px;border:1px solid var(--accent);border-radius:999px;
background:var(--accent-bg);color:var(--accent);font:12px/1.7 ui-monospace,SFMono-Regular,Menlo,
Consolas,monospace}
h1{margin:16px 0 8px;font-size:24px;line-height:1.25}
p{margin:0 0 12px;color:var(--muted)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 24px;margin:20px 0 0;
padding-top:18px;border-top:1px solid var(--line);font-size:13px}
dt{color:var(--key)}
dd{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;word-break:break-all}
</style></head>
<body><main>
<span class="badge">403 · Gerätezertifikat</span>
<h1>Kein Zugang</h1>
<p>Dieser Dienst ist nur mit einem freigegebenen Gerätezertifikat erreichbar.</p>
<p>Hast du eine Einladung bekommen? Installiere das Zertifikat über den Link und öffne die Seite
danach neu. Fragt der Browser nach einem Zertifikat, wähle das Zertifikat deines Geräts.</p>
<dl>
<dt>Dienst</dt><dd>{http.request.host}</dd>
<dt>Deine IP</dt><dd>{http.vars.client_ip}</dd>
<dt>Zeit</dt><dd>{time.now.http}</dd>
<dt>Verarbeitung</dt><dd id="ms">{http.request.duration_ms} ms</dd>
<dt>Anfrage-ID</dt><dd>{http.request.uuid}</dd>
</dl>
<script>
// Verarbeitungszeit lesbar runden (Caddy liefert alle Nachkommastellen)
var e = document.getElementById("ms"), n = parseFloat(e.textContent);
if (!isNaN(n)) e.textContent = n.toFixed(1).replace(".", ",") + " ms";
</script>
</main></body></html>
"""

# Englische Fassung – für Browser, die nicht Deutsch bevorzugen (Accept-Language)
HINT_PAGE_EN = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>No access</title>
<style>
:root{--bg:#f4f5f8;--card:#fff;--line:#e4e6ec;--fg:#14161b;--muted:#5b6170;--key:#5b6170;
--accent:#7c6cf0;--accent-bg:#f1effe}
@media (prefers-color-scheme:dark){:root{--bg:#0e1014;--card:#161920;--line:#262b36;--fg:#eceef3;
--muted:#a0a7b4;--key:#8a91a0;--accent:#a99cff;--accent-bg:#221f3a}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:var(--bg);color:var(--fg);font:16px/1.6 Inter,system-ui,-apple-system,sans-serif;
padding:24px}
main{width:100%;max-width:500px;padding:28px 32px;border:1px solid var(--line);border-radius:16px;
background:var(--card)}
.badge{display:inline-block;padding:2px 12px;border:1px solid var(--accent);border-radius:999px;
background:var(--accent-bg);color:var(--accent);font:12px/1.7 ui-monospace,SFMono-Regular,Menlo,
Consolas,monospace}
h1{margin:16px 0 8px;font-size:24px;line-height:1.25}
p{margin:0 0 12px;color:var(--muted)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 24px;margin:20px 0 0;
padding-top:18px;border-top:1px solid var(--line);font-size:13px}
dt{color:var(--key)}
dd{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;word-break:break-all}
</style></head>
<body><main>
<span class="badge">403 · device certificate</span>
<h1>No access</h1>
<p>This service is only reachable with an approved device certificate.</p>
<p>Did you get an invitation? Install the certificate via the link and then reload this page.
If the browser asks for a certificate, choose your device's certificate.</p>
<dl>
<dt>Service</dt><dd>{http.request.host}</dd>
<dt>Your IP</dt><dd>{http.vars.client_ip}</dd>
<dt>Time</dt><dd>{time.now.http}</dd>
<dt>Processing</dt><dd id="ms">{http.request.duration_ms} ms</dd>
<dt>Request ID</dt><dd>{http.request.uuid}</dd>
</dl>
<script>
// round processing time
var e = document.getElementById("ms"), n = parseFloat(e.textContent);
if (!isNaN(n)) e.textContent = n.toFixed(1) + " ms";
</script>
</main></body></html>
"""


# Endungen, für die es kein öffentliches Zertifikat gibt (RFC 6762/8375 und übliche Heimnetze)
LOCAL_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".home.arpa",
    ".intern",
    ".corp",
    ".test",
)


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def is_public_name(domain: str) -> bool:
    """Bekommt die Domain ein öffentliches Zertifikat? (nicht localhost, keine IP)"""
    if domain == "localhost" or domain.endswith(LOCAL_SUFFIXES):
        return False
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        return True
    return False


def upstream_dial(host: str, port: int) -> str:
    if ":" in host:  # IPv6
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def _proxy(host: HostSpec) -> JSON:
    handler: JSON = {
        "handler": "reverse_proxy",
        "upstreams": [{"dial": upstream_dial(host.upstream_host, host.upstream_port)}],
    }
    if host.upstream_scheme == "https":
        tls: JSON = {"insecure_skip_verify": True} if host.upstream_insecure else {}
        handler["transport"] = {"protocol": "http", "tls": tls}
    if host.pass_fingerprint:
        # "set" überschreibt einen vom Client mitgeschickten Header
        handler["headers"] = {"request": {"set": {FINGERPRINT_HEADER: [FINGERPRINT]}}}
    return handler


def path_patterns(paths: tuple[str, ...] | list[str]) -> list[str]:
    """`/admin` deckt auch `/admin/…` ab; Muster mit `*` bleiben, wie sie sind."""
    out: list[str] = []
    for p in paths:
        p = "/" + p.strip().lstrip("/")
        if "*" in p:
            out.append(p)
            continue
        base = p.rstrip("/") or "/"
        out.append(base)
        out.append("/*" if base == "/" else base + "/*")
    return list(dict.fromkeys(out))


# Grund einer Ablehnung fürs Zugriffs-Log (Phase 5). Der Marker wird in build_config entweder
# durch einen `log_append`-Handler ersetzt (Feld `tesseract_reason`) oder entfernt.
REASON_KEY = "_tesseract_reason"
ACCESS_LOGGER = "tesseract_access"


def _tagged(handler: JSON, reason: str) -> JSON:
    return {**handler, REASON_KEY: reason}


def _apply_reasons(node: Any, enabled: bool) -> None:
    """Marker auflösen: vor jeden markierten Handler ein log_append setzen (oder nur löschen)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "handle" and isinstance(value, list):
                out = []
                for h in value:
                    reason = h.pop(REASON_KEY, None) if isinstance(h, dict) else None
                    if reason and enabled:
                        out.append(
                            {"handler": "log_append", "key": "tesseract_reason", "value": reason}
                        )
                    out.append(h)
                    _apply_reasons(h, enabled)
                node[key] = out
            else:
                _apply_reasons(value, enabled)
    elif isinstance(node, list):
        for item in node:
            _apply_reasons(item, enabled)


def _hint(body: str) -> JSON:
    return {
        "handler": "static_response",
        "status_code": 403,
        # Verbindung danach schließen: die nächste Anfrage baut eine neue auf und kann dann
        # ein (inzwischen installiertes) Zertifikat mitschicken
        "close": True,
        "headers": {
            "Content-Type": ["text/html; charset=utf-8"],
            "Cache-Control": ["no-store"],
            "Vary": ["Accept-Language"],
        },
        "body": body,
    }


# Deutsch, wenn der Browser Deutsch zuerst nennt oder keine Sprache schickt – sonst Englisch
GERMAN_FIRST: list[JSON] = [
    {"header_regexp": {"Accept-Language": {"pattern": r"(?i)^\s*de\b"}}},
    {"header": {"Accept-Language": None}},
]


def _deny(host: HostSpec) -> JSON:
    if host.no_cert_action == "hint":
        return {
            "handler": "subroute",
            "routes": [
                {"match": GERMAN_FIRST, "handle": [_hint(HINT_PAGE)], "terminal": True},
                {"handle": [_hint(HINT_PAGE_EN)]},
            ],
        }
    return {"handler": "static_response", "status_code": 403, "body": "Kein Zugang", "close": True}


def gate_route(host: HostSpec) -> JSON | None:
    """Sperrt geschützte Anfragen ohne freigegebenes Client-Zertifikat."""
    if not host.needs_client_auth:
        return None
    fingerprints = [fp for fp, _ in host.allowed] or ["-"]
    negations: list[JSON] = [{"vars": {FINGERPRINT: fingerprints}}]
    if host.cert_free_networks:
        # aus den internen Netzen auch ohne Zertifikat (echte Verbindungs-IP, nicht XFF)
        negations.append({"remote_ip": {"ranges": list(host.cert_free_networks)}})
    patterns = path_patterns(host.paths)
    matcher: JSON
    if host.access == "mtls":
        # alles geschützt außer den öffentlichen Pfaden
        if patterns:
            negations.append({"path": patterns})
        matcher = {"not": negations}
    else:
        # nur die gelisteten Pfade geschützt
        matcher = {"not": negations, "path": patterns}
    return {"match": [matcher], "handle": [_tagged(_deny(host), "mtls")], "terminal": True}


def waf_directives(
    mode: str,
    paranoia: int,
    exclusions: tuple[int, ...] | list[int],
    exceptions: tuple[tuple[int, int, str, str], ...] | list = (),
) -> str:
    """Coraza-Konfiguration: empfohlene Basis + OWASP CRS, Paranoia-Level, Ausnahmen.
    Gezielte Ausnahmen (Feld/Pfad) stehen als ctl-Regeln vor dem CRS, ganze danach."""
    from tesseract.wafrules import exception_directives

    level = min(max(int(paranoia), 1), 4)
    lines = [
        "Include @coraza.conf-recommended",
        # Antworten nicht puffern/prüfen – spart Speicher, stört kein Streaming
        "SecResponseBodyAccess Off",
        "Include @crs-setup.conf.example",
        'SecAction "id:900000,phase:1,pass,t:none,nolog,'
        f'setvar:tx.blocking_paranoia_level={level}"',
        *exception_directives(list(exceptions)),
        "Include @owasp_crs/*.conf",
        f"SecRuleEngine {'On' if mode == 'block' else 'DetectionOnly'}",
    ]
    lines += [f"SecRuleRemoveById {rule_id}" for rule_id in sorted(set(exclusions))]
    return "\n".join(lines)


def waf_handler(host: HostSpec) -> JSON:
    return {
        "handler": "waf",
        "load_owasp_crs": True,
        "directives": waf_directives(
            host.waf_mode, host.waf_paranoia, host.waf_exclusions, host.waf_exceptions
        ),
    }


def ip_route(host: HostSpec) -> JSON | None:
    """IP-Filter – als Erstes, er ist am billigsten."""
    if host.ip_mode == "off":
        return None
    if host.ip_mode == "allow" and not host.ip_ranges:
        matcher: JSON = {}  # leere Erlaubt-Liste → niemand
    elif host.ip_mode == "allow":
        matcher = {"not": [{"client_ip": {"ranges": list(host.ip_ranges)}}]}
    elif host.ip_ranges:
        matcher = {"client_ip": {"ranges": list(host.ip_ranges)}}
    else:
        return None
    route: JSON = {
        "handle": [
            _tagged(
                {"handler": "static_response", "status_code": 403, "body": "Zugriff gesperrt"},
                "ip",
            )
        ],
        "terminal": True,
    }
    if matcher:
        route["match"] = [matcher]
    return route


AUTHELIA_ENDPOINT = "/api/authz/forward-auth"


def _upstream_from_url(url: str) -> tuple[str, bool]:
    """'https://auth.example.org' → ('auth.example.org:443', True)."""
    from urllib.parse import urlsplit

    parts = urlsplit(url if "://" in url else f"http://{url}")
    tls = parts.scheme == "https"
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = parts.port or (443 if tls else 80)
    return f"{host}:{port}", tls


def authelia_handler(url: str, headers: tuple[str, ...] | list[str]) -> JSON:
    """Entspricht Caddys `forward_auth`: Anfrage an Authelia, bei 2xx Header übernehmen,
    sonst Authelias Antwort (Weiterleitung zum Login) an den Browser."""
    dial, tls = _upstream_from_url(url)
    copy_routes: list[JSON] = [{"handle": [{"handler": "vars"}]}]
    for name in headers:
        placeholder = "{http.reverse_proxy.header." + name + "}"
        # Erst löschen – ein vom Client mitgeschickter Header darf nie durchkommen
        copy_routes.append({"handle": [{"handler": "headers", "request": {"delete": [name]}}]})
        copy_routes.append(
            {
                "match": [{"not": [{"vars": {placeholder: [""]}}]}],
                "handle": [{"handler": "headers", "request": {"set": {name: [placeholder]}}}],
            }
        )
    handler: JSON = {
        "handler": "reverse_proxy",
        "upstreams": [{"dial": dial}],
        "rewrite": {"method": "GET", "uri": AUTHELIA_ENDPOINT},
        "headers": {
            "request": {
                "set": {
                    "X-Forwarded-Method": ["{http.request.method}"],
                    "X-Forwarded-Uri": ["{http.request.uri}"],
                }
            }
        },
        "handle_response": [{"match": {"status_code": [2]}, "routes": copy_routes}],
    }
    if tls:
        handler["transport"] = {"protocol": "http", "tls": {}}
    return handler


# ---------- Bot-Schutz (Anubis) ----------

ANUBIS_PREFIX = "/.within.website/"
ANUBIS_CHECK = "/.within.website/x/cmd/anubis/api/check"
ANUBIS_PASS = "/.within.website/x/cmd/anubis/api/pass-challenge"


@dataclass(frozen=True)
class BotContext:
    """Was alle Hosts eines Nodes für den Bot-Schutz brauchen."""

    url: str = ""
    allow_agents: tuple[str, ...] = ()
    skip_networks: tuple[str, ...] = ()


def bot_context(spec: "NodeSpec") -> BotContext:
    return BotContext(
        url=spec.anubis_url,
        allow_agents=spec.bot_allow_agents,
        skip_networks=spec.internal_networks if spec.bot_skip_internal else (),
    )


def anubis_routes(host: HostSpec, ctx: BotContext | None) -> list[JSON]:
    """Bot-Schutz vor dem Dienst – wie Caddys `forward_auth` mit Anubis im Subrequest-Modus.

    1. `/.within.website/*` (Prüfseite, Skripte, Bestätigung) geht direkt an Anubis.
    2. Alle anderen Anfragen fragt Caddy bei Anubis an (`…/api/check`):
       2xx → weiter zum Dienst · 401 → Weiterleitung zur Prüfseite · sonst (z. B. 403 für
       bekannte schlechte Bots) Anubis' Antwort an den Client. Beides im Log als Grund „bot“.
    Ohne Prüfung: Ausnahme-Pfade, Geräte mit freigegebenem Zertifikat, interne Netze (wenn
    eingeschaltet) und erwünschte Bots per User-Agent."""
    if not host.bot_protection:
        return []
    if ctx is None or not ctx.url:
        # gewünscht, aber nicht eingerichtet → lieber zu als offen (wie bei Authelia)
        return [
            {
                "handle": [
                    _tagged(
                        {
                            "handler": "static_response",
                            "status_code": 503,
                            "body": "Bot-Schutz (Anubis) ist nicht eingerichtet",
                        },
                        "bot",
                    )
                ],
                "terminal": True,
            }
        ]
    dial, tls = _upstream_from_url(ctx.url)
    real_ip = {"X-Real-Ip": ["{http.vars.client_ip}"]}

    def proxy(extra: JSON | None = None) -> JSON:
        h: JSON = {
            "handler": "reverse_proxy",
            "upstreams": [{"dial": dial}],
            "headers": {"request": {"set": dict(real_ip)}},
        }
        if tls:
            h["transport"] = {"protocol": "http", "tls": {}}
        if extra:
            h.update(extra)
        return h

    assets = {
        "match": [{"path": [ANUBIS_PREFIX + "*"]}],
        "handle": [proxy()],
        "terminal": True,
    }
    check = proxy(
        {
            "rewrite": {"method": "GET", "uri": ANUBIS_CHECK},
            "handle_response": [
                # bestanden: nichts tun – die Kette läuft weiter zum Dienst
                {"match": {"status_code": [2]}, "routes": [{"handle": [{"handler": "vars"}]}]},
                {
                    "match": {"status_code": [401]},
                    "routes": [
                        {
                            "handle": [
                                _tagged(
                                    {
                                        "handler": "static_response",
                                        "status_code": 307,
                                        "headers": {
                                            "Location": [
                                                ANUBIS_PREFIX + "?redir={http.request.uri}"
                                            ],
                                            "Cache-Control": ["no-store"],
                                        },
                                    },
                                    "bot",
                                )
                            ]
                        }
                    ],
                },
                {
                    "match": {"status_code": [4, 5]},
                    "routes": [{"handle": [_tagged({"handler": "copy_response"}, "bot")]}],
                },
            ],
        }
    )
    check["headers"]["request"]["set"].update(
        {
            "X-Forwarded-Method": ["{http.request.method}"],
            "X-Forwarded-Uri": ["{http.request.uri}"],
        }
    )
    skip: list[JSON] = []
    if host.bot_exempt:
        skip.append({"path": path_patterns(host.bot_exempt)})
    fps = [fp for fp, _ in host.all_allowed]
    if fps:
        skip.append({"vars": {FINGERPRINT: fps}})
    if ctx.skip_networks:
        skip.append({"remote_ip": {"ranges": list(ctx.skip_networks)}})
    if ctx.allow_agents:
        pattern = "(?i)(" + "|".join(re.escape(a) for a in ctx.allow_agents) + ")"
        skip.append({"header_regexp": {"User-Agent": {"pattern": pattern}}})
    matcher: JSON = {}
    if skip:
        matcher["not"] = skip
    if host.bot_paths:
        matcher["path"] = path_patterns(host.bot_paths)
    guarded: JSON = {"handle": [check]}
    if matcher:
        guarded["match"] = [matcher]
    return [assets, guarded]


def area_spec(host: HostSpec, area: AreaSpec) -> HostSpec:
    """Host-Einstellungen mit den Abweichungen des Bereichs."""
    changes: dict = {"areas": ()}
    if area.access is not None:
        changes["access"] = area.access
        changes["paths"] = ()
        if area.allowed is not None:
            changes["allowed"] = area.allowed
    if area.waf_mode is not None:
        changes["waf_mode"] = area.waf_mode
    if area.waf_exclusions:
        changes["waf_exclusions"] = tuple(sorted({*host.waf_exclusions, *area.waf_exclusions}))
    if area.authelia is not None:
        changes["authelia"] = area.authelia
    if area.ip_mode is not None:
        changes["ip_mode"] = area.ip_mode
        changes["ip_ranges"] = area.ip_ranges
    return replace(host, **changes)


def host_handlers(
    host: HostSpec, authelia: JSON | None = None, bot: BotContext | None = None
) -> list[JSON]:
    """Die Handler-Kette eines Hosts (ohne Host-Matcher):
    IP-Filter → Zertifikat → WAF → Bot-Schutz → Authelia → Dienst."""
    routes: list[JSON] = []
    # Bereiche zuerst: eigene, vollständige Kette für ihre Pfade
    for area in host.areas:
        if not area.paths:
            continue
        routes.append(
            {
                "match": [{"path": path_patterns(area.paths)}],
                "handle": host_handlers(area_spec(host, area), authelia, bot),
                "terminal": True,
            }
        )
    ip = ip_route(host)
    if ip is not None:
        routes.append(ip)
    gate = gate_route(host)
    if gate is not None:
        routes.append(gate)
    if host.waf_mode in ("detect", "block"):
        routes.append({"handle": [waf_handler(host)]})
    routes += anubis_routes(host, bot)
    if host.authelia and authelia is not None:
        routes.append({"handle": [authelia]})
    elif host.authelia:
        # Authelia gewünscht, aber nicht eingerichtet → lieber zu als offen
        routes.append(
            {
                "handle": [
                    _tagged(
                        {
                            "handler": "static_response",
                            "status_code": 503,
                            "body": "Anmeldung (Authelia) ist nicht eingerichtet",
                        },
                        "authelia",
                    )
                ],
                "terminal": True,
            }
        )
    if not host.websockets:
        routes.append(
            {
                "match": [{"header": {"Upgrade": ["websocket"]}}],
                "handle": [
                    _tagged({"handler": "static_response", "status_code": 403}, "websocket")
                ],
                "terminal": True,
            }
        )
    if host.compression:
        routes.append(
            {
                "handle": [
                    {
                        "handler": "encode",
                        "encodings": {"zstd": {}, "gzip": {}},
                        "prefer": ["zstd", "gzip"],
                    }
                ]
            }
        )
    routes.append({"handle": [_proxy(host)]})
    return [{"handler": "subroute", "routes": routes}]


def internal_route(networks: tuple[str, ...]) -> JSON:
    """Für alle außerhalb der internen Netze: Verbindung abbrechen, keine Antwort.
    Geprüft wird die echte Verbindungs-IP (remote_ip), nicht X-Forwarded-For."""
    abort: JSON = {
        "handle": [_tagged({"handler": "static_response", "abort": True}, "internal")],
        "terminal": True,
    }
    if networks:
        abort["match"] = [{"not": [{"remote_ip": {"ranges": list(networks)}}]}]
    return abort


def robots_route(body: str) -> JSON:
    """/robots.txt direkt beantworten – vor Zertifikat, WAF und Bereichen."""
    return {
        "match": [{"path": ["/robots.txt"], "method": ["GET", "HEAD"]}],
        "handle": [
            {
                "handler": "static_response",
                "status_code": 200,
                "headers": {
                    "Content-Type": ["text/plain; charset=utf-8"],
                    "Cache-Control": ["public, max-age=3600"],
                },
                "body": body,
            }
        ],
        "terminal": True,
    }


def host_route(
    host: HostSpec,
    authelia: JSON | None = None,
    internal: tuple[str, ...] = (),
    bot: BotContext | None = None,
) -> JSON:
    handle = host_handlers(host, authelia, bot)
    if host.robots:
        handle[0]["routes"].insert(0, robots_route(host.robots))
    if host.internal:
        # vor allem anderen – noch vor IP-Filter, Zertifikat und WAF
        handle[0]["routes"].insert(0, internal_route(internal))
    return {
        "@id": f"host-{host.id}",
        "match": [{"host": [host.domain]}],
        "handle": handle,
        "terminal": True,
    }


def custom_tag(cert_id: int) -> str:
    return f"tesseract-custom-{cert_id}"


def tls_policy(host: HostSpec, ca_der_b64: str | tuple[str, ...]) -> JSON:
    policy: JSON = {"match": {"sni": [host.domain]}}
    if host.custom_cert is not None:
        # genau dieses hochgeladene Zertifikat ausliefern
        policy["certificate_selection"] = {"any_tag": [custom_tag(host.custom_cert)]}
    if not (host.needs_client_auth or host.ask_client_cert) or not ca_der_b64:
        return policy
    client_auth: JSON = {
        "ca": {
            "provider": "inline",
            "trusted_ca_certs": [ca_der_b64] if isinstance(ca_der_b64, str) else list(ca_der_b64),
        },
        "mode": "verify_if_given",
    }
    if host.strict:
        client_auth["mode"] = "require_and_verify"
        allowed = host.all_allowed
        if allowed:
            client_auth["verifiers"] = [
                {
                    "verifier": "leaf",
                    "leaf_certs_loaders": [
                        {"loader": "pem", "certificates": [pem for _, pem in allowed]}
                    ],
                }
            ]
    policy["client_authentication"] = client_auth
    return policy


def _redirect_route(domain: str) -> JSON:
    return {
        "match": [{"host": [domain]}],
        "handle": [
            {
                "handler": "static_response",
                "status_code": 308,
                "headers": {"Location": ["https://{http.request.host}{http.request.uri}"]},
            }
        ],
        "terminal": True,
    }


def controller_spec(spec: NodeSpec) -> HostSpec:
    host, _, port = spec.controller_upstream.rpartition(":")
    protected = spec.controller_protected
    return HostSpec(
        id=0,
        domain=spec.controller_domain,
        upstream_scheme="http",
        upstream_host=host.strip("[]") or spec.controller_upstream,
        upstream_port=int(port) if port.isdigit() else 80,
        access="mtls" if protected else "public",
        no_cert_action="hint",
        paths=public_paths(spec) if protected else (),
        allowed=spec.controller_allowed,
        pass_fingerprint=True,
        ask_client_cert=True,
        waf_mode=spec.controller_waf_mode,
    )


def public_paths(spec: "NodeSpec", agents_open: bool = True) -> tuple[str, ...]:
    """Öffentliche Pfade der Controller-Domain – ohne Statusseite, solange sie aus ist."""
    return tuple(
        p
        for p in CONTROLLER_PUBLIC_PATHS
        if (agents_open or p not in AGENT_PATHS)
        and (spec.controller_status_open or p not in STATUS_PATHS)
    )


def _admin_networks_route(spec: "NodeSpec") -> JSON:
    """Oberfläche nur aus diesen Netzen: sonst Verbindung abbrechen, keine Antwort. Die
    öffentlichen Pfade (Einladung, Verlängern, Agents …) bleiben überall erreichbar.
    Geprüft wird die echte Verbindungs-IP (remote_ip), nicht X-Forwarded-For.
    Personen mit Zugriff per Gerätezertifikat kommen von überall durch – erkannt am
    Fingerabdruck, den Caddy nach Prüfung gegen die eigene CA setzt."""
    exceptions: list[JSON] = [
        {"remote_ip": {"ranges": list(spec.controller_networks)}},
        {"path": list(public_paths(spec, spec.controller_agents_open))},
    ]
    if spec.controller_cert_users:
        exceptions.append({"vars": {FINGERPRINT: list(spec.controller_cert_users)}})
    return {
        "match": [{"not": exceptions}],
        # im Log wie „nur intern“ (gleiche Wirkung: von außen keine Antwort)
        "handle": [_tagged({"handler": "static_response", "abort": True}, "internal")],
        "terminal": True,
    }


def _controller_route(spec: NodeSpec) -> JSON:
    route = host_route(controller_spec(spec))
    route["@id"] = "controller"
    if spec.controller_networks:
        # vor allem anderen – noch vor Zertifikat und WAF
        gate = _admin_networks_route(spec)
        route["handle"][0]["routes"].insert(0, gate)
    return route


def covering_wildcard(domain: str, wildcards: tuple[str, ...] | list[str]) -> str | None:
    """Welches Wildcard-Zertifikat deckt den Namen ab? (genau eine Ebene darunter)"""
    if domain.startswith("*."):
        return domain if domain in wildcards else None
    first, _, rest = domain.partition(".")
    if not first or not rest:
        return None
    candidate = f"*.{rest}"
    return candidate if candidate in wildcards else None


def _route_order(h: HostSpec) -> tuple[int, str]:
    # Wildcards nach den konkreten Namen, sonst fängt *.example.org alles ab
    return (1 if h.domain.startswith("*.") else 0, h.domain)


def tls_automation(spec: NodeSpec, hosts: list[HostSpec]) -> JSON | None:
    """ACME-Richtlinien: HTTP-01 (Standard) und DNS-01 über Cloudflare."""
    wild = spec.wildcard_certs if spec.cloudflare_token else ()
    # Hosts unter einem geteilten Wildcard-Zertifikat brauchen kein eigenes
    public = [
        h for h in hosts if is_public_name(h.domain) and not covering_wildcard(h.domain, wild)
    ]
    http_subjects = [h.domain for h in public if h.tls_challenge != "dns"]
    dns_subjects = [*wild, *(h.domain for h in public if h.tls_challenge == "dns")]
    dns_subjects = list(dict.fromkeys(dns_subjects))
    cd = spec.controller_domain
    if cd and is_public_name(cd) and not covering_wildcard(cd, wild):
        # Mit Cloudflare-Token per DNS-01 – klappt auch, wenn der Name nur im Heimnetz
        # existiert (kein öffentlicher A-Eintrag, kein offener Port 80)
        if spec.cloudflare_token:
            dns_subjects.insert(0, cd)
        else:
            http_subjects.insert(0, cd)

    def issuer(dns: bool) -> JSON:
        acme: JSON = {"module": "acme"}
        if spec.acme_email:
            acme["email"] = spec.acme_email
        if dns:
            acme["challenges"] = {
                "dns": {"provider": {"name": "cloudflare", "api_token": spec.cloudflare_token}}
            }
        return acme

    policies: list[JSON] = []
    # Interne Namen (.lan, .home.arpa …): Zertifikat aus Caddys eigener CA
    local = [
        h.domain
        for h in hosts
        if not is_public_name(h.domain) and not _is_ip(h.domain) and h.domain != "localhost"
    ]
    # auch die Oberfläche selbst, wenn sie unter einem internen Namen läuft
    if cd and not is_public_name(cd) and not _is_ip(cd) and cd != "localhost":
        local.insert(0, cd)
    if local:
        policies.append({"subjects": local, "issuers": [{"module": "internal"}]})
    if dns_subjects and spec.cloudflare_token:
        policies.append({"subjects": dns_subjects, "issuers": [issuer(True)]})
    if http_subjects and spec.acme_email:
        policies.append({"subjects": http_subjects, "issuers": [issuer(False)]})
    if not policies:
        return None
    tls: JSON = {"automation": {"policies": policies}}
    if wild:
        # Wildcard-Zertifikate auch ohne eigenen Host holen und erneuern
        tls["certificates"] = {"automate": list(wild)}
    return tls


def build_config(spec: NodeSpec) -> JSON:
    hosts = sorted(spec.hosts, key=_route_order)
    https_routes: list[JSON] = []
    http_routes: list[JSON] = []
    policy_hosts: list[HostSpec] = []

    if spec.controller_domain and spec.controller_upstream:
        https_routes.append(_controller_route(spec))
        redirect = _redirect_route(spec.controller_domain)
        # Gibt es Personen mit Zugriff per Gerätezertifikat, muss Port 80 immer auf HTTPS
        # umleiten: Über HTTP gibt es kein Zertifikat, ein Abbruch hier ließe sie von unterwegs
        # nie bis zur Zertifikatsabfrage kommen. Ohne Zertifikat bricht HTTPS danach ab.
        if spec.controller_networks and not spec.controller_cert_users:
            # sonst verrät auch die Umleitung von außen nichts
            redirect["handle"] = [
                {
                    "handler": "subroute",
                    "routes": [
                        _admin_networks_route(spec),
                        {"handle": redirect["handle"]},
                    ],
                }
            ]
        http_routes.append(redirect)
        policy_hosts.append(controller_spec(spec))

    # Gesperrte IPs: nach der Controller-Route (die Oberfläche bleibt erreichbar), vor allen Hosts
    if spec.banned:
        ban: JSON = {
            "@id": "banned",
            "match": [{"client_ip": {"ranges": list(spec.banned)}}],
            "handle": [
                _tagged(
                    {"handler": "static_response", "status_code": 403, "body": "Gesperrt"}, "ban"
                )
            ],
            "terminal": True,
        }
        https_routes.append(ban)
        http_routes.append({**copy.deepcopy(ban), "@id": "banned-http"})

    authelia = (
        authelia_handler(spec.authelia_url, spec.authelia_headers) if spec.authelia_url else None
    )
    nets = spec.internal_networks
    bot = bot_context(spec)
    for host in hosts:
        https_routes.append(host_route(host, authelia, nets, bot))
        # Geschützte Hosts nie unverschlüsselt ausliefern (über HTTP gibt es kein Zertifikat)
        if host.force_https or host.needs_client_auth or host.internal:
            redirect = _redirect_route(host.domain)
            if host.internal:
                # auch die Umleitung verrät von außen nichts
                redirect["handle"] = [
                    {
                        "handler": "subroute",
                        "routes": [internal_route(nets), {"handle": redirect["handle"]}],
                    }
                ]
            http_routes.append(redirect)
        else:
            route = host_route(host, authelia, nets, bot)
            route["@id"] = f"host-{host.id}-http"
            http_routes.append(route)

    https_server: JSON = {
        "listen": [":443"],
        "routes": https_routes,
        "automatic_https": {"disable_redirects": True},
    }
    wild = spec.wildcard_certs if spec.cloudflare_token else ()
    own = [h.domain for h in hosts if h.custom_cert is not None]
    covered = own + [
        h.domain for h in hosts if is_public_name(h.domain) and covering_wildcard(h.domain, wild)
    ]
    cd = spec.controller_domain
    if cd and is_public_name(cd) and covering_wildcard(cd, wild):
        covered.append(cd)
    if covered:
        # kein Einzelzertifikat – Caddy liefert das passende Wildcard-Zertifikat aus
        https_server["automatic_https"]["skip_certificates"] = covered
    http_server: JSON = {"listen": [":80"], "routes": http_routes}
    if spec.trusted_proxies:
        proxies = {"source": "static", "ranges": list(spec.trusted_proxies)}
        for server in (https_server, http_server):
            server["trusted_proxies"] = proxies
            server["client_ip_headers"] = ["X-Forwarded-For"]
    policy_hosts += [h for h in hosts if h.wants_tls_policy]
    # Client-Zertifikate gehen nur mit CA; eigene Zertifikate auch ohne
    if not spec.client_ca_der_b64:
        policy_hosts = [h for h in policy_hosts if h.custom_cert is not None]
    if policy_hosts:
        https_server["tls_connection_policies"] = [
            *(tls_policy(h, spec.client_ca_der_b64) for h in policy_hosts),
            {},  # alle übrigen Hosts: ohne Client-Zertifikat
        ]

    config: JSON = {
        "admin": {"listen": spec.admin_listen},
        "apps": {
            "http": {
                "servers": {
                    "https": https_server,
                    "http": http_server,
                }
            }
        },
    }

    tls = tls_automation(spec, [h for h in hosts if h.custom_cert is None])
    if spec.custom_certs:
        tls = tls or {}
        tls["certificates"] = {
            **tls.get("certificates", {}),
            "load_pem": [
                {"certificate": cert, "key": key, "tags": [custom_tag(cid)]}
                for cid, cert, key in spec.custom_certs
            ],
        }
    if any("client_authentication" in p for p in https_server.get("tls_connection_policies", [])):
        # Keine TLS-Sitzungswiederaufnahme: Eine ohne Zertifikat begonnene Sitzung (z. B. die
        # Hinweisseite) würde sonst bei jeder neuen Verbindung ohne Zertifikat fortgesetzt –
        # ein frisch installiertes Gerätezertifikat käme nie an, bis Caddy neu lädt.
        tls = tls or {}
        tls["session_tickets"] = {"disabled": True}
        # Kein HTTP/3: Browser schicken über QUIC keine Client-Zertifikate (und fragen auch
        # nicht danach). Wo das Zertifikat nur optional ist (Oberfläche, Hinweisseite),
        # käme die Anfrage dann still ohne Zertifikat an.
        https_server["protocols"] = ["h1", "h2"]
    if tls:
        config["apps"]["tls"] = tls
    logs: JSON = {}
    if spec.access_log_file:
        # Zugriffs-Log aller Hosts (Phase 5) – ohne die Oberfläche selbst (Polling, Agents)
        server_logs: JSON = {"default_logger_name": ACCESS_LOGGER}
        if spec.controller_domain:
            server_logs["skip_hosts"] = [spec.controller_domain]
        https_server["logs"] = server_logs
        http_server["logs"] = dict(server_logs)
        logs[ACCESS_LOGGER] = {
            "writer": {
                "output": "file",
                "filename": spec.access_log_file,
                "roll_size_mb": 50,
                "roll_keep": 3,
                "mode": "0644",
            },
            "encoder": {"format": "json"},
            "include": [f"http.log.access.{ACCESS_LOGGER}"],
        }
    _apply_reasons(config, bool(spec.access_log_file))
    if spec.waf_log_file:
        # Eigene Logdatei nur für WAF-Treffer – liest der Controller für die Auto-Sperre
        logs.update(
            {
                "tesseract_waf": {
                    "writer": {
                        "output": "file",
                        "filename": spec.waf_log_file,
                        "roll_size_mb": 10,
                        "roll_keep": 3,
                        # der Controller läuft als anderer Nutzer und muss mitlesen
                        "mode": "0644",
                    },
                    "encoder": {"format": "json"},
                    "level": "ERROR",
                    "include": ["http.handlers.waf"],
                }
            }
        )
    if logs:
        config["logging"] = {"logs": logs}
    return config


def redact(config: JSON) -> JSON:
    """Kopie ohne Geheimnisse – für die Anzeige im UI."""
    raw = json.dumps(config)
    data = json.loads(raw)
    for loaded in data.get("apps", {}).get("tls", {}).get("certificates", {}).get("load_pem", []):
        loaded["key"] = "***"
    for policy in data.get("apps", {}).get("tls", {}).get("automation", {}).get("policies", []):
        for issuer in policy.get("issuers", []):
            provider = issuer.get("challenges", {}).get("dns", {}).get("provider")
            if provider and "api_token" in provider:
                provider["api_token"] = "***"
    return data


def config_hash(config: JSON) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
