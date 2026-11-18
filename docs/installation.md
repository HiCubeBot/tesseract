# Installation

Tesseract läuft als zwei Container: der **Controller** (Oberfläche, API, Datenbank) und
**Caddy** (Reverse Proxy, Zertifikate, WAF). Weitere Server kommen als Nodes mit Agent dazu –
siehe [agent.md](agent.md).

## Voraussetzungen

- Linux-Server (amd64 oder arm64, z. B. Raspberry Pi 4/5) mit Docker und Docker Compose ≥ 2.24
- Ports **80** und **443** frei und aus dem Internet erreichbar (für Let's Encrypt per HTTP-01;
  mit DNS-01 über Cloudflare reicht 443 bzw. gar kein offener Port für rein interne Dienste)
- Ein DNS-Eintrag für die Oberfläche, z. B. `tesseract.beispiel.de` → IP des Servers
- Etwa 300 MB RAM, wenige hundert MB Platz (plus Logs, je nach Verkehr)

## Schritt für Schritt

```bash
mkdir tesseract && cd tesseract
curl -LO https://raw.githubusercontent.com/HiCubeBot/tesseract/main/compose.yaml
curl -L https://raw.githubusercontent.com/HiCubeBot/tesseract/main/.env.example -o .env
```

`.env` anpassen – mindestens:

```ini
TESSERACT_DOMAIN=tesseract.beispiel.de
TESSERACT_ADMIN_PASSWORD=ein-langes-passwort   # mind. 12 Zeichen
TESSERACT_ACME_EMAIL=admin@beispiel.de
# feste Version statt „latest“ empfohlen:
TESSERACT_VERSION=1.0.0
```

Starten (die veröffentlichten Images kommen aus der GitHub Container Registry):

```bash
docker compose pull
docker compose up -d
docker compose logs -f tesseract
```

Wer lieber selbst baut: Repository klonen und `docker compose up -d --build`.

Danach ist die Oberfläche unter `https://<TESSERACT_DOMAIN>` erreichbar.

## Erste Schritte

1. Mit `admin` und dem Passwort aus der `.env` anmelden.
2. **Einstellungen › Zertifizierungsstelle**: CA erzeugen. Den **Root-Schlüssel** samt
   Passphrase offline sichern (USB-Stick, Passwortmanager) – er wird nur für einen späteren
   CA-Wechsel gebraucht und liegt nie auf dem Server.
3. **Einstellungen › Backup**: Passphrase setzen, Zeitplan (z. B. täglich) und am besten ein
   zweites Ziel (S3) einrichten. Einmal „Jetzt sichern“ und „Testen“.
4. **Proxy-Hosts**: ersten Host anlegen.
5. Für private Dienste: unter **Nutzer** sich selbst in der Gruppe `Admin` anlegen, ein Gerät
   ausstellen und die `.p12` installieren. Dann **Einstellungen › Allgemein › Zugang zur
   Oberfläche** einschalten – die Oberfläche ist danach nur noch mit diesem Gerät erreichbar.
6. Optional: GeoIP-Datenbank ([deployment.md](deployment.md#geoip-optional)),
   Benachrichtigungen (ntfy, E-Mail, Webhook), Prometheus-Metriken.

## Weitere Nodes

Unter **Nodes › Node hinzufügen** einen Node anlegen und den angezeigten Befehl auf dem neuen
Server ausführen – z. B.:

```bash
curl -fsSL https://tesseract.beispiel.de/install/node.sh | sudo sh -s -- --token <Token>
```

Danach den angezeigten Fingerabdruck im Controller vergleichen und bestätigen. Optionen und
Sonderfälle (ohne Docker, private Images, interne Domain, ohne Internet): [agent.md](agent.md).

**Images:** Die Nodes laden `ghcr.io/hicubebot/tesseract-caddy` und `…/tesseract-agent`. Ist das
Repository privat, sind die Pakete es zunächst auch – entweder in GitHub unter *Packages ›
Package settings* auf „Public“ stellen (sie enthalten keine Geheimnisse) oder beim Installieren
`--registry-token` mitgeben.

## Wenn etwas nicht klappt

| Problem | Ursache / Lösung |
|---|---|
| Zertifikatsfehler im Browser | DNS zeigt noch nicht auf den Server, Port 80 zu, oder `TESSERACT_ACME_EMAIL` fehlt – `docker compose logs caddy` |
| Anmeldung schlägt sofort mit 429 fehl | zu viele Versuche – eine Minute warten |
| Oberfläche gesperrt (Admin-Gerät verloren) | `docker compose exec tesseract tesseract admin mtls off` |
| Passwort vergessen | in der `.env` neu setzen und `docker compose up -d` |
