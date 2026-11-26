# Deployment

## Images

Veröffentlicht unter `ghcr.io/hicubebot/<image>:<version>` (amd64, arm64) bei jedem
Versions-Tag (`.github/workflows/release.yml`); `compose.yaml` nutzt sie mit
`TESSERACT_VERSION` (Standard `latest`).

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

Das Admin-Passwort kommt aus `TESSERACT_ADMIN_PASSWORD` in der `.env`. Ist es leer, steht nach
dem ersten Start ein Zufallspasswort im Log:

```bash
docker compose logs tesseract | grep "Erster Start"
```

### Erste Schritte nach dem Start

1. Anmelden – mit `TESSERACT_ADMIN_PASSWORD` aus der `.env` oder, wenn keins gesetzt ist, mit dem
   Zufallspasswort aus dem Log (dann unter Einstellungen ändern).
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

Vorlage mit allen Einstellungen: [`.env.example`](../.env.example) → `cp .env.example .env`.
Die Kommentare darin sind englisch und reines ASCII – Umlaute machen in manchen Editoren
(z. B. nano im Terminal) Probleme. Der Controller bekommt alle `TESSERACT_*`-Variablen aus der
`.env` (`env_file` in `compose.yaml`); was unter `environment:` steht, gehört zum Stack und hat
Vorrang.

**Compose-Profile** – zusätzliche Dienste, festgelegt in der `.env` über `COMPOSE_PROFILES`
(Standard der Vorlage: `anubis,victorialogs`). Dann reicht immer `docker compose up -d`:

| Profil | Dienst |
|---|---|
| `anubis` | Bot-Schutz (Proof-of-Work gegen KI-Crawler und Scraper), siehe unten |
| `victorialogs` | Log-Speicher für lange Aufbewahrung (weniger RAM als Loki) – in der Vorlage schon angebunden |
| `loki` | Log-Speicher für Grafana (statt `victorialogs`) |
| `docker` | Socket-Proxy (nur lesen) für Hosts aus Docker-Labels |

Leer lassen = nur Tesseract und Caddy. Einmalig zusätzlich geht auch
`docker compose --profile loki up -d`.

| Variable | Bedeutung |
|---|---|
| `TESSERACT_DOMAIN` | Domain des Controller-UIs (Standard `localhost`) |
| `TESSERACT_LOG_LEVEL` | Log-Level des Controllers |
| `TESSERACT_ADMIN_NETWORKS` | Netze, aus denen die Oberfläche erreichbar ist (Standard alle). Öffentliche Seiten für Gäste bleiben erreichbar, die Schnittstelle für Nodes je nach `TESSERACT_AGENT_API_PUBLIC` (Standard: erreichbar) |
| `TESSERACT_ADMIN_USERNAME` · `TESSERACT_ADMIN_PASSWORD` (oder `…_FILE`) | Admin-Zugang. Mit Passwort gilt es bei jedem Start und ist in der Oberfläche gesperrt |
| `TESSERACT_CLOUDFLARE_TOKEN` (oder `…_FILE`) | Cloudflare-Token für DNS-01 – auch die Oberfläche holt ihr Zertifikat dann per DNS (ohne Portweiterleitung). In der Oberfläche gesperrt |
| `TESSERACT_ACME_EMAIL` · `TESSERACT_LOGS_DAYS` · `TESSERACT_INTERNAL_NETWORKS` · `TESSERACT_TRUSTED_PROXIES` | Einstellungen der Oberfläche festlegen – werden bei jedem Start gesetzt, die Oberfläche weist darauf hin |
| `TESSERACT_SECRET_KEY` | Hauptschlüssel (sonst `secret.key` im Datenvolume) |
| `TESSERACT_SESSION_HOURS` · `TESSERACT_SESSION_REMEMBER_DAYS` · `TESSERACT_GEOIP_DB` | siehe [backend.md](backend.md#konfiguration) |

Alle weiteren Controller-Variablen: [backend.md](backend.md#konfiguration).

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

## Bot-Schutz mit Anubis (optional)

[Anubis](https://github.com/TecharoHQ/anubis) stellt Browsern vor dem Dienst eine kurze
Proof-of-Work-Aufgabe. Besucher merken davon kaum etwas, KI-Crawler und Scraper werden teuer oder
abgewiesen. Ein Anubis-Container je Node prüft für alle Hosts dieses Nodes (Subrequest-Modus,
Caddy fragt per `forward_auth`).

Im Controller-Stack ist das Profil `anubis` in der Vorlage schon eingeschaltet
(`COMPOSE_PROFILES=anubis,victorialogs` in der `.env`). Auf weiteren Nodes mit geschützten Hosts
in deren `.env` `COMPOSE_PROFILES=anubis` setzen – oder einmalig:

```bash
docker compose --profile anubis up -d
```

1. Unter Einstellungen › Integrationen › Bot-Schutz die Adresse eintragen: `http://anubis:8923`
   (gilt für alle Nodes – dort heißt der Container gleich).
2. Je Host unter Sicherheit › „Bot-Schutz einschalten“, optional nur für bestimmte Pfade.
3. **Ausnahmen** für Apps ohne Browser (Bitwarden, Home Assistant, WebDAV, Feeds, APIs): deren
   Pfade unter „Nie unter diesen Pfaden“ eintragen. Ohne Prüfung kommen außerdem Geräte mit
   freigegebenem Zertifikat, die internen Netze (abschaltbar) und erwünschte Bots per User-Agent.

- Reihenfolge: IP-Filter → Zertifikat → WAF → Bot-Schutz → Authelia → Dienst.
- Policy: die Standard-Policy von Anubis (bekannte schlechte Bots abweisen, gute Suchmaschinen
  durchlassen, Browser prüfen), mitgeliefert in der Compose-Datei – mit `DENY: 403`, denn bei
  `forward_auth` hieße die Anubis-Voreinstellung 200 „durchlassen“.
- `.env`: `ANUBIS_DIFFICULTY` (Standard 4), `ANUBIS_KEY` (64 Hex-Zeichen, `openssl rand -hex 32`,
  damit bestandene Prüfungen einen Neustart überleben), `ANUBIS_VERSION`.
- Ist ein Host geschützt, aber keine Anubis-Adresse eingetragen oder Anubis nicht erreichbar,
  antwortet der Host mit einem Fehler statt ungeschützt – lieber zu als offen.
- Statistik › Sicherheit zeigt, wie viele Anfragen zur Prüfung geschickt, abgewiesen und
  bestanden wurden; im Log steht der Grund „Bot-Schutz“.

## GeoIP (optional)

Für Länder in Logs, Statistik und auf der Herkunftskarte braucht der Controller eine
Datenbank im Format `.mmdb`. Abgefragt wird nur lokal – keine IP verlässt den Server.

**Am einfachsten – automatisch:** in der `.env`

```
TESSERACT_GEOIP_AUTO=dbip
```

Der Controller holt dann „IP to Country Lite“ von DB-IP (ohne Konto), prüft die Datei, legt
sie unter `/data/geoip/` ab und übernimmt sie ohne Neustart. Er schaut alle 6 Stunden nach und
lädt einmal im Monat die neue Ausgabe; ein Fehlschlag lässt die vorhandene Datenbank in
Gebrauch. Stand und „Jetzt aktualisieren“ unter Einstellungen › Metriken › Logs. Das ist die
einzige Verbindung nach außen und deshalb standardmäßig aus.

Mehr Details auf der Karte (Statistik › Karte):

| Wert | Datenbank | Größe | Ergebnis |
|---|---|---|---|
| `dbip` | IP to Country Lite | ~8 MB | Länder |
| `dbip-city` | IP to City Lite | ~130 MB | Länder, Städte, Punkte auf der Karte |
| `+asn` dazu, z. B. `dbip+asn` | IP to ASN Lite | ~10 MB | Netzbetreiber (Telekom, Hetzner, Amazon …) |

Eine eigene ASN-Datei (z. B. GeoLite2-ASN) geht mit `TESSERACT_GEOIP_ASN_DB`. Städte und
Netzbetreiber werden beim Eintreffen der Logs gespeichert – ältere Einträge bleiben ohne.

Läuft im Netz ein DNS-Filter (Pi-hole, AdGuard Home), muss `download.db-ip.com` dort erlaubt
sein – manche Sperrlisten führen die Domain. Sonst steht in den Einstellungen „DB-IP nicht
erreichbar … DNS-Filter?“.

Oder von Hand als Datei:

**Variante 1 – DB-IP „IP to Country Lite“ (ohne Konto):** monatlich neu, Lizenz CC BY 4.0
(Quellenangabe „IP Geolocation by DB-IP“, wenn man Auswertungen weitergibt).
Übersicht: <https://db-ip.com/db/download/ip-to-country-lite>

```bash
mkdir -p geoip
curl -L https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz | gunzip > geoip/country.mmdb
```

**Variante 2 – MaxMind GeoLite2-Country (kostenloses Konto):** Konto anlegen unter
<https://www.maxmind.com/en/geolite2/signup>, Lizenzschlüssel erzeugen und
`GeoLite2-Country.mmdb` herunterladen (oder automatisch mit `geoipupdate`). Es gilt die
GeoLite2-Lizenz von MaxMind.

Einbinden (z. B. in einer `compose.override.yaml`), danach `docker compose up -d`:

```yaml
services:
  tesseract:
    environment:
      TESSERACT_GEOIP_DB: /geoip/country.mmdb
    volumes:
      - ./geoip:/geoip:ro
```

Die Datenbank alle paar Wochen erneuern (gleicher Dateiname, Controller neu starten). Mit
`TESSERACT_GEOIP_AUTO` hat die automatisch geholte Datei Vorrang; `TESSERACT_GEOIP_DB` gilt nur,
bis sie das erste Mal geladen ist. Länder gibt es nur für öffentliche Adressen; private und
lokale IPs bleiben ohne Land.
