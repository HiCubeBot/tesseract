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

import hashlib
import ipaddress
import json
from dataclasses import dataclass, field, replace
from typing import Any

JSON = dict[str, Any]

FINGERPRINT = "{http.request.tls.client.fingerprint}"
# Header, mit dem Caddy dem Controller den Fingerabdruck des Client-Zertifikats mitteilt
FINGERPRINT_HEADER = "X-Tesseract-Client-Fingerprint"
# Auf der Controller-Domain immer ohne Zertifikat erreichbar (Einladungsseite + Dateien)
CONTROLLER_PUBLIC_PATHS = ("/e/*", "/api/enroll/*", "/assets/*", "/api/health", "/favicon.ico")


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
    # IP-Filter: "off" | "block" | "allow", aufgelöste Netze (CIDR)
    ip_mode: str = "off"
    ip_ranges: tuple[str, ...] = ()
    # Login über Authelia (forward_auth); greift nur mit gesetzter Authelia-Adresse
    authelia: bool = False
    # ACME-Prüfung: "http" (HTTP-01) oder "dns" (DNS-01 über Cloudflare)
    tls_challenge: str = "http"
    areas: tuple[AreaSpec, ...] = ()

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
        return self.needs_client_auth or self.ask_client_cert

    @property
    def strict(self) -> bool:
        """Ganzer Host geschützt, ohne Zertifikat den Handshake ablehnen."""
        return (
            self.access == "mtls"
            and not self.paths
            and self.no_cert_action == "reject"
            and not any(a.access == "public" for a in self.areas)
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
    # Vertrauenswürdige Proxys davor (z. B. Cloudflare) – nur dann zählt X-Forwarded-For
    trusted_proxies: tuple[str, ...] = ()
    # Authelia-Instanz, z. B. "http://authelia:9091" oder "https://auth.example.org"
    authelia_url: str = ""
    authelia_headers: tuple[str, ...] = (
        "Remote-User",
        "Remote-Groups",
        "Remote-Email",
        "Remote-Name",
    )
    acme_email: str = ""
    # API-Token für DNS-01 bei Cloudflare (Zone:DNS:Edit)
    cloudflare_token: str = ""
    # Geräte-Zwischenzertifikat (DER, Base64) – Vertrauensanker für Client-Zertifikate
    client_ca_der_b64: str = ""


HINT_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kein Zugang</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0e1014;color:#e7e9ee;font:15px/1.6 Inter,system-ui,sans-serif;padding:24px}
main{max-width:440px;padding:28px;border:1px solid #232833;border-radius:12px;background:#161920}
h1{margin:0 0 8px;font-size:22px}p{margin:0 0 10px;color:#a0a7b4}code{color:#c9ced8}
</style></head>
<body><main><h1>Kein Zugang</h1>
<p>Dieser Dienst ist nur von freigegebenen Geräten aus erreichbar.</p>
<p>Dein Gerät hat kein passendes Zertifikat. Wende dich an die Person,
die dich eingeladen hat.</p>
<p><code>{http.request.host}</code></p>
</main></body></html>
"""


def is_public_name(domain: str) -> bool:
    """Bekommt die Domain ein öffentliches Zertifikat? (nicht localhost, keine IP)"""
    if domain == "localhost" or domain.endswith((".localhost", ".local", ".internal")):
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
        handler["transport"] = {"protocol": "http", "tls": {}}
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


def _deny(host: HostSpec) -> JSON:
    if host.no_cert_action == "hint":
        return {
            "handler": "static_response",
            "status_code": 403,
            "headers": {
                "Content-Type": ["text/html; charset=utf-8"],
                "Cache-Control": ["no-store"],
            },
            "body": HINT_PAGE,
        }
    return {"handler": "static_response", "status_code": 403, "body": "Kein Zugang"}


def gate_route(host: HostSpec) -> JSON | None:
    """Sperrt geschützte Anfragen ohne freigegebenes Client-Zertifikat."""
    if not host.needs_client_auth:
        return None
    fingerprints = [fp for fp, _ in host.allowed] or ["-"]
    negations: list[JSON] = [{"vars": {FINGERPRINT: fingerprints}}]
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
    return {"match": [matcher], "handle": [_deny(host)], "terminal": True}


def waf_directives(mode: str, paranoia: int, exclusions: tuple[int, ...] | list[int]) -> str:
    """Coraza-Konfiguration: empfohlene Basis + OWASP CRS, Paranoia-Level, Ausnahmen."""
    level = min(max(int(paranoia), 1), 4)
    lines = [
        "Include @coraza.conf-recommended",
        # Antworten nicht puffern/prüfen – spart Speicher, stört kein Streaming
        "SecResponseBodyAccess Off",
        "Include @crs-setup.conf.example",
        'SecAction "id:900000,phase:1,pass,t:none,nolog,'
        f'setvar:tx.blocking_paranoia_level={level}"',
        "Include @owasp_crs/*.conf",
        f"SecRuleEngine {'On' if mode == 'block' else 'DetectionOnly'}",
    ]
    lines += [f"SecRuleRemoveById {rule_id}" for rule_id in sorted(set(exclusions))]
    return "\n".join(lines)


def waf_handler(host: HostSpec) -> JSON:
    return {
        "handler": "waf",
        "load_owasp_crs": True,
        "directives": waf_directives(host.waf_mode, host.waf_paranoia, host.waf_exclusions),
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
        "handle": [{"handler": "static_response", "status_code": 403, "body": "Zugriff gesperrt"}],
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


def host_handlers(host: HostSpec, authelia: JSON | None = None) -> list[JSON]:
    """Die Handler-Kette eines Hosts (ohne Host-Matcher)."""
    routes: list[JSON] = []
    # Bereiche zuerst: eigene, vollständige Kette für ihre Pfade
    for area in host.areas:
        if not area.paths:
            continue
        routes.append(
            {
                "match": [{"path": path_patterns(area.paths)}],
                "handle": host_handlers(area_spec(host, area), authelia),
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
    if host.authelia and authelia is not None:
        routes.append({"handle": [authelia]})
    elif host.authelia:
        # Authelia gewünscht, aber nicht eingerichtet → lieber zu als offen
        routes.append(
            {
                "handle": [
                    {
                        "handler": "static_response",
                        "status_code": 503,
                        "body": "Anmeldung (Authelia) ist nicht eingerichtet",
                    }
                ],
                "terminal": True,
            }
        )
    if not host.websockets:
        routes.append(
            {
                "match": [{"header": {"Upgrade": ["websocket"]}}],
                "handle": [{"handler": "static_response", "status_code": 403}],
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


def host_route(host: HostSpec, authelia: JSON | None = None) -> JSON:
    return {
        "@id": f"host-{host.id}",
        "match": [{"host": [host.domain]}],
        "handle": host_handlers(host, authelia),
        "terminal": True,
    }


def tls_policy(host: HostSpec, ca_der_b64: str) -> JSON:
    client_auth: JSON = {
        "ca": {"provider": "inline", "trusted_ca_certs": [ca_der_b64]},
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
    return {"match": {"sni": [host.domain]}, "client_authentication": client_auth}


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
        paths=CONTROLLER_PUBLIC_PATHS if protected else (),
        allowed=spec.controller_allowed,
        pass_fingerprint=True,
        ask_client_cert=True,
        waf_mode=spec.controller_waf_mode,
    )


def _controller_route(spec: NodeSpec) -> JSON:
    route = host_route(controller_spec(spec))
    route["@id"] = "controller"
    return route


def _route_order(h: HostSpec) -> tuple[int, str]:
    # Wildcards nach den konkreten Namen, sonst fängt *.example.org alles ab
    return (1 if h.domain.startswith("*.") else 0, h.domain)


def tls_automation(spec: NodeSpec, hosts: list[HostSpec]) -> JSON | None:
    """ACME-Richtlinien: HTTP-01 (Standard) und DNS-01 über Cloudflare."""
    http_subjects = [
        h.domain for h in hosts if is_public_name(h.domain) and h.tls_challenge != "dns"
    ]
    dns_subjects = [
        h.domain for h in hosts if is_public_name(h.domain) and h.tls_challenge == "dns"
    ]
    if spec.controller_domain and is_public_name(spec.controller_domain):
        http_subjects.insert(0, spec.controller_domain)

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
    if dns_subjects and spec.cloudflare_token:
        policies.append({"subjects": dns_subjects, "issuers": [issuer(True)]})
    if http_subjects and spec.acme_email:
        policies.append({"subjects": http_subjects, "issuers": [issuer(False)]})
    return {"automation": {"policies": policies}} if policies else None


def build_config(spec: NodeSpec) -> JSON:
    hosts = sorted(spec.hosts, key=_route_order)
    https_routes: list[JSON] = []
    http_routes: list[JSON] = []
    policy_hosts: list[HostSpec] = []

    if spec.controller_domain and spec.controller_upstream:
        https_routes.append(_controller_route(spec))
        http_routes.append(_redirect_route(spec.controller_domain))
        policy_hosts.append(controller_spec(spec))

    authelia = (
        authelia_handler(spec.authelia_url, spec.authelia_headers) if spec.authelia_url else None
    )
    for host in hosts:
        https_routes.append(host_route(host, authelia))
        # Geschützte Hosts nie unverschlüsselt ausliefern (über HTTP gibt es kein Zertifikat)
        if host.force_https or host.needs_client_auth:
            http_routes.append(_redirect_route(host.domain))
        else:
            route = host_route(host, authelia)
            route["@id"] = f"host-{host.id}-http"
            http_routes.append(route)

    https_server: JSON = {
        "listen": [":443"],
        "routes": https_routes,
        "automatic_https": {"disable_redirects": True},
    }
    http_server: JSON = {"listen": [":80"], "routes": http_routes}
    if spec.trusted_proxies:
        proxies = {"source": "static", "ranges": list(spec.trusted_proxies)}
        for server in (https_server, http_server):
            server["trusted_proxies"] = proxies
            server["client_ip_headers"] = ["X-Forwarded-For"]
    policy_hosts += [h for h in hosts if h.wants_tls_policy]
    if policy_hosts and spec.client_ca_der_b64:
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

    tls = tls_automation(spec, hosts)
    if tls is not None:
        config["apps"]["tls"] = tls
    return config


def redact(config: JSON) -> JSON:
    """Kopie ohne Geheimnisse – für die Anzeige im UI."""
    raw = json.dumps(config)
    data = json.loads(raw)
    for policy in data.get("apps", {}).get("tls", {}).get("automation", {}).get("policies", []):
        for issuer in policy.get("issuers", []):
            provider = issuer.get("challenges", {}).get("dns", {}).get("provider")
            if provider and "api_token" in provider:
                provider["api_token"] = "***"
    return data


def config_hash(config: JSON) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
