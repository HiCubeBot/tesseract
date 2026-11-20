# Changelog

Alle wichtigen Änderungen. Format nach [Keep a Changelog](https://keepachangelog.com/de/),
Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Upgrade-Hinweise:
[docs/operations.md](docs/operations.md#aktualisieren-upgrade-pfad).

## [1.9.0] – 2026-11-21

### Hinzugefügt
- **DNS-Eintrag automatisch bei Cloudflare:** Beim Anlegen oder Bearbeiten eines Hosts wählbar.
  Pro Domain (Einstellungen › Integrationen › DNS-Einträge) der Standard: CNAME auf einen Namen
  (z. B. den DDNS-Namen) oder A/AAAA auf die öffentlichen IPs des Nodes bzw. eigene IPs,
  optional über den Cloudflare-Proxy; pro Host änderbar. Der Eintrag wird vor dem Übertragen an
  Caddy angelegt, mit dem Host geändert und gelöscht. Fremde Einträge bleiben unangetastet,
  Fehler stehen beim Host. Die Vorab-Prüfung zeigt, was angelegt wird
- Migration 0021 (DNS-Felder am Host)

## [1.8.1] – 2026-11-20

### Behoben
- Übersicht › Letzte Ereignisse: Bei älteren Einträgen lief das Datum in den Titel. Jetzt
  kurz „19.11. 22:52“ (Jahr nur, wenn es nicht das aktuelle ist) in einer breiteren Spalte

## [1.8.0] – 2026-11-20

### Hinzugefügt
- **GeoIP-Datenbank automatisch:** Mit `TESSERACT_GEOIP_AUTO=dbip` holt der Controller
  „IP to Country Lite“ von DB-IP (ohne Konto), prüft die Datei, erneuert sie monatlich und
  übernimmt sie ohne Neustart. Stand und „Jetzt aktualisieren“ unter Einstellungen › Metriken,
  Quellenangabe unter der Karte. Standardmäßig aus (einzige Verbindung nach außen). Sperrt ein
  DNS-Filter wie Pi-hole oder AdGuard die Domain, sagt die Fehlermeldung das

## [1.7.0] – 2026-11-20

### Hinzugefügt
- **Oberfläche nur aus bestimmten Netzen:** `TESSERACT_ADMIN_NETWORKS` in der `.env`
  (kommagetrennt, Standard `0.0.0.0/0,::/0` = alle Netze). Aus anderen Netzen bricht Caddy die
  Verbindung ohne Antwort ab – auch die HTTP-Umleitung. Einladungen, Gerät verlängern, die
  Agent-Schnittstelle, `/metrics` und `/install` bleiben überall erreichbar. Geprüft wird die
  echte Verbindungs-IP. Anzeige unter Einstellungen › Allgemein › Zugang zur Oberfläche

## [1.6.0] – 2026-11-20

### Hinzugefügt
- **Hosts aus Docker-Labels:** Container mit `tesseract.domain` werden zu Proxy-Hosts (Port,
  Ziel, Zugriff, interne Netze, Freigaben, WAF, Prüfart per Label). Lokal liest der Controller
  über `TESSERACT_DOCKER_HOST` (Socket-Proxy im Compose-Profil `docker`), Agents melden ihre
  Container mit `TESSERACT_AGENT_DOCKER_HOST`. Neue Hosts sind Entwürfe, Freigaben nur an
  vorhandene Gruppen/Personen, gestoppte Container schalten ihren Host ab. Einstellungen ›
  Integrationen › Docker-Labels
- **Log-Ansicht und Statistik aus Loki oder VictoriaLogs:** auf Wunsch (Einstellungen ›
  Metriken bzw. `TESSERACT_LOGS_EXTERNAL`) statt aus SQLite – so weit zurück, wie der
  Log-Speicher aufbewahrt
- **Restic als Backup-Ziel:** Repository (REST, S3, B2, SFTP, Verzeichnis) mit Passwort und
  optionalen Zugangsdaten; Repository wird bei Bedarf angelegt, Aufräumen per
  `restic forget --prune`. restic ist im Controller-Image enthalten

### Upgrade
- Migration 0020 (Herkunft der Hosts). `compose.yaml` übernehmen, wer den Socket-Proxy nutzen
  will (Profil `docker`)

## [1.5.0] – 2026-11-19

### Hinzugefügt
- **Heller Modus:** folgt der Systemeinstellung, Umschalter in der Seitenleiste
  (System → Hell → Dunkel), pro Browser gemerkt
- **Favicon** für Browser-Tab und Lesezeichen
- **Hosts in der Liste ein- und ausschalten:** Schalter direkt in der Zeile, neuer Filter
  „Deaktiviert“, deaktivierte Hosts gedimmt

### Geändert
- **Host bearbeiten ist eine eigene Seite** statt der schmalen Seitenleiste neben der Liste:
  Tabs Allgemein · Zugriff · Sicherheit · Verlauf, Aktiv-Schalter im Kopf, Vorab-Prüfungen
  wie beim Anlegen, Speichern-Leiste bleibt beim Scrollen sichtbar. Bei ungespeicherten
  Änderungen fragt ein Tab-Wechsel nach

## [1.4.2] – 2026-11-19

### Hinzugefügt
- **Cloudflare-Token über die `.env`** (`TESSERACT_CLOUDFLARE_TOKEN` oder `…_FILE`): gilt bei
  jedem Start und ist in der Oberfläche gesperrt
- **Zertifikat der Oberfläche per DNS-01:** Ist ein Cloudflare-Token hinterlegt, holt sich auch
  die Oberfläche ihr Zertifikat per DNS – ohne Portweiterleitung und ohne öffentlichen
  DNS-Eintrag (z. B. `tesseract.home.beispiel.de` nur im lokalen DNS). Liegt sie unter einem
  geteilten Wildcard-Zertifikat, nutzt sie dieses
- Caddy nutzt den Token schon beim allerersten Start (`Caddyfile.cloudflare`), bevor der
  Controller seine Config überträgt

### Upgrade
- Der Caddy-Container startet jetzt mit `command: tesseract-caddy` und bekommt
  `TESSERACT_CLOUDFLARE_TOKEN` durchgereicht – `compose.yaml` übernehmen. Mit der alten
  `compose.yaml` läuft alles weiter, nur der allererste Start nutzt dann kein DNS-01

## [1.4.1] – 2026-11-19

### Behoben
- **Öffentliche IPs pro Node:** Bisher gab es nur eine Liste für alle Nodes, die DNS-Prüfung
  bei „Host anlegen“ verglich deshalb auch Hosts auf anderen Nodes mit der IP des Controllers.
  Die IPs stehen jetzt am Node (Nodes › Bearbeiten), die Prüfung nimmt die des gewählten Nodes.
  Eine bisher eingetragene Liste übernimmt der lokale Node (Migration 0019)
- Nodes lassen sich in der Oberfläche bearbeiten (Name, Standort, öffentliche IPs)

## [1.4.0] – 2026-11-19

### Neu
- **Bestehende CA importieren:** Root-Zertifikat mit Root-Schlüssel (Tesseract erzeugt das
  Zwischenzertifikat und vergisst den Root-Schlüssel) oder mit fertigem Zwischenzertifikat samt
  Schlüssel. ECDSA oder RSA (ab 2048 Bit)
- **Wechsel der Root-CA:** neu erzeugt oder importiert. Das alte Zwischenzertifikat bleibt
  vertraut, solange Geräte oder Nodes daran hängen; Agents erneuern ihr Zertifikat danach von
  selbst (`renew_cert` in der Antwort auf den Status)
- **VictoriaLogs** als Log-Speicher neben Loki (`TESSERACT_LOKI_KIND=victorialogs`,
  Compose-Profil `victorialogs`)
- **Node ohne Controller:** Der Agent hebt die zuletzt geladene Config auf und lädt sie wieder,
  wenn Caddy nach einem Neustart ohne Config hochkommt – auch ohne Controller

### Behoben
- Nach einem Wechsel des Zwischenzertifikats blieb das alte nur vertraut, solange Geräte
  daran hingen – Nodes zählten nicht mit und konnten den Kontakt zum Controller verlieren

## [1.3.1] – 2026-11-19

### Neu
- **Dauerhafte IP-Sperre:** Gesperrte IPs lassen sich jetzt auch „für immer“ sperren (bis zum
  Entsperren von Hand); zusätzlich 90 Tage und 1 Jahr als Dauer. Datenbank-Migration 0018

## [1.3.0] – 2026-11-19

### Neu
- **SSO für die Admin-Oberfläche** über OpenID Connect (Authelia, Keycloak, Authentik, Dex …):
  Authorization Code mit PKCE, ID-Token per JWKS geprüft, Admin über Gruppe oder E-Mail.
  Das Admin-Gerätezertifikat bleibt die erste Hürde. Getestet mit Dex und Gruppen aus LDAP
- **Passkeys (WebAuthn)** für Admins – Anmeldung ohne Passwort; mehrere pro Konto
- **Passwort-Anmeldung abschaltbar**, sobald SSO oder ein Passkey eingerichtet ist;
  Notausgang `tesseract admin password-login on`
- **LDAP-Abgleich** für Personen und Gruppen (OpenLDAP, Active Directory, FreeIPA …):
  regelmäßig oder von Hand, mit Vorschau; Deaktivierte oder Entfernte werden gesperrt samt
  Geräten; Schutz vor Fehlkonfiguration. Getestet gegen OpenLDAP
- Anleitung: [docs/anmeldung.md](docs/anmeldung.md)

### Upgrade
- Datenbank-Migration läuft automatisch. Neue Abhängigkeiten: `webauthn`, `ldap3`, `pyjwt`.

## [1.2.0] – 2026-11-19

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

### Upgrade
- Controller aktualisieren. Die Config wird beim Start neu übertragen (öffentliche Pfade `/v`
  und `/api/renew` für das Selbst-Verlängern). Agents brauchen kein Update.
- Loki ist optional: `docker compose --profile loki up -d` und `TESSERACT_LOKI_URL` setzen.

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
