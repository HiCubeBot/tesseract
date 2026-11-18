# Tesseract

Caddy-Verwaltung (NPM-Alternative) mit mTLS statt VPN und Coraza WAF. Sprache in Code-Kommentaren, UI und Doku: Deutsch.

## Struktur
- `frontend/` Svelte 5 + Vite (TypeScript) · `backend/` Python 3.13, FastAPI, uv · `docs/` **alle** Dokumentation
- Phasen und Features: `docs/roadmap.md`, `docs/features.md` – bei neuen Features aktualisieren

## Git
- Nie direkt auf `main` arbeiten. Pro Feature ein Branch (`feature/…`, `fix/…`, `docs/…`), fertig → PR gegen `main` → mergen.
- Commits nur mit `git@criehe.de` (lokal gesetzt, vor dem Commit prüfen).

## Vor jedem PR
- `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`
- `cd frontend && npm run check && npm run build`
