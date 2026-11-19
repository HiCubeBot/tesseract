# Changelog

Alle wichtigen Änderungen. Format nach [Keep a Changelog](https://keepachangelog.com/de/),
Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Upgrade-Hinweise:
[docs/operations.md](docs/operations.md#aktualisieren-upgrade-pfad).

## [Unveröffentlicht]

### Neu
- **Loki als zusätzlicher Log-Speicher**: Zugriffs- und WAF-Logs aller Nodes gehen auch an
  Loki (Einstellungen › Metriken, Verbindungstest, Puffer bei Ausfall). Loki optional im
  Compose-Stack: `docker compose --profile loki up -d`, `TESSERACT_LOKI_URL=http://loki:3100`
- **Git-Spiegel der Configs** (Einstellungen › Backup): Hosts, Caddy-Configs, IP-Listen und
  Einstellungen lesbar in einem Git-Repository, jede Änderung ein Commit. Anmeldung per Token
  oder SSH-Deploy-Key; ohne Geheimnisse und Personen. Das Image enthält dafür `git` und `ssh`
- **Gäste verlängern ihr Gerät selbst** über `https://<controller>/v` – auf dem Gerät öffnen,
  das noch gültige Zertifikat ist der Ausweis. Ab 30 Tagen vor Ablauf (einstellbar), nach
  einem CA-Wechsel sofort. Abschaltbar unter Einstellungen › Zertifizierungsstelle; der Link
  steht nach der Registrierung auf der Einladungsseite

## [1.1.0] – 2026-11-18

### Neu
- **Nodes per Einzeiler installieren**: `curl -fsSL https://<controller>/install/node.sh | sudo sh
  -s -- --token …` richtet Caddy und Agent ein, zeigt den Fingerabdruck; `--update`,
  `--uninstall`, `--install-docker`, `--registry-token`; bei interner Domain mit
  Prüfsumme und mitgelieferter CA; nutzt vorab eingespielte Images, wenn die Registry fehlt
- **https zum Ziel ohne Zertifikatsprüfung** pro Host – für selbst signierte Zertifikate
  (Proxmox, Unifi, NAS-Oberflächen)
- **Fehlende Caddy-Module** werden beim Speichern erkannt: Ein Host mit WAF oder DNS-01 auf
  einem Node ohne das Modul wird mit verständlicher Meldung abgelehnt, statt dass Caddy später
  die ganze Config verwirft
- **Erreichbarkeit des Ziels vom Node aus**: Bei Agent-Nodes prüft der Agent selbst
  (Agent ≥ 1.1), nicht mehr der Controller
- **Zertifikatsübersicht für alle Nodes**: Agents lesen die Zertifikate ihres Caddy aus
- Aufgaben für Agents über das bestehende Long-Polling (keine eingehende Verbindung nötig)

### Behoben
- Lokal gebaute Images enthielten eine vorhandene `backend/.env` (Entwicklungswerte, z. B.
  ohne Hintergrundaufgaben). Die über GitHub veröffentlichten Images waren nicht betroffen.
  Wer selbst baut: `docker compose up -d --build`
- Nach dem Einrichten der CA fragte Caddy erst nach der nächsten Änderung nach
  Client-Zertifikaten – Agents und Admin-Geräte wurden bis dahin nicht erkannt
- Die Zertifikatsübersicht fragte bei Agent-Nodes den Controller-Rechner statt des Nodes ab

### Upgrade
- Controller und Agents aktualisieren; ältere Agents funktionieren weiter, nur die Prüfung vom
  Node und die Zertifikate des Nodes brauchen Agent 1.1.

## [1.0.0] – 2026-11-18

Erste stabile Version (Phase 0–6 der [Roadmap](docs/roadmap.md)).

### Proxy & Zertifikate
- Proxy-Hosts mit Assistent, Vorab-Prüfungen, Versionierung mit Diff und Zurücksetzen
- Let's Encrypt per HTTP-01 und DNS-01 (Cloudflare), geteilte Wildcard-Zertifikate,
  eigene Zertifikate, Zertifikatsübersicht

### Zugriff
- Eigene CA, ein Client-Zertifikat pro Gerät, mTLS statt VPN, Zugriff pro Pfad und Bereich
- Personen, Gruppen, Zugriffsmatrix, Einladungen mit Bestätigungscode und Admin-Freigabe
- Zugriffsart „Nur aus internen Netzen“, Oberfläche nur mit Admin-Zertifikat
- CA-Wechsel mit Übergang, Geräte verlängern, Ablauf-Erinnerungen

### Sicherheit
- Coraza WAF (OWASP CRS) pro Host und Bereich, IP-Filter, IP-Listen, Auto-Sperre,
  Authelia als Middleware
- Rate-Limits, Sicherheits-Header, strenge CSP, gehärtete Container, keine externen Abrufe
  der Oberfläche

### Multi-Node
- Agent für weitere Nodes: Beitritt per Token, ausgehendes mTLS (auch hinter NAT),
  Config-Verteilung, Abweichungen überschreiben/übernehmen, Modul-Erkennung,
  automatische Erneuerung des Node-Zertifikats

### Beobachtbarkeit
- Zentrale Logs aller Nodes mit Suche und Aktionen, Statistik mit Herkunftskarte,
  unveränderliches Audit-Log mit Prüfsummenkette, Prometheus-Metriken, Grafana-Dashboard,
  Benachrichtigungen per ntfy, E-Mail, Webhook

### Betrieb
- Verschlüsselte Sicherungen (lokal, S3) mit Zeitplan, Test und Wiederherstellen
- Einstellungen und Admin-Passwort über die `.env`
- Veröffentlichte Images für amd64 und arm64
