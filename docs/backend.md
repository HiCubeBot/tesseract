# Backend (Controller)

Python 3.13 · FastAPI · Pydantic Settings · verwaltet mit [uv](https://docs.astral.sh/uv/).

## Starten

```bash
cd backend
uv sync                                   # .venv anlegen, Abhängigkeiten installieren
uv run fastapi dev src/tesseract/app.py   # Dev-Server mit Reload auf :8000
uv run tesseract                          # wie im Container (uvicorn, Einstellungen aus Env)
```

API-Doku (Swagger): <http://127.0.0.1:8000/api/docs>

## Aufbau

```
backend/
  pyproject.toml          Abhängigkeiten, Ruff- und pytest-Konfiguration
  uv.lock                 gelockte Versionen (einchecken!)
  src/tesseract/
    __init__.py           Version, Einstiegspunkt `tesseract`
    cli.py                startet uvicorn
    config.py             Einstellungen (Env-Präfix TESSERACT_)
    app.py                create_app(): API unter /api, optional Frontend unter /
    api/
      __init__.py         sammelt alle Router
      health.py           GET /api/health
  tests/                  pytest
```

Geplante Module (siehe [Roadmap](roadmap.md)): `db/` (Modelle, Migrationen), `caddy/`
(Config-Erzeugung, Admin-API-Client), `pki/` (CA, Zertifikate), `api/hosts.py`,
`api/users.py`, `api/devices.py`, `api/nodes.py`, `api/invites.py`, `audit/`.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen oder einer `.env` im Arbeitsverzeichnis.

| Variable | Standard | Bedeutung |
|---|---|---|
| `TESSERACT_HOST` | `127.0.0.1` | Bind-Adresse |
| `TESSERACT_PORT` | `8000` | Port |
| `TESSERACT_RELOAD` | `false` | Auto-Reload (nur Entwicklung) |
| `TESSERACT_DATA_DIR` | `data` | Persistente Daten (DB, CA, Backups) |
| `TESSERACT_STATIC_DIR` | – | Gebautes Frontend; leer = nur API |
| `TESSERACT_CADDY_ADMIN_URL` | `http://caddy:2019` | Caddy-Admin-API (Phase 1) |
| `TESSERACT_LOG_LEVEL` | `info` | Log-Level |

## Qualität

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

Abhängigkeiten hinzufügen: `uv add <paket>` bzw. `uv add --dev <paket>`.
