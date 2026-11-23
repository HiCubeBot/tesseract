"""User-Agent → Art (Browser, App/API, Bot) und Name für die Statistik.

Bewusst einfach: wenige bekannte Namen, alles andere landet in „Sonstige …“.
"""

import re

from tesseract.sqlstore import BOT_RE

# Reihenfolge zählt: spezifische Namen vor allgemeinen
_BOTS = [
    ("Googlebot", r"googlebot"),
    ("Bingbot", r"bingbot"),
    ("Applebot", r"applebot"),
    ("GPTBot", r"gptbot|chatgpt"),
    ("ClaudeBot", r"claudebot|anthropic"),
    ("Ahrefs", r"ahrefs"),
    ("Semrush", r"semrush"),
    ("Censys", r"censys"),
    ("Shodan", r"shodan"),
    ("zgrab", r"zgrab"),
    ("libwww-perl", r"libwww-perl"),
    ("Facebook", r"facebookexternalhit|meta-externalagent"),
]
_APPS = [
    ("Prometheus", r"prometheus"),
    ("Uptime Kuma", r"uptime-?kuma"),
    ("Grafana", r"grafana"),
    ("Home Assistant", r"home ?assistant|hass"),
    ("Jellyfin", r"jellyfin"),
    ("Nextcloud", r"nextcloud|mirall"),
    ("Bitwarden", r"bitwarden"),
    ("Immich", r"immich"),
    ("Docker", r"docker/|containerd"),
    ("Git", r"^git/|git-lfs"),
    ("curl", r"^curl/"),
    ("Wget", r"^wget/"),
    ("Python", r"python|aiohttp|httpx"),
    ("Go", r"go-http-client"),
    ("okhttp", r"okhttp"),
    ("Java", r"java/|apache-httpclient"),
    ("Node.js", r"node-fetch|axios|undici"),
    ("Dart", r"^dart/"),
]
_BROWSERS = [
    ("Edge", r"edg/|edge/"),
    ("Opera", r"opr/|opera"),
    ("Samsung Internet", r"samsungbrowser"),
    ("Firefox", r"firefox/|fxios"),
    ("Chrome", r"chrome/|crios"),
    ("Safari", r"safari/|applewebkit"),
]
_C = [
    (kind, name, re.compile(rx, re.I))
    for kind, table in (("bot", _BOTS), ("app", _APPS), ("browser", _BROWSERS))
    for name, rx in table
]


def classify(ua: str | None) -> tuple[str, str]:
    """→ (Art, Name). Art: browser | app | bot."""
    ua = (ua or "").strip()
    if not ua or ua == "-":
        return "bot", "ohne Kennung"
    for kind, name, rx in _C:
        if kind == "bot" and rx.search(ua):
            return "bot", name
    for kind, name, rx in _C:
        if kind == "app" and rx.search(ua):
            # Werkzeuge wie curl zählen als App/API, nicht als Bot
            return "app", name
    if BOT_RE.search(ua):
        return "bot", "Sonstige Bots"
    if ua.startswith("Mozilla/"):
        for kind, name, rx in _C:
            if kind == "browser" and rx.search(ua):
                return "browser", name
        return "browser", "Sonstige Browser"
    return "app", "Sonstige"
