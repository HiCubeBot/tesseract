# Deployment

## Images

| Image | Quelle | Inhalt |
|---|---|---|
| `tesseract` | `Dockerfile` (Repo-Wurzel) | Mehrstufig: baut das Svelte-Frontend (Node 22), installiert das Backend mit uv, Laufzeit auf `python:3.13-slim` als Nicht-Root-Nutzer. Liefert UI unter `/` und API unter `/api`. |
| `tesseract-agent` | `agent/Dockerfile` (Kontext `agent/`) | Agent für weitere Nodes, Python 3.13 als Nicht-Root-Nutzer. Siehe [agent.md](agent.md). |
| `tesseract-caddy` | `docker/caddy/Dockerfile` | Caddy 2.11, gebaut mit `xcaddy` inkl. `coraza-caddy` (WAF) und `caddy-dns/cloudflare` (DNS-01). |

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

### Erste Schritte nach dem Start

1. Mit dem Passwort aus dem Log anmelden und es unter Einstellungen ändern.
2. **Einstellungen › Zertifizierungsstelle** einrichten und den Root-Schlüssel offline sichern.
3. Unter **Nutzer** eine Person für dich in der Gruppe `Admin` anlegen und dein Gerät
   „direkt ausstellen“, die `.p12` installieren.
4. Die Oberfläche mit diesem Gerät öffnen – die Login-Seite zeigt „Admin-Gerät erkannt“.
5. **Einstellungen › Allgemein › Zugang zur Oberfläche** einschalten. Ab jetzt ist die
   Oberfläche nur noch mit Admin-Zertifikat erreichbar; die Einladungsseite `/e/…` bleibt öffentlich.

Notausgang, falls das Admin-Gerät verloren ist:

```bash
docker compose exec tesseract tesseract admin mtls off
```

### Sichern

Wichtig sind das Volume `tesseract-data` (Datenbank) **und** die Datei `secret.key` darin – ohne
sie lässt sich der Schlüssel des Zwischenzertifikats nicht entschlüsseln. Der Root-Schlüssel ist
nicht auf dem Server; den hast du beim Einrichten heruntergeladen.

### Volumes

| Volume | Inhalt |
|---|---|
| `tesseract-data` | Controller-Daten (`/data`): DB, CA-Zwischenzertifikat, Backups |
| `caddy-data` | ACME-Konten und Zertifikate |
| `caddy-config` | von Caddy gespeicherte Config |
| `caddy-logs` | WAF-Treffer (`waf.log`) – Caddy schreibt, der Controller liest (Auto-Sperre) |

### Umgebungsvariablen (`.env`)

| Variable | Bedeutung |
|---|---|
| `TESSERACT_DOMAIN` | Domain des Controller-UIs (Standard `localhost`) |
| (Let's-Encrypt-E-Mail) | wird im UI unter Einstellungen gesetzt |
| `TESSERACT_LOG_LEVEL` | Log-Level des Controllers |

Weitere Controller-Variablen: siehe [backend.md](backend.md#konfiguration).

## Weitere Nodes (Phase 4)

Weitere Nodes bekommen nur `tesseract-caddy` und den Agent. Vorlage:
[`docker/node/compose.yaml`](../docker/node/compose.yaml), Ablauf in [agent.md](agent.md).

```bash
docker build -t tesseract-caddy:dev docker/caddy
docker build -t tesseract-agent:dev agent
```

- Der Node braucht nur **ausgehend** HTTPS zur Controller-Domain. Ports 80/443 öffnet er
  nur für die eigenen Hosts.
- Damit WAF-Treffer und Zugriffe der Nodes in Logs, Statistik und Auto-Sperre ankommen, muss
  der Controller `TESSERACT_CADDY_WAF_LOG` und `TESSERACT_CADDY_ACCESS_LOG` gesetzt haben (im
  Compose-Stack schon so). Dieselben Pfade landen in der Config jedes Nodes; der Agent liest
  sie über `TESSERACT_AGENT_WAF_LOG` und `TESSERACT_AGENT_ACCESS_LOG`.

## GeoIP (optional)

Für Länder in Logs und Statistik eine lokale Datenbank einbinden, z. B. DB-IP „IP to Country
Lite“ oder MaxMind GeoLite2-Country (`.mmdb`, Lizenz beachten). Es geht keine Anfrage nach außen.

```yaml
services:
  tesseract:
    environment:
      TESSERACT_GEOIP_DB: /geoip/country.mmdb
    volumes:
      - ./geoip:/geoip:ro
```
