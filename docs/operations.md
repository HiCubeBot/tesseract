# Betrieb

## Aktualisieren (Upgrade-Pfad)

Tesseract folgt [Semantic Versioning](https://semver.org/lang/de/): Innerhalb einer
Hauptversion (1.x) sind Updates ohne Handarbeit möglich.

```bash
# 1. Vorher sichern (Oberfläche: Einstellungen › Backup › Jetzt sichern) oder:
docker compose exec tesseract tesseract backup create
# 2. Version in der .env anheben (TESSERACT_VERSION=1.1.0) oder „latest“ lassen
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
| Node-Zertifikat | gilt 2 Jahre | erneuert der Agent ab 60 Tage vorher selbst |
| Root-Zertifikat | gilt 10 Jahre | neue CA einrichten (Backlog: Import/Übergang) |

## Überwachen

- **Übersicht** zeigt Nodes, Abweichungen, Beitrittsanfragen.
- **Benachrichtigungen** melden u. a. Node offline, fehlgeschlagene Übertragung oder
  Sicherung, Abweichungen, Ablauf von Zertifikaten.
- **Prometheus:** `/metrics` (Einstellungen › Metriken), Grafana-Dashboard zum Herunterladen.
- **Loki (optional):** für lange Aufbewahrung der Zugriffs- und WAF-Logs, siehe unten.
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

## Notausgänge (nur auf dem Controller)

```bash
docker compose exec tesseract tesseract admin reset      # neues Zufallspasswort
docker compose exec tesseract tesseract admin mtls off   # Oberfläche ohne Admin-Zertifikat
```

Mit `TESSERACT_ADMIN_PASSWORD` in der `.env` gilt beim nächsten Start wieder dieses Passwort.
