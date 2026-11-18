"""Grafana-Dashboard (JSON-Modell) für die Prometheus-Metriken von Tesseract."""

from typing import Any


def _panel(
    pid: int,
    title: str,
    expr: str,
    x: int,
    y: int,
    w: int = 12,
    kind: str = "timeseries",
    unit: str = "short",
    legend: str = "{{host}}",
) -> dict[str, Any]:
    return {
        "id": pid,
        "type": kind,
        "title": title,
        "datasource": {"type": "prometheus", "uid": "${datasource}"},
        "gridPos": {"x": x, "y": y, "w": w, "h": 8},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "targets": [{"refId": "A", "expr": expr, "legendFormat": legend}],
    }


def dashboard() -> dict[str, Any]:
    sel = 'node=~"$node"'
    panels = [
        _panel(
            1,
            "Nodes erreichbar",
            f"sum(tesseract_node_up{{{sel}}})",
            0,
            0,
            6,
            "stat",
            legend="erreichbar",
        ),
        _panel(
            2,
            "Lokal geändert (Abweichung)",
            f"sum(tesseract_node_drift{{{sel}}})",
            6,
            0,
            6,
            "stat",
            legend="Nodes",
        ),
        _panel(3, "Gesperrte IPs", "tesseract_bans_active", 12, 0, 6, "stat", legend="IPs"),
        _panel(4, "Hosts", f"sum(tesseract_hosts{{{sel}}})", 18, 0, 6, "stat", legend="Hosts"),
        _panel(
            5,
            "Anfragen pro Sekunde nach Host",
            f"sum by (host) (rate(tesseract_requests_total{{{sel}}}[5m]))",
            0,
            8,
            12,
            unit="reqps",
        ),
        _panel(
            6,
            "Abgelehnt nach Grund",
            f'sum by (reason) (rate(tesseract_requests_total{{{sel},reason!="ok"}}[5m]))',
            12,
            8,
            12,
            unit="reqps",
            legend="{{reason}}",
        ),
        _panel(
            7,
            "Antwortzeit p95",
            "histogram_quantile(0.95, sum by (le, host) "
            f"(rate(tesseract_request_duration_seconds_bucket{{{sel}}}[5m])))",
            0,
            16,
            12,
            unit="s",
        ),
        _panel(
            8,
            "Server-Fehler (5xx)",
            f'sum by (host) (rate(tesseract_requests_total{{{sel},status="5xx"}}[5m]))',
            12,
            16,
            12,
            unit="reqps",
        ),
        _panel(
            9,
            "WAF-Blockaden",
            f"sum by (host) (increase(tesseract_waf_blocked_total{{{sel}}}[1h]))",
            0,
            24,
            12,
            unit="short",
        ),
        _panel(
            10,
            "Daten an Clients",
            f"sum by (host) (rate(tesseract_response_bytes_total{{{sel}}}[5m]))",
            12,
            24,
            12,
            unit="Bps",
        ),
    ]
    return {
        "title": "Tesseract",
        "uid": "tesseract",
        "schemaVersion": 39,
        "time": {"from": "now-24h", "to": "now"},
        "refresh": "1m",
        "tags": ["tesseract", "caddy"],
        "templating": {
            "list": [
                {
                    "name": "datasource",
                    "type": "datasource",
                    "query": "prometheus",
                    "label": "Datenquelle",
                },
                {
                    "name": "node",
                    "type": "query",
                    "label": "Node",
                    "datasource": {"type": "prometheus", "uid": "${datasource}"},
                    "query": "label_values(tesseract_node_up, node)",
                    "includeAll": True,
                    "multi": True,
                    "current": {"text": "All", "value": "$__all"},
                },
            ]
        },
        "panels": panels,
    }
