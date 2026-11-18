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

## Zertifizierungsstelle

| Was | Wann | Wie |
|---|---|---|
| Gerät verlängern | Erinnerung 30 und 7 Tage vorher | **Geräte › Verlängern** – neue `.p12`, Freigaben bleiben |
| Zwischenzertifikat wechseln | Erinnerung 90/30/7 Tage vorher (gilt 3 Jahre) | **Einstellungen › Zertifizierungsstelle › Wechsel** mit Root-Schlüssel; alte Geräte funktionieren weiter, bis sie verlängert sind |
| Node-Zertifikat | gilt 2 Jahre | erneuert der Agent ab 60 Tage vorher selbst |
| Root-Zertifikat | gilt 10 Jahre | neue CA einrichten (Backlog: Import/Übergang) |

## Überwachen

- **Übersicht** zeigt Nodes, Abweichungen, Beitrittsanfragen.
- **Benachrichtigungen** melden u. a. Node offline, fehlgeschlagene Übertragung oder
  Sicherung, Abweichungen, Ablauf von Zertifikaten.
- **Prometheus:** `/metrics` (Einstellungen › Metriken), Grafana-Dashboard zum Herunterladen.
- **Audit-Log:** Prüfung der Prüfsummenkette oben auf der Seite.

## Notausgänge (nur auf dem Controller)

```bash
docker compose exec tesseract tesseract admin reset      # neues Zufallspasswort
docker compose exec tesseract tesseract admin mtls off   # Oberfläche ohne Admin-Zertifikat
```

Mit `TESSERACT_ADMIN_PASSWORD` in der `.env` gilt beim nächsten Start wieder dieses Passwort.
