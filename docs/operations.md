# Betrieb

## Aktualisieren (Upgrade-Pfad)

Tesseract folgt [Semantic Versioning](https://semver.org/lang/de/): Innerhalb einer
Hauptversion (1.x) sind Updates ohne Handarbeit möglich.

```bash
# 1. Vorher sichern (Oberfläche: Einstellungen › Backup › Jetzt sichern) oder:
docker compose exec tesseract tesseract backup create
# 2. Version in der .env anheben (TESSERACT_VERSION=1.2.0) oder „latest“ lassen
docker compose pull
docker compose up -d
```

- **Datenbank-Migrationen** laufen beim Start automatisch. Ein Zurück auf eine ältere Version
  geht nur über das Backup von vorher.
- **Caddy** bekommt nach dem Start sofort wieder die komplette Config vom Controller.
- **Nodes:** zuerst den Controller, dann die Nodes aktualisieren
  (`docker compose pull && docker compose up -d` auf jedem Node). Der Controller versteht
  auch ältere Agents (ab 0.1); neue Funktionen (z. B. Logs ab 0.2, automatische
  Zertifikats-Erneuerung ab 0.3) brauchen den neuen Agent.
- Was sich je Version ändert: [CHANGELOG.md](../CHANGELOG.md).

## Sichern und Wiederherstellen

Siehe **Einstellungen › Backup**. Kurz:

- Gesichert werden Datenbank (Hosts, Personen, Geräte, Freigaben, Nodes, Verlauf, Audit-Log)
  und der Hauptschlüssel – verschlüsselt mit deiner Passphrase. Zugriffs-Logs nur auf Wunsch.
- **Nicht** enthalten: Root-Schlüssel der CA (liegt offline), Caddys Let's-Encrypt-Zertifikate
  (holt Caddy neu), die Nodes selbst (bekommen ihre Config vom Controller).
- Monatlich einen **Wiederherstellungstest** machen („Testen“ in der Liste) – er entschlüsselt
  und prüft die Datenbank, ohne etwas zu ändern.

Umzug oder Totalausfall des Controllers:

```bash
# Neuer Server: compose.yaml + .env wie bei der Installation, dann
docker compose up -d tesseract && docker compose stop tesseract
docker compose cp tesseract-20261118-030000.tsbak tesseract:/data/restore.tsbak
docker compose run --rm -e TESSERACT_BACKUP_PASSPHRASE='…' tesseract \
  tesseract backup restore /data/restore.tsbak
docker compose up -d
```

Alternativ in der Oberfläche: **Backup › Aus Datei wiederherstellen**. Die Nodes melden sich
danach wieder (ihre Zertifikate stecken in der Sicherung) und bekommen die Config.

Wer `TESSERACT_SECRET_KEY` nutzt, muss auf dem neuen Server denselben Wert setzen.

### Restic als Ziel

Unter **Backup › Ziele › Restic-Repository** Repository und Passwort eintragen, speichern und
„Verbindung prüfen“ – fehlt das Repository, legt der Controller es an. Jede Sicherung wird ein
Snapshot mit genau einer Datei (Tag `tesseract`); aufgeräumt wird mit
`restic forget --keep-last N --prune` (N = „Aufbewahren“). Restic steckt im Controller-Image.

| Repository | Beispiel | Zugangsdaten (Feld „Umgebung“) |
|---|---|---|
| REST-Server | `rest:https://nas:8000/tesseract` | Nutzer/Passwort in der URL |
| S3 / MinIO | `s3:https://minio.beispiel.de/backups/tesseract` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Backblaze B2 | `b2:bucket:tesseract` | `B2_ACCOUNT_ID`, `B2_ACCOUNT_KEY` |
| SFTP | `sftp:backup@nas:/restic/tesseract` | SSH-Schlüssel im Volume, siehe unten |
| Verzeichnis | `/data/restic` | – (schützt nicht vor Ausfall des Servers) |

Die Sicherung ist schon mit der Passphrase verschlüsselt, Restic verschlüsselt das Repository
zusätzlich. Deduplizieren kann Restic verschlüsselte Dateien kaum – der Gewinn liegt bei den
vielen Speicherorten und der Aufbewahrung. Wiederherstellen geht wie bei den anderen Zielen
(Liste › Wiederherstellen) oder von Hand:

```bash
restic -r rest:https://nas:8000/tesseract snapshots --tag tesseract
restic -r rest:https://nas:8000/tesseract dump <id> /tesseract-20261120-030000.tsbak > restore.tsbak
```

SFTP braucht einen SSH-Schlüssel ohne Passphrase im Container (`/app/.ssh/id_ed25519` per
Volume, Besitzer `tesseract`) und den Server in `known_hosts`; einfacher ist der REST-Server.

### Git-Spiegel

Zusätzlich zu den Sicherungen kann der Controller die Config lesbar in ein Git-Repository
schreiben (**Backup › Ziele › Git-Spiegel**). Etwa 30 Sekunden nach jeder Änderung entsteht
ein Commit; die Nachricht nennt die Einträge aus dem Audit-Log (wer hat was geändert).

| Datei | Inhalt |
|---|---|
| `hosts/<domain>.json` | Einstellungen pro Host wie im Verlauf |
| `nodes/<name>.caddy.json` | Caddy-Config pro Node, Schlüssel geschwärzt, ohne IP-Sperren |
| `ip-lists.json`, `settings.json` | IP-Listen und Einstellungen ohne Geheimnisse |

Anmeldung per **Token** über HTTPS (GitHub, Gitea, GitLab: Token mit Schreibrecht auf das
Repository) oder per **SSH-Deploy-Key** (privater Schlüssel, z. B. `ssh-keygen -t ed25519`;
den öffentlichen Schlüssel beim Repository mit Schreibrecht eintragen). Beim ersten Kontakt
merkt sich der Controller den Host-Schlüssel des Servers (`/data/git-mirror-known_hosts`).

Der Spiegel ersetzt die Sicherungen nicht: Personen, Geräte und Schlüssel fehlen. Er ist
für Nachvollziehbarkeit gedacht und für den Notfall, eine Caddy-Config von Hand zu laden.
Das Repository sollte trotzdem privat sein – es zeigt Hostnamen, interne Ziele und Netze.

## Zertifizierungsstelle

| Was | Wann | Wie |
|---|---|---|
| Gerät verlängern | Erinnerung 30 und 7 Tage vorher | **Geräte › Verlängern** – neue `.p12`, Freigaben bleiben; oder der Gast selbst über `https://<controller>/v` (abschaltbar) |
| Zwischenzertifikat wechseln | Erinnerung 90/30/7 Tage vorher (gilt 3 Jahre) | **Einstellungen › Zertifizierungsstelle › Wechsel** mit Root-Schlüssel; alte Geräte funktionieren weiter, bis sie verlängert sind |
| Root-CA wechseln | Root läuft ab (10 Jahre), Root-Schlüssel verloren oder kompromittiert, Umzug auf eine vorhandene PKI | **Einstellungen › Zertifizierungsstelle › Wechsel der Root-CA**: neu erzeugen (neuer Root-Schlüssel zum Sichern) oder importieren. Alte Geräte funktionieren weiter, bis sie verlängert sind; Nodes erneuern selbst. Das neue Root-Zertifikat dort installieren, wo das alte als vertrauenswürdig hinterlegt ist |
| Node-Zertifikat | gilt 2 Jahre | erneuert der Agent ab 60 Tage vorher selbst |
| Root-Zertifikat | gilt 10 Jahre | neue CA einrichten (Backlog: Import/Übergang) |

## Überwachen

- **Übersicht** zeigt Nodes, Abweichungen, Beitrittsanfragen.
- **Benachrichtigungen** melden u. a. Node offline, fehlgeschlagene Übertragung oder
  Sicherung, Abweichungen, Ablauf von Zertifikaten.
- **Prometheus:** `/metrics` (Einstellungen › Metriken), Grafana-Dashboard zum Herunterladen.
- **Loki oder VictoriaLogs (optional):** für lange Aufbewahrung der Zugriffs- und WAF-Logs,
  siehe unten.
- **Audit-Log:** Prüfung der Prüfsummenkette oben auf der Seite.

### Logs in Loki

Die Log-Ansicht und die Statistik nutzen die eigene Datenbank (Aufbewahrung: Einstellungen ›
Metriken, Standard 14 Tage). Für längere Aufbewahrung oder Auswertung in Grafana schickt der
Controller jeden Eintrag zusätzlich an Loki.

```bash
# in der .env
TESSERACT_LOKI_URL=http://loki:3100
LOKI_RETENTION=2160h   # 90 Tage, optional

docker compose --profile loki up -d
```

Ein vorhandenes Loki trägt man stattdessen unter Einstellungen › Metriken › Loki ein (optional
mit Mandant `X-Scope-OrgID`). Ist Loki nicht erreichbar, puffert der Controller bis zu 50 000
Einträge im Speicher und sendet sie nach.

In Grafana Loki als Datenquelle hinzufügen (`http://loki:3100`, dazu Grafana ins Netz
`internal` des Stacks hängen oder den Port 3100 in `compose.yaml` freigeben). Beispiele:

```logql
{job="tesseract", reason="waf"} | json
sum by (host) (count_over_time({job="tesseract"} | json | status >= 500 [5m]))
{job="tesseract"} | json | ip="198.51.100.7"
```

### Logs in VictoriaLogs

Statt Loki geht auch VictoriaLogs (weniger Speicher und RAM, eigene Abfragesprache LogsQL).
Der Controller schickt dieselben Einträge über die JSON-Lines-Schnittstelle
(`/insert/jsonline`); `job`, `node`, `host` und `reason` sind Stream-Felder, alle anderen Werte
(`status`, `ip`, `country`, `waf_rules` …) einzelne Felder.

```bash
# in der .env
TESSERACT_LOKI_URL=http://victorialogs:9428
TESSERACT_LOKI_KIND=victorialogs
VICTORIALOGS_RETENTION=90d   # optional

docker compose --profile victorialogs up -d
```

Oder unter Einstellungen › Metriken › Log-Speicher „VictoriaLogs“ wählen und die URL
eintragen; Mandant als `AccountID` oder `AccountID:ProjectID`. In Grafana mit dem Plugin
„VictoriaLogs“, oder direkt in der eingebauten Oberfläche unter `/select/vmui`. Beispiele:

```logsql
{job="tesseract", reason="waf"}
{job="tesseract"} status:>=500 | stats by (host) count()
{job="tesseract"} ip:="198.51.100.7"
```

### Log-Ansicht und Statistik aus Loki/VictoriaLogs

Unter **Einstellungen › Metriken › Log-Speicher** „Log-Ansicht und Statistik aus … lesen“
einschalten (oder `TESSERACT_LOGS_EXTERNAL=true`). Dann fragen Suche, Live-Ansicht, Details und
Statistik den Log-Speicher – so weit zurück, wie er aufbewahrt (Loki: `LOKI_RETENTION`,
VictoriaLogs: `VICTORIALOGS_RETENTION`). Die eigene Datenbank sammelt weiter; sie braucht der
Controller für Auto-Sperre, Benachrichtigungen und „zuletzt gesehen“ der Geräte.

- Suche: dieselbe Syntax wie sonst, übersetzt nach LogQL bzw. LogsQL. Bei VictoriaLogs gehen
  IP-Netze nur für IPv4 (`ip:198.51.100.0/24`).
- Loki begrenzt eine Abfrage auf 30 Tage (`max_query_length`) – länger zurück blättern geht
  über „Ältere laden“.
- Kennzahlen sind Aggregat-Abfragen (`sum by … count_over_time` bzw. `| stats by …`); Mediane
  und p95 rechnet der Log-Speicher, sie können leicht von SQLite abweichen.
- Nachträglich auf einmal eingespielte alte Logs zeigt Loki erst, wenn der Ingester sie
  geschrieben hat (`query_ingesters_within`, Standard 3 Stunden); im laufenden Betrieb fällt
  das nicht auf.

## DNS-Einträge automatisch (Cloudflare)

Unter **Einstellungen › Integrationen › DNS-Einträge** pro Domain festlegen, wie neue Hosts
eingetragen werden:

| Art | Wert | Typischer Fall |
|---|---|---|
| CNAME | ein Name, z. B. `home.beispiel.de` | Heimnetz mit DDNS: alle Hosts zeigen auf den DDNS-Namen |
| A / AAAA | öffentliche IPs des Nodes (Nodes › Bearbeiten) oder eigene | Server mit fester IP; AAAA für IPv6 |

Beim Anlegen oder Bearbeiten eines Hosts dann „DNS-Eintrag bei Cloudflare › Automatisch
anlegen“. Art, Ziel und Proxy lassen sich pro Host ändern. Tesseract legt den Eintrag an, bevor
es die Config an Caddy überträgt (damit Let's Encrypt den Namen findet), ändert ihn mit dem Host
und löscht ihn mit dem Host. Entwürfe bekommen noch keinen Eintrag.

- Nur Einträge, die Tesseract selbst angelegt hat (Kommentar „Tesseract: <domain>“), werden
  geändert oder gelöscht. Gibt es den Namen schon mit anderem Wert, meldet Tesseract das und
  lässt ihn stehen; hat er bereits den gewünschten Wert, wird er übernommen.
- Schlägt etwas fehl, bleibt der Host trotzdem gespeichert; der Fehler steht beim Host, erneutes
  Speichern versucht es noch einmal.
- Über den Cloudflare-Proxy (orange Wolke) gehen weder Client-Zertifikate (mTLS) noch „Nur aus
  internen Netzen“ – Tesseract lehnt die Kombination ab.
- Der Token braucht „Zone › Zone › Lesen“ und „Zone › DNS › Bearbeiten“ – dieselben Rechte wie
  für DNS-01. „Zugriff prüfen“ in den Einstellungen testet das.

### Eintrag für die Tesseract-Domain (Nodes)

Nodes außerhalb des Heimnetzes erreichen den Controller nur, wenn `TESSERACT_DOMAIN` öffentlich
auflöst. Unter **Einstellungen › Integrationen › DNS-Einträge › Tesseract-Domain für die Nodes**
legt Tesseract dafür einen CNAME (Standard: Ziel der Domain, z. B. der DDNS-Name) oder A/AAAA
(Standard: öffentliche IPs des lokalen Nodes) an. Nie über den Cloudflare-Proxy – die Nodes
melden sich mit eigenem Zertifikat. Der Eintrag wird beim Start und bei neuen IPs des lokalen
Nodes nachgezogen.

Zusammen mit `TESSERACT_ADMIN_NETWORKS` ergibt das: Die Oberfläche ist nur aus dem Heimnetz
erreichbar, die Nodes melden sich trotzdem von überall (`TESSERACT_AGENT_API_PUBLIC=true`,
Standard). Ändern sich die öffentlichen IPs eines Nodes (Nodes › Bearbeiten), zieht Tesseract
auch die A/AAAA-Einträge der Hosts darauf nach.

## Hosts aus Docker-Labels

Container mit dem Label `tesseract.domain` werden zu Proxy-Hosts:

```yaml
services:
  navidrome:
    image: deluan/navidrome
    networks: [tesseract_internal]   # Caddy muss den Container erreichen
    labels:
      tesseract.domain: "musik.beispiel.de"
      tesseract.port: "4533"          # entfällt bei genau einem Port
      tesseract.access: "mtls"        # public | mtls
      tesseract.grants: "Familie"     # vorhandene Gruppen/Personen
      tesseract.waf: "block"          # off | detect | block
```

Weitere Labels: `tesseract.scheme` (http/https), `tesseract.upstream` (Ziel-Adresse, Standard
ist der Container-Name), `tesseract.internal` (true/false), `tesseract.tls` (http/dns),
`tesseract.robots` (off/allow/deny/deny-ai, robots.txt von Caddy),
`tesseract.enable` (false = überspringen).

Einrichten auf dem Controller-Server:

```bash
# .env
TESSERACT_DOCKER_HOST=tcp://docker-proxy:2375
docker compose --profile docker up -d
```

Der Socket-Proxy gibt nur die Container-Liste frei (Nur-Lese). Danach unter **Einstellungen ›
Integrationen › Docker-Labels** einschalten. Auf Agent-Nodes `TESSERACT_AGENT_DOCKER_HOST`
setzen (ebenfalls am besten auf einen Socket-Proxy); der Agent meldet die Container mit jedem
Status.

Regeln: Neue Hosts sind Entwürfe, bis du sie überträgst (oder „Neue Hosts direkt übertragen“).
Ändern sich die Labels, gelten sie; andere Felder stellst du in der Oberfläche ein. Gestoppte
oder entfernte Container schalten ihren Host ab, ein wieder laufender Container schaltet ihn
wieder an. Domains manuell angelegter Hosts werden nicht übernommen.

## Notausgänge (nur auf dem Controller)

```bash
docker compose exec tesseract tesseract admin reset      # neues Zufallspasswort
docker compose exec tesseract tesseract admin mtls off   # Oberfläche ohne Admin-Zertifikat
docker compose exec tesseract tesseract admin password-login on   # Passwort wieder erlauben (SSO weg)
```

Mit `TESSERACT_ADMIN_PASSWORD` in der `.env` gilt beim nächsten Start wieder dieses Passwort.
