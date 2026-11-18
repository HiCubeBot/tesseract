# Backend (Controller)

Python 3.13 · FastAPI · SQLAlchemy 2 + Alembic (SQLite) · argon2 · verwaltet mit [uv](https://docs.astral.sh/uv/).

## Starten

```bash
cd backend
cp .env.example .env      # Reload an, Cookie ohne HTTPS, Daten in backend/data
uv sync
uv run tesseract          # Controller auf :8000
```

Beim **ersten Start** legt der Controller den Admin `admin` mit einem Zufallspasswort an und
schreibt es **einmalig ins Log**. Passwort vergessen? Nur lokal auf dem Controller:

```bash
uv run tesseract admin reset                               # Entwicklung
docker compose exec tesseract tesseract admin reset        # Container
```

Das setzt ein neues Zufallspasswort und beendet alle Sessions.

API-Doku (Swagger): <http://127.0.0.1:8000/api/docs>

## Aufbau

```
backend/
  pyproject.toml          Abhängigkeiten, Ruff- und pytest-Konfiguration
  uv.lock                 gelockte Versionen (einchecken!)
  src/tesseract/
    __init__.py           Version, Einstiegspunkt `tesseract`
    cli.py                serve · admin reset · db upgrade
    config.py             Einstellungen (Env-Präfix TESSERACT_)
    app.py                create_app(): API unter /api, optional Frontend unter /
    bootstrap.py          Start: Migrationen, erster Admin, lokaler Node
    auth.py               Passwörter, Sessions, Login-Bremse
    audit.py              Audit-Einträge schreiben
    deps.py               FastAPI-Abhängigkeiten (DB-Session, angemeldeter Admin)
    db/
      models.py           Datenmodell
      migrations/         Alembic (Migrationen laufen beim Start automatisch)
    api/                  Router: health, auth, audit …
  tests/                  pytest (eigene SQLite-DB pro Test)
```

## Anmeldung & Sessions

- `POST /api/auth/login` → Session-Cookie `tesseract_session` (HttpOnly, SameSite=Strict,
  Secure außer bei `TESSERACT_COOKIE_SECURE=false`). In der DB steht nur der SHA-256 des Tokens.
- Ohne „angemeldet bleiben“ gilt die Session 12 h als Browser-Cookie, mit 30 Tage.
- Nach 5 Fehlversuchen in 5 Minuten wird die IP für den Rest des Fensters gebremst (`429`).
- Passwortwechsel (`POST /api/auth/password`) beendet alle Sessions.
- Anmeldungen, Fehlversuche und Passwortwechsel landen im Audit-Log.

## Datenbank & Migrationen

Schema ändern:

1. Modelle in `db/models.py` anpassen.
2. Neue Migration erzeugen (Alembic-Autogenerate gegen eine leere DB) und unter
   `db/migrations/versions/` mit fortlaufender Nummer ablegen; generierte Typen
   `tesseract.db.models.UTCDateTime()` durch `sa.DateTime()` ersetzen.
3. `uv run pytest` – die Tests laufen gegen das migrierte Schema.

Zeitstempel werden als UTC gespeichert und immer zeitzonenbewusst zurückgegeben.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen oder einer `.env` im Arbeitsverzeichnis.

| Variable | Standard | Bedeutung |
|---|---|---|
| `TESSERACT_HOST` | `127.0.0.1` | Bind-Adresse |
| `TESSERACT_PORT` | `8000` | Port |
| `TESSERACT_RELOAD` | `false` | Auto-Reload (nur Entwicklung) |
| `TESSERACT_DATA_DIR` | `data` | Persistente Daten (DB, CA, Backups) |
| `TESSERACT_DATABASE_URL` | SQLite in `DATA_DIR` | Andere Datenbank-URL |
| `TESSERACT_STATIC_DIR` | – | Gebautes Frontend; leer = nur API |
| `TESSERACT_CADDY_ADMIN_URL` | `http://caddy:2019` | Caddy-Admin-API des lokalen Nodes |
| `TESSERACT_CADDY_ADMIN_LISTEN` | `0.0.0.0:2019` | Admin-Adresse, die in die erzeugte Caddy-Config geschrieben wird |
| `TESSERACT_CONTROLLER_UPSTREAM` | `tesseract:8000` | Wie Caddy den Controller erreicht |
| `TESSERACT_COOKIE_SECURE` | `true` | Session-Cookie nur über HTTPS |
| `TESSERACT_SESSION_HOURS` | `12` | Session-Dauer ohne „angemeldet bleiben“ |
| `TESSERACT_SESSION_REMEMBER_DAYS` | `30` | Session-Dauer mit „angemeldet bleiben“ |
| `TESSERACT_LOG_LEVEL` | `info` | Log-Level |

## Qualität

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

Abhängigkeiten hinzufügen: `uv add <paket>` bzw. `uv add --dev <paket>`.
