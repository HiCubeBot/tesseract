"""Erzeugt die vollständige Caddy-JSON-Config für einen Node.

Aufbau:
- Server `https` (:443): eine Route pro Host + Controller-Route. Automatische
  HTTP→HTTPS-Umleitung ist aus – das regelt der Server `http` pro Host.
- Server `http` (:80): pro Host Umleitung auf HTTPS oder direkt der Proxy.
  ACME-HTTP-01-Prüfungen beantwortet Caddy auf diesem Port selbst.
"""

import hashlib
import ipaddress
import json
from dataclasses import dataclass, field
from typing import Any

JSON = dict[str, Any]


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


@dataclass(frozen=True)
class NodeSpec:
    admin_listen: str
    hosts: list[HostSpec] = field(default_factory=list)
    controller_domain: str = ""
    controller_upstream: str = ""
    acme_email: str = ""


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


def host_handlers(host: HostSpec) -> list[JSON]:
    """Die Handler-Kette eines Hosts (ohne Host-Matcher)."""
    routes: list[JSON] = []
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
        if host.force_https:
            http_routes.append(_redirect_route(host.domain))
        else:
            route = host_route(host)
            route["@id"] = f"host-{host.id}-http"
            http_routes.append(route)

    config: JSON = {
        "admin": {"listen": spec.admin_listen},
        "apps": {
            "http": {
                "servers": {
                    "https": {
                        "listen": [":443"],
                        "routes": https_routes,
                        "automatic_https": {"disable_redirects": True},
                    },
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
