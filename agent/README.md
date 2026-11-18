# Tesseract-Agent

Läuft neben Caddy auf jedem weiteren Node, verbindet sich **ausgehend per mTLS** mit dem
Controller (funktioniert hinter NAT, kein offener Admin-Port) und spielt die Config über die
lokale Caddy-Admin-API ein.

Anleitung, Einstellungen und Protokoll: [docs/agent.md](../docs/agent.md).

```bash
uv sync
uv run tesseract-agent --help
uv run pytest
```
