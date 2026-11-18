# Tesseract-Agent (Phase 4)

Der Agent läuft neben Caddy auf jedem weiteren Node. Er baut die Verbindung zum Controller
**selbst und ausgehend** auf (HTTPS mit Client-Zertifikat). Deshalb funktioniert er hinter NAT
und braucht keinen offenen Admin-Port und kein VPN. Den lokalen Caddy im Compose-Stack des
Controllers spricht der Controller weiterhin direkt an (Node `local`).

```
  Raspberry Pi (hinter NAT)                      Controller
 ┌───────────────────────────┐  HTTPS + mTLS   ┌────────────────────────┐
 │ Caddy  ◄── Admin-API ──┐  │  nur ausgehend  │ Caddy (Controller-     │
 │                        │  │ ──────────────► │ Domain) → FastAPI      │
 │        Tesseract-Agent ┘  │                 │ /api/agent/*           │
 └───────────────────────────┘                 └────────────────────────┘
```

Paket und Image: `agent/` (Python 3.13, nur `httpx` und `cryptography`).

## Node hinzufügen

1. **Controller › Nodes › Node hinzufügen** – Name (z. B. `pi-eltern`) und Standort. Der
   Controller zeigt ein **Beitritts-Token** (30 Minuten gültig, einmal verwendbar) mit
   fertigem Befehl und Compose-Ausschnitt. Voraussetzung: die Zertifizierungsstelle ist
   eingerichtet, denn sie signiert die Node-Zertifikate.
2. **Auf dem Node** Caddy und Agent starten, Vorlage: [`docker/node/compose.yaml`](../docker/node/compose.yaml)
   ```bash
   cat > .env <<'EOF'
   TESSERACT_CONTROLLER=https://tesseract.beispiel.de
   TESSERACT_JOIN_TOKEN=<Token aus dem Controller>
   EOF
   docker compose up -d
   docker compose logs agent
   ```
   Der Agent erzeugt seinen Schlüssel (ECDSA P-256) selbst, schickt eine Zertifikatsanfrage
   (CSR) und gibt den **Fingerabdruck seines Schlüssels** aus.
3. **Im Controller bestätigen**: Die Anfrage erscheint unter Nodes (und in der Übersicht) mit
   Rechnername und Schlüssel-Fingerabdruck. Bestätigen Sie nur, wenn der Fingerabdruck mit der
   Ausgabe des Agents übereinstimmt. Der Controller signiert die CSR mit dem
   Geräte-Zwischenzertifikat (CN `node:<name>`, EKU clientAuth, 2 Jahre).
4. Der Agent holt Zertifikat und Agent-Token **genau einmal** ab und verbindet sich ab dann
   nur noch per mTLS. Danach lassen sich dem Node unter Proxy-Hosts Hosts zuweisen.

Ohne Docker geht es genauso mit der Kommandozeile:

```bash
cd agent && uv sync
uv run tesseract-agent join --controller https://tesseract.beispiel.de --token <Token>
uv run tesseract-agent run        # verbunden bleiben
uv run tesseract-agent status
```

Ist der Agent neu aufzusetzen (Daten weg, neuer Rechner): **Neues Token** am Node erzeugen
und erneut beitreten. Mit der Bestätigung verliert das alte Zertifikat seine Gültigkeit.

## Was der Agent tut

| Aufgabe | Wie |
|---|---|
| **Config** | Long-Polling `GET /api/agent/config?known=<hash>&force=<n>&wait=25`. Bei einer Änderung kommt die komplette Config, der Agent lädt sie per `POST /load` in Caddy. Lehnt Caddy sie ab, läuft der alte Stand weiter und der Fehler wird gemeldet; derselbe Stand wird nicht erneut versucht. |
| **Status** | Alle 30 s und direkt nach jedem Laden: geladene und **laufende** Config (Prüfsumme), erkannte Module, Agent- und Caddy-Version. |
| **Abweichung** | Weicht die laufende Config von der geladenen ab (jemand hat Caddy direkt geändert), schickt der Agent sie mit (Base64-JSON). Der Controller zeigt die Unterschiede pro Host. |
| **WAF-Treffer** | Neue Zeilen aus Caddys WAF-Log landen zuerst in einem Puffer auf der Platte (`/data/waf-buffer.jsonl`, höchstens 50 000 Zeilen) und werden nachgeliefert. Sie zählen für die Auto-Sperre wie die des lokalen Caddy. |
| **Module** | Über Caddys `/adapt` (nichts wird geladen): `http.handlers.waf` (Coraza) und `dns.providers.cloudflare`. Fehlt ein Modul, warnt die Nodes-Seite. |

Ist der Controller nicht erreichbar, läuft Caddy mit dem zuletzt geladenen Stand weiter
(`--resume`), und der Agent versucht es mit wachsender Pause (bis 60 s) erneut. Nach 90 s
ohne Kontakt zeigt der Controller den Node als **offline**.

## Abweichung: überschreiben oder übernehmen

- **Mit Controller überschreiben**: Der Controller zählt `force` hoch, und der Agent lädt den
  Stand des Controllers neu, auch wenn sich dort nichts geändert hat.
- **Änderung übernehmen**: Die laufende Config gilt als in Ordnung und wird nicht mehr als
  Abweichung gemeldet. Sie bleibt nur so lange, bis der Controller die nächste Änderung an
  diesen Node überträgt. In die Hosts des Controllers wird sie **nicht** übernommen;
  dauerhafte Änderungen gehören in den Controller.

Beim lokalen Node prüft der Controller selbst alle 30 Sekunden die laufende Config.

## Sicherheit

- Der Agent authentifiziert sich doppelt: mit dem **Node-Zertifikat** (Caddy auf der
  Controller-Domain prüft es gegen das Zwischenzertifikat und reicht den Fingerabdruck weiter)
  **und** mit dem **Agent-Token** (`Authorization: Bearer …`, im Controller nur als SHA-256).
- `/api/agent/*` bleibt auch bei „Oberfläche nur mit Admin-Zertifikat“ ohne Admin-Zertifikat
  erreichbar; die Prüfung macht der Controller selbst. Beitritt und Abholen sind wie die
  Einladungsseite pro IP gebremst.
- Node-Zertifikate stehen in keiner Freigabeliste und öffnen deshalb keine Hosts.
- Die Admin-API von Caddy bleibt im internen Docker-Netz des Nodes und wird nie veröffentlicht.
- Die Config enthält Geheimnisse (z. B. den Cloudflare-Token für DNS-01) im Klartext, denn
  Caddy braucht sie so. Sie geht nur über die mTLS-Verbindung.

## Einstellungen

| Variable | Standard | Bedeutung |
|---|---|---|
| `TESSERACT_AGENT_CONTROLLER` | – | Adresse des Controllers, z. B. `https://tesseract.beispiel.de` (nur für den Beitritt) |
| `TESSERACT_AGENT_JOIN_TOKEN` | – | Beitritts-Token; nach dem Beitritt ohne Wirkung |
| `TESSERACT_AGENT_DATA_DIR` | `data` (Image: `/data`) | Schlüssel, Zertifikat, Zustand, WAF-Puffer |
| `TESSERACT_AGENT_CADDY_ADMIN_URL` | `http://caddy:2019` | Admin-API des Caddy auf diesem Node |
| `TESSERACT_AGENT_CADDY_ADMIN_LISTEN` | `0.0.0.0:2019` | Admin-Adresse in der erzeugten Config; muss zur Admin-URL passen |
| `TESSERACT_AGENT_WAF_LOG` | – | WAF-Log von Caddy (gemeinsames Volume) |
| `TESSERACT_AGENT_CONTROLLER_CA` | – | CA-Datei, wenn das Zertifikat des Controllers nicht öffentlich vertraut ist (z. B. Caddys lokale CA bei `tesseract.lan`) |
| `TESSERACT_AGENT_CADDY_BIN` | `caddy` | Caddy-Programm für die Versionsanzeige. Im Docker-Betrieb meist nicht vorhanden, dann zeigt der Controller „–“ |
| `TESSERACT_AGENT_LOG_LEVEL` | `info` | Log-Level |

## Schnittstelle

| Methode & Pfad | Anmeldung | Zweck |
|---|---|---|
| `POST /api/agent/join` | Beitritts-Token | CSR, Rechnername, Version → `node_id`, Abhol-Geheimnis |
| `GET /api/agent/join/{node_id}` | `X-Join-Secret` | `202` wartet · `200` Zertifikat, Kette, Agent-Token (einmalig) · `403` abgelehnt |
| `GET /api/agent/config` | Zertifikat + Token | Soll-Config (Long-Polling, `204` ohne Änderung) |
| `POST /api/agent/status` | Zertifikat + Token | Status, laufende Config bei Abweichung |
| `POST /api/agent/waf` | Zertifikat + Token | gepufferte WAF-Log-Zeilen |

## Entwicklung

```bash
cd agent
uv sync
uv run pytest && uv run ruff check . && uv run ruff format --check .
docker build -t tesseract-agent:dev agent/     # aus der Repo-Wurzel
```
