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
    services.py           Hosts, Versionen, Einstellungen, Übertragen an Nodes
    pki.py                Root, Zwischenzertifikat, Client-Zertifikate, PKCS#12
    identity.py           CA einrichten, Geräte ausstellen und sperren
    secretbox.py          Verschlüsselung von Geheimnissen (AES-GCM) mit dem Hauptschlüssel
    checks.py             Vorab-Prüfungen (Domain frei, DNS, Ziel erreichbar)
    caddy/
      config.py           erzeugt die komplette Caddy-JSON-Config eines Nodes
      client.py           POST /load an die Caddy-Admin-API
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

## API (Phase 1)

Alle Endpunkte außer `/api/health` und `/api/auth/login` brauchen eine Session.

| Methode & Pfad | Zweck |
|---|---|
| `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` | Anmeldung |
| `POST /api/auth/password` | Passwort ändern (beendet alle Sessions) |
| `GET /api/hosts` · `POST /api/hosts` | Hosts auflisten / anlegen (`draft: true` = nur speichern) |
| `GET/PUT/DELETE /api/hosts/{id}` | Host lesen / ändern / löschen – jede Änderung wird übertragen |
| `POST /api/hosts/check` | Vorab-Prüfungen für Domain und Ziel |
| `POST /api/hosts/preview` | Caddy-Route, die für einen Host erzeugt würde |
| `GET /api/hosts/{id}/versions[/{v}]` | Verlauf mit Änderungen, Caddy-Route vorher/nachher |
| `POST /api/hosts/{id}/versions/{v}/restore` | Version wiederherstellen (= neue Version) |
| `GET /api/nodes` · `GET /api/nodes/{id}/config` · `POST /api/nodes/{id}/apply` | Nodes, erzeugte Config, erneut übertragen |
| `GET/PUT /api/settings/general` | Let's-Encrypt-E-Mail, öffentliche IPs des Nodes |
| `GET /api/audit` | Audit-Log (`q`, `limit`, `before_id`) |

### Speichern & übertragen

1. Änderung wird mit neuer Version und Audit-Eintrag gespeichert.
2. Der Controller erzeugt die **komplette** Config des betroffenen Nodes (`caddy/config.py`)
   und lädt sie per `POST /load`. Caddy prüft sie und behält bei Fehlern die alte.
3. Schlägt das fehl, bleibt die Änderung gespeichert; der Node zeigt den Fehler und
   „nicht synchron“, bis `POST /api/nodes/{id}/apply` klappt.

Beim Start überträgt der Controller die Config einmal an alle Nodes (mit Wiederholungen,
falls Caddy später startet). Die Controller-Domain (`TESSERACT_CONTROLLER_DOMAIN`) bekommt
immer eine eigene Route, damit sich der Controller nicht aussperrt.

## Zertifizierungsstelle (Phase 2)

- `POST /api/ca/setup` erzeugt Root-CA (ECDSA P-384, 10 Jahre) und Geräte-Zwischenzertifikat
  (3 Jahre). Die Antwort enthält den **mit der Passphrase verschlüsselten Root-Schlüssel** – der
  Controller speichert ihn nicht.
- Der Schlüssel des Zwischenzertifikats liegt mit AES-GCM verschlüsselt in der DB. Der
  Hauptschlüssel kommt aus `TESSERACT_SECRET_KEY` oder wird als `secret.key` im
  Datenverzeichnis angelegt. **Ohne ihn ist die CA nach einem Restore unbrauchbar** – getrennt
  von der Datenbank sichern.
- Geräte bekommen ECDSA-P-256-Zertifikate (EKU clientAuth). Der Schlüssel wird beim Ausstellen
  erzeugt, als `.p12` (3DES/SHA1 für maximale Kompatibilität) mit Einmal-Passwort ausgeliefert
  und nicht gespeichert.
- Der Fingerabdruck (SHA-256 über DER, hex) entspricht Caddys `{http.request.tls.client.fingerprint}`.

| Methode & Pfad | Zweck |
|---|---|
| `GET /api/ca` · `POST /api/ca/setup` · `GET /api/ca/root.pem` | Status, Einrichten, Root-Zertifikat |
| `GET/POST /api/groups` · `PUT/DELETE /api/groups/{id}` | Gruppen (Gruppe `Admin` ist eingebaut) |
| `GET/POST /api/persons` · `GET/PUT/DELETE /api/persons/{id}` | Personen mit Gruppen und Geräten |
| `POST /api/persons/{id}/devices` | Zertifikat direkt ausstellen (liefert `.p12` einmalig) |
| `GET /api/devices` · `POST /api/devices/{id}/revoke` · `GET /api/devices/revoked.csv` | Geräte, sperren, Export |

## Einladungen (Phase 2)

1. Admin: `POST /api/persons/{id}/invites` → Link `https://<controller>/e/<token>`, QR-Code
   (`GET /api/invites/{id}/qr.svg`) und 6-stelliger **Bestätigungscode**, der separat
   (z. B. am Telefon) weitergegeben wird. Token und Code liegen verschlüsselt in der DB,
   gesucht wird über den SHA-256 des Tokens. Gültig 7 Tage (1–30).
2. Gast (öffentlich, ohne Anmeldung): `GET /api/enroll/{token}` zeigt Name, freie Plätze und
   die erreichbaren Dienste; `POST /api/enroll/{token}/register` mit Gerätename, Plattform und
   Code legt eine Anfrage an und liefert ein Geheimnis für die Statusabfrage
   (`X-Enroll-Secret`). 5 falsche Codes sperren die Einladung, zusätzlich Bremse pro IP.
3. Admin: `POST /api/enrollments/{id}/approve` bzw. `/reject`.
4. Gast: `POST /api/enroll/{token}/requests/{id}/certificate` liefert die `.p12` mit
   Einmal-Passwort – **genau einmal**. Danach werden die Freigabelisten neu übertragen.

Die Seite `/e/<token>` ist der einzige Teil des Controllers, der ohne Anmeldung und ohne
Admin-Zertifikat erreichbar ist.

## Oberfläche nur mit Admin-Zertifikat

- Caddy fragt auf der Controller-Domain immer nach einem Client-Zertifikat
  (`verify_if_given`) und reicht den Fingerabdruck als `X-Tesseract-Client-Fingerprint`
  an den Controller weiter (ein vom Client gesendeter Header wird überschrieben).
- `GET /api/auth/device` erkennt Admin-Geräte (aktive Geräte nicht gesperrter Personen in der
  eingebauten Gruppe `Admin`) – die Login-Seite zeigt „Admin-Gerät erkannt“.
- `PUT /api/settings/admin-access` schaltet den Schutz ein, **aber nur**, wenn die Anfrage
  gerade selbst mit einem Admin-Zertifikat kommt (Schutz vor dem Aussperren). Dann sperrt Caddy
  alles außer `/e/*`, `/api/enroll/*`, `/assets/*`, `/api/health`, und der Controller prüft
  zusätzlich jede angemeldete Anfrage und den Login.
- Notausgang: `tesseract admin mtls off`.

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
| `TESSERACT_CADDY_TLS_ADDRESS` | Host der Admin-URL `:443` | HTTPS-Port von Caddy für die Zertifikatsübersicht |
| `TESSERACT_CADDY_ADMIN_LISTEN` | `0.0.0.0:2019` | Admin-Adresse, die in die erzeugte Caddy-Config geschrieben wird |
| `TESSERACT_CONTROLLER_DOMAIN` | – | Domain der Tesseract-Oberfläche (Compose: `TESSERACT_DOMAIN`) |
| `TESSERACT_CONTROLLER_UPSTREAM` | `tesseract:8000` | Wie Caddy den Controller erreicht |
| `TESSERACT_SYNC_ON_START` | `true` | Beim Start die Config an alle Nodes übertragen |
| `TESSERACT_SECRET_KEY` | – | Hauptschlüssel (Base64, 32 Byte); leer = `secret.key` im Datenverzeichnis |
| `TESSERACT_CADDY_WAF_LOG` | – | Pfad im Caddy-Container für WAF-Treffer (Auto-Sperre) |
| `TESSERACT_WAF_LOG_PATH` | – | Pfad, unter dem der Controller dieselbe Datei liest |
| `TESSERACT_BACKGROUND_TASKS` | `true` | Hintergrundaufgaben (Auto-Sperre) |
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
