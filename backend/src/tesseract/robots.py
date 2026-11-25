"""robots.txt pro Host – direkt von Caddy ausgeliefert, der Dienst dahinter merkt nichts davon.

Modi:
- `off`      Anfragen auf /robots.txt gehen wie bisher an den Dienst
- `allow`    alles erlauben
- `deny`     alles verbieten (`Disallow: /`)
- `deny_ai`  KI-Crawler verbieten, Suchmaschinen erlauben (Liste unter Einstellungen pflegbar)
- `paths`    nur bestimmte Pfade sperren
- `custom`   eigener Text

Dazu optional eine `Sitemap:`-Zeile. Mit „Hosts nur mit Zertifikat: alles verbieten“ in den
Einstellungen bekommen geschützte Hosts im Modus `off` automatisch `Disallow: /`.
"""

import re
from dataclasses import dataclass, field
from typing import Any

MODES = ("off", "allow", "deny", "deny_ai", "paths", "custom")

# Bekannte KI-Crawler (Training und KI-Suche). Suchmaschinen wie Googlebot und Bingbot fehlen
# bewusst – sie bleiben erlaubt. Google-Extended und Applebot-Extended sind keine eigenen
# Crawler, sondern Schalter für die KI-Nutzung der Inhalte.
DEFAULT_AI_BOTS: tuple[str, ...] = (
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-User",
    "Claude-SearchBot",
    "anthropic-ai",
    "CCBot",
    "Google-Extended",
    "Applebot-Extended",
    "Bytespider",
    "PerplexityBot",
    "Perplexity-User",
    "Meta-ExternalAgent",
    "FacebookBot",
    "Amazonbot",
    "cohere-ai",
    "Diffbot",
    "YouBot",
    "MistralAI-User",
    "DuckAssistBot",
    "Timpibot",
    "ImagesiftBot",
    "omgili",
)

# Felder, die gängige Crawler verstehen (RFC 9309 plus verbreitete Erweiterungen)
KNOWN_FIELDS = {
    "user-agent",
    "allow",
    "disallow",
    "sitemap",
    "crawl-delay",
    "host",
    "clean-param",
    "content-signal",
}
MAX_LENGTH = 16_000
_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z-]*)\s*:\s*(.*?)\s*$")


@dataclass
class Check:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _paths_block(paths: list[str]) -> list[str]:
    return [f"Disallow: {'/' + p.strip().lstrip('/')}" for p in paths if p.strip()]


def render(
    mode: str,
    paths: list[str] | None = None,
    sitemap: str = "",
    text: str = "",
    ai_bots: list[str] | tuple[str, ...] = DEFAULT_AI_BOTS,
) -> str:
    """Inhalt der robots.txt für einen Modus. Leer = aus."""
    if mode == "off" or mode not in MODES:
        return ""
    if mode == "custom":
        body = text.replace("\r\n", "\n").strip()
        return body + "\n" if body else ""
    lines: list[str] = []
    if mode == "allow":
        lines = ["User-agent: *", "Allow: /"]
    elif mode == "deny":
        lines = ["User-agent: *", "Disallow: /"]
    elif mode == "deny_ai":
        bots = [b.strip() for b in ai_bots if b.strip()]
        for bot in bots:
            lines.append(f"User-agent: {bot}")
        if bots:
            lines += ["Disallow: /", ""]
        lines += ["User-agent: *", "Allow: /"]
    elif mode == "paths":
        block = _paths_block(paths or [])
        lines = ["User-agent: *", *(block or ["Allow: /"])]
    if sitemap.strip():
        lines += ["", f"Sitemap: {sitemap.strip()}"]
    return "\n".join(lines) + "\n"


def check(text: str) -> Check:
    """Syntax prüfen: Fehler (ungültige Zeilen) und Hinweise (unbekannte Felder, Reihenfolge)."""
    out = Check()
    if len(text) > MAX_LENGTH:
        out.errors.append(f"Zu lang (höchstens {MAX_LENGTH} Zeichen)")
        return out
    seen_agent = False
    for no, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _LINE.match(line)
        if not m:
            out.errors.append(f"Zeile {no}: „Feld: Wert“ erwartet")
            continue
        name, value = m.group(1).lower(), m.group(2)
        if name not in KNOWN_FIELDS:
            out.warnings.append(f"Zeile {no}: unbekanntes Feld „{m.group(1)}“")
            continue
        if name == "user-agent":
            seen_agent = True
            if not value:
                out.errors.append(f"Zeile {no}: User-agent ohne Wert")
        elif name in ("allow", "disallow"):
            if not seen_agent:
                out.errors.append(f"Zeile {no}: {m.group(1)} vor dem ersten User-agent")
            elif value and not (value.startswith("/") or value.startswith("*")):
                out.warnings.append(f"Zeile {no}: Pfad sollte mit / beginnen")
        elif name == "sitemap" and not re.match(r"^https?://", value, re.I):
            out.errors.append(f"Zeile {no}: Sitemap braucht eine vollständige Adresse (https://…)")
        elif name == "crawl-delay" and not re.match(r"^\d+(\.\d+)?$", value):
            out.errors.append(f"Zeile {no}: Crawl-delay erwartet Sekunden")
    if not seen_agent and text.strip():
        out.warnings.append("Kein User-agent – Crawler ignorieren die Regeln")
    return out


def host_body(host: Any, general: dict[str, Any]) -> str:
    """robots.txt eines Hosts mit den Einstellungen (KI-Liste, Standard für mTLS-Hosts)."""
    mode = getattr(host, "robots", "off") or "off"
    if mode == "off":
        if general.get("robots_mtls_deny") and getattr(host, "access", "public") == "mtls":
            return render("deny")
        return ""
    return render(
        mode,
        paths=list(getattr(host, "robots_paths", None) or []),
        sitemap=getattr(host, "robots_sitemap", "") or "",
        text=getattr(host, "robots_text", "") or "",
        ai_bots=general.get("robots_ai_bots") or DEFAULT_AI_BOTS,
    )
