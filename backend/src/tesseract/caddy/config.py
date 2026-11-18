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
from dataclasses import dataclass, field
from typing import Any

JSON = dict[str, Any]

FINGERPRINT = "{http.request.tls.client.fingerprint}"


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

    @property
    def needs_client_auth(self) -> bool:
        return self.access == "mtls" or bool(self.paths)

    @property
    def strict(self) -> bool:
        """Ganzer Host geschützt, ohne Zertifikat den Handshake ablehnen."""
        return self.access == "mtls" and not self.paths and self.no_cert_action == "reject"


@dataclass(frozen=True)
class NodeSpec:
    admin_listen: str
    hosts: list[HostSpec] = field(default_factory=list)
    controller_domain: str = ""
    controller_upstream: str = ""
    acme_email: str = ""
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


def host_handlers(host: HostSpec) -> list[JSON]:
    """Die Handler-Kette eines Hosts (ohne Host-Matcher)."""
    routes: list[JSON] = []
    gate = gate_route(host)
    if gate is not None:
        routes.append(gate)
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


def host_route(host: HostSpec) -> JSON:
    return {
        "@id": f"host-{host.id}",
        "match": [{"host": [host.domain]}],
        "handle": host_handlers(host),
        "terminal": True,
    }


def tls_policy(host: HostSpec, ca_der_b64: str) -> JSON:
    client_auth: JSON = {
        "ca": {"provider": "inline", "trusted_ca_certs": [ca_der_b64]},
        "mode": "verify_if_given",
    }
    if host.strict:
        client_auth["mode"] = "require_and_verify"
        if host.allowed:
            client_auth["verifiers"] = [
                {
                    "verifier": "leaf",
                    "leaf_certs_loaders": [
                        {"loader": "pem", "certificates": [pem for _, pem in host.allowed]}
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


def _controller_route(spec: NodeSpec) -> JSON:
    return {
        "@id": "controller",
        "match": [{"host": [spec.controller_domain]}],
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": spec.controller_upstream}],
            }
        ],
        "terminal": True,
    }


def build_config(spec: NodeSpec) -> JSON:
    hosts = sorted(spec.hosts, key=lambda h: h.domain)
    https_routes: list[JSON] = []
    http_routes: list[JSON] = []

    if spec.controller_domain and spec.controller_upstream:
        https_routes.append(_controller_route(spec))
        http_routes.append(_redirect_route(spec.controller_domain))

    for host in hosts:
        https_routes.append(host_route(host))
        # Geschützte Hosts nie unverschlüsselt ausliefern (über HTTP gibt es kein Zertifikat)
        if host.force_https or host.needs_client_auth:
            http_routes.append(_redirect_route(host.domain))
        else:
            route = host_route(host)
            route["@id"] = f"host-{host.id}-http"
            http_routes.append(route)

    https_server: JSON = {
        "listen": [":443"],
        "routes": https_routes,
        "automatic_https": {"disable_redirects": True},
    }
    protected = [h for h in hosts if h.needs_client_auth]
    if protected and spec.client_ca_der_b64:
        https_server["tls_connection_policies"] = [
            *(tls_policy(h, spec.client_ca_der_b64) for h in protected),
            {},  # alle übrigen Hosts: ohne Client-Zertifikat
        ]

    config: JSON = {
        "admin": {"listen": spec.admin_listen},
        "apps": {
            "http": {
                "servers": {
                    "https": https_server,
                    "http": {"listen": [":80"], "routes": http_routes},
                }
            }
        },
    }

    public = [h.domain for h in hosts if is_public_name(h.domain)]
    if spec.controller_domain and is_public_name(spec.controller_domain):
        public.insert(0, spec.controller_domain)
    if spec.acme_email and public:
        config["apps"]["tls"] = {
            "automation": {
                "policies": [
                    {
                        "subjects": public,
                        "issuers": [{"module": "acme", "email": spec.acme_email}],
                    }
                ]
            }
        }
    return config


def config_hash(config: JSON) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
