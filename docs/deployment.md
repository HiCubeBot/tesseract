# Deployment

## Images

| Image | Quelle | Inhalt |
|---|---|---|
| `tesseract` | `Dockerfile` (Repo-Wurzel) | Mehrstufig: baut das Svelte-Frontend (Node 22), installiert das Backend mit uv, Laufzeit auf `python:3.13-slim` als Nicht-Root-Nutzer. Liefert UI unter `/` und API unter `/api`. |
| `tesseract-caddy` | `docker/caddy/Dockerfile` | Caddy, gebaut mit `xcaddy` inkl. `coraza-caddy` (WAF) und `caddy-dns/cloudflare` (DNS-01). |

## Compose-Stack

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

- `tesseract` – Controller auf Port 8000, nur im internen Netz.
- `caddy` – veröffentlicht 80/443 (inkl. HTTP/3), proxyt die Controller-Domain auf den Controller.
  Die Admin-API (Port 2019) ist nur im internen Netz erreichbar und wird **nicht** veröffentlicht.

Die mitgelieferte `docker/caddy/Caddyfile` gilt nur beim allerersten Start. Danach überträgt
der Controller die komplette Config als JSON über die Admin-API. Caddy läuft mit `--resume`
und startet nach einem Neustart mit der zuletzt geladenen Config (gespeichert in `caddy-config`).

Das Admin-Passwort steht nach dem ersten Start im Log:

```bash
docker compose logs tesseract | grep "Erster Start"
```

### Volumes

| Volume | Inhalt |
|---|---|
| `tesseract-data` | Controller-Daten (`/data`): DB, CA-Zwischenzertifikat, Backups |
| `caddy-data` | ACME-Konten und Zertifikate |
| `caddy-config` | von Caddy gespeicherte Config |

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `TESSERACT_DOMAIN` | Domain des Controller-UIs (Standard `localhost`) |
| `ACME_EMAIL` | Kontakt-E-Mail für Let's Encrypt |
| `TESSERACT_LOG_LEVEL` | Log-Level des Controllers |

Weitere Controller-Variablen: siehe [backend.md](backend.md#konfiguration).

## Nodes (ab Phase 4)

Weitere Nodes bekommen nur `tesseract-caddy` und den Agent; eine Compose-Vorlage dafür folgt
mit Phase 4.
