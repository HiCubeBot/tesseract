# Roadmap

Das Projekt wird in Phasen umgesetzt. Jede Phase endet mit einem lauffähigen Stand, der
für sich nutzbar ist. Details zu den einzelnen Features: [features.md](features.md).

| Phase | Name | Ergebnis |
|---|---|---|
| 0 | Fundament | Projektstruktur, Docker, Doku – **fertig** |
| 1 | Proxy-Manager (Single-Node) | Ersetzt NPM für einen lokalen Caddy – **fertig** |
| 2 | mTLS & Identitäten | Private Dienste ohne VPN, Einladungen – **fertig** |
| 3 | WAF & Zugriffsschutz | Coraza, IP-Filter, Authelia – **fertig** |
| 3b | Interne Dienste & Zertifikate | Zugriffsart „Intern“, Wildcard-Zertifikate, Zertifikatsübersicht – **fertig** |
| 4 | Multi-Node | Agent, mehrere Server, auch hinter NAT – **fertig** |
| 5 | Beobachtbarkeit | Logs, Statistik, Audit, Metriken, Benachrichtigungen – **fertig** |
| 6 | Betrieb & Release | Backup, CA-Rotation, Härtung, v1.0 – **fertig** |
| 1.1 | Lücken geschlossen | Selbst signierte Ziele, Modul-Prüfung, Aufgaben für Agents – **fertig** |
| 1.2 | Aus dem Backlog | Loki, Git-Spiegel, Gäste verlängern selbst – **fertig** |
| 1.3 | Anmeldung & Verzeichnis | SSO (OIDC) und Passkeys für Admins, LDAP-Abgleich – **fertig** |
| 1.4 | CA, Logs, Ausfallsicherheit | CA-Import und Root-Wechsel, VictoriaLogs, Node ohne Controller – **fertig** |
| 1.5 | Oberfläche | Heller Modus, Favicon, Host-Seite mit Tabs, Hosts direkt in der Liste abschalten – **fertig** |
| 1.6 | Betrieb | Docker-Labels, Logs und Statistik aus Loki/VictoriaLogs, Restic als Backup-Ziel – **fertig** |
| 1.7 | Zugang | Oberfläche nur aus bestimmten Netzen (`TESSERACT_ADMIN_NETWORKS`) – **fertig** |
| 1.8 | GeoIP automatisch | Länder-Datenbank selbst holen und monatlich erneuern (`TESSERACT_GEOIP_AUTO`) – **fertig** |
| 1.9 | DNS-Einträge | DNS-Eintrag beim Anlegen eines Hosts automatisch bei Cloudflare – CNAME oder A/AAAA, pro Domain einstellbar – **fertig** |
| 1.10 | Nodes über DNS | Node-Schnittstelle wahlweise von den Admin-Netzen ausgenommen, DNS-Eintrag für die Tesseract-Domain – **fertig** |
| 1.11 | Herkunftskarte | Karte zeigt alle Anfragen, Filter Abgelehnt / Angenommen – **fertig** |
| 1.12 | Intern ohne Zertifikat | mTLS-Hosts wahlweise aus den internen Netzen ohne Zertifikat – **fertig** |
| 1.21 | Controller-Zertifikat | Tesseract selbst darf auf mTLS-Hosts zugreifen (z. B. ntfy) – **fertig** |
| 1.20 | Statusseite einschaltbar | Öffentliche Statusseite nur, wenn in den Einstellungen eingeschaltet (Standard aus) – **fertig** |
| 1.19 | Länder anklickbar | Karte: Land anklicken für Details, Städte und Netzbetreiber – **fertig** |
| 1.13–1.18 | [Oberfläche, Statistik, Status Page](#oberfläche-statistik-status-page-fertig) | Kein-Zugang-Seite, Seitenleiste, Nodes, Host-Statistik, Statistik mit Karte, Uptime-Monitor, Übersicht – **fertig** |
| – | [Offen / bekannte Grenzen](#offen--bekannte-grenzen) | Einschränkungen des aktuellen Stands |
| – | [Backlog](#backlog-niedrige-priorität) | Niedrige Priorität, ohne festen Zeitpunkt |

---

## Oberfläche, Statistik, Status Page (fertig)

- [x] Kein-Zugang-Seite überarbeitet: Grund als Kennzeichen, Hinweis zur Einladung, Dienst,
  IP, Zeit, Verarbeitungszeit und Anfrage-ID (1.13)
- [x] README auf Englisch, Repo-Beschreibung (1.13)
- [x] Sidebar mit Zahlen (Hosts, Personen, Geräte, Nodes) (1.14)
- [x] Node-Übersicht als Karten: Caddy-Version, Hosts (davon öffentlich), letzter Kontakt,
  Config-Stand, Verbindung zum Controller (1.14)
- [x] Proxy-Hosts: Anfragen der letzten 24 h mit Verlaufslinie je Host; eigener Tab
  „Statistik“ pro Host (Anfragen, Besucher, Daten, Antwortzeit, Fehler, Kompression,
  Pfade, Herkunft, Abgelehnt, Top abgelehnte IPs) (1.15)
- [x] Statistik überarbeitet: Kennzahlen mit Verlauf und Vergleich zum Vorzeitraum,
  gesamter Zeitraum, Statuscodes, Protokolle, Clients (Browser/Apps/Bots), Pfade mit
  Fehlern, Netzbetreiber (ASN), Städte; eigener Tab mit zoombarer Karte (1.16)
- [x] Status Page: Erreichbarkeit der Dienste prüfen (Uptime Monitor), öffentliche Statusseite;
  Statistik › Betrieb mit Erreichbarkeit der Nodes und Hosts, Zertifikaten und Rekorden (1.17)
- [x] Übersicht überarbeitet (1.18)

## Version 1.12 – Intern ohne Zertifikat (fertig)

- [x] Pro Host mit „Nur mit Zertifikat“: aus den internen Netzen ohne Zertifikat erreichbar,
  von außen weiter nur mit

## Version 1.11 – Herkunftskarte (fertig)

- [x] Karte unter Statistik › Sicherheit zeigt die Herkunft aller Anfragen; Filter „Abgelehnt“
  und „Angenommen“, auch mit Loki/VictoriaLogs

## Version 1.10 – Nodes über DNS (fertig)

- [x] `TESSERACT_AGENT_API_PUBLIC` – Node-Schnittstelle von `TESSERACT_ADMIN_NETWORKS`
  ausnehmen (Standard) oder mit einschränken
- [x] DNS-Eintrag für die Tesseract-Domain bei Cloudflare, damit Nodes den Controller finden;
  A/AAAA-Einträge folgen neuen öffentlichen IPs eines Nodes

## Version 1.9 – DNS-Einträge (fertig)

- [x] DNS-Eintrag beim Anlegen eines Hosts automatisch bei Cloudflare anlegen, mit dem Host
  ändern und löschen; pro Domain Standard CNAME (auf einen Namen) oder A/AAAA (IPs des Nodes
  oder eigene), pro Host änderbar, optional über den Cloudflare-Proxy
- [x] Vorab-Prüfung zeigt den geplanten Eintrag; fremde Einträge bleiben unangetastet

## Version 1.8 – GeoIP automatisch (fertig)

- [x] `TESSERACT_GEOIP_AUTO=dbip`: DB-IP Lite selbst holen, prüfen, monatlich erneuern und ohne
  Neustart übernehmen; Hinweis, wenn ein DNS-Filter die Domain sperrt

## Version 1.7 – Zugang (fertig)

- [x] Oberfläche nur aus bestimmten Netzen – `TESSERACT_ADMIN_NETWORKS` in der `.env`
  (Standard `0.0.0.0/0,::/0`); Caddy bricht Verbindungen aus anderen Netzen ab, die
  öffentlichen Pfade für Gäste und Agents bleiben erreichbar

## Version 1.6 – Betrieb (fertig)

- [x] Docker-Labels – Hosts aus Container-Labels (`tesseract.domain`, `tesseract.port` …);
  lokal über einen Socket-Proxy (Compose-Profil `docker`), Agent-Nodes melden ihre Container
  im Status. Neue Hosts als Entwurf, Freigaben nur an vorhandene Gruppen/Personen, gestoppte
  Container schalten ihren Host ab ([HiCubeBot/tesseract#14](https://github.com/HiCubeBot/tesseract/issues/14))
- [x] Log-Ansicht und Statistik direkt aus Loki oder VictoriaLogs (Einstellung bzw.
  `TESSERACT_LOGS_EXTERNAL`) – gleiche Suche, gleiche Kennzahlen wie aus SQLite
- [x] Restic als Backup-Ziel (lokal, SFTP, S3, B2, REST-Server …), Aufräumen mit
  `restic forget --prune`, restic im Controller-Image

## Version 1.5 – Oberfläche (fertig)

- [x] Heller Modus – folgt der Systemeinstellung, umschaltbar in der Seitenleiste
  (System → Hell → Dunkel), pro Browser gemerkt
- [x] Favicon
- [x] Hosts direkt in der Liste ein- und ausschalten; Filter „Deaktiviert“, deaktivierte Zeilen
  gedimmt
- [x] Host bearbeiten als eigene Seite statt Seitenleiste – Tabs Allgemein · Zugriff ·
  Sicherheit · Verlauf, Aktiv-Schalter im Kopf, Speichern-Leiste bleibt sichtbar

## Version 1.4 – CA, Logs, Ausfallsicherheit (fertig)

- [x] Bestehende CA importieren – Root mit Schlüssel oder fertiges Zwischenzertifikat (ECDSA
  oder RSA); Root-Schlüssel wird nie gespeichert
- [x] Wechsel der Root-CA – neu erzeugt oder importiert; altes Zwischenzertifikat bleibt
  vertraut, bis Geräte verlängert und Nodes erneuert sind; Agents erneuern ihr Zertifikat
  nach dem Wechsel von selbst
- [x] VictoriaLogs als Log-Speicher neben Loki (JSON-Lines-Schnittstelle, Compose-Profil
  `victorialogs`)
- [x] Node ohne Controller: Startet Caddy ohne Config, lädt der Agent den zuletzt bekannten
  Stand aus seinem Datenverzeichnis

## Version 1.3 – Anmeldung & Verzeichnis (fertig)

- [x] SSO für die Admin-Oberfläche über OpenID Connect (Authelia, Keycloak, Authentik, Dex …),
  Admin über Gruppe oder E-Mail; Admin-Gerätezertifikat bleibt erste Hürde
- [x] Passkeys (WebAuthn) für Admins – zusätzlich oder statt Passwort; Passwort-Anmeldung
  abschaltbar, Notausgang `tesseract admin password-login on`
- [x] LDAP-Abgleich für Personen und Gruppen, Sperre samt Geräten bei Deaktivierung, Vorschau,
  Schutz vor Fehlkonfiguration
- Anleitung: [anmeldung.md](anmeldung.md)

## Version 1.2 – aus dem Backlog (fertig)

- [x] Loki als zusätzlicher Log-Speicher, optional im Compose-Stack (Profil `loki`)
- [x] Git-Spiegel der Configs als Backup-Ziel
- [x] Gäste verlängern ihr Gerät selbst über einen Link (abschaltbar)

## Offen / bekannte Grenzen

Was im aktuellen Stand fehlt oder bewusst eingeschränkt ist.

- **DNS-01 nicht mit echter Zone getestet** – der Zertifikatsabruf per DNS-01 (Cloudflare) ist
  bisher nur über die Format-Prüfung der Caddy-Config getestet.
- **Caddy-Version im Docker-Betrieb** – sie wird nur angezeigt, wenn der Agent das
  `caddy`-Programm aufrufen kann. Läuft der Agent im eigenen Container, steht dort „–“
  (Caddys Admin-API liefert keine Version).
- **„Änderung übernehmen“ bei Abweichungen** – die lokale Änderung auf dem Node wird nicht in
  die Hosts des Controllers übernommen und gilt nur bis zur nächsten Übertragung.
- **Abgelehnte TLS-Handshakes** (strenges mTLS) stehen nicht im Zugriffs-Log – Caddy schreibt
  dafür keine Anfrage. Sichtbar sind nur die 403 der Hinweisseite und der Pfad-Regeln.
- **Anomalie-Score** – Coraza schreibt ihn bei OWASP CRS 4 nicht ins Log; er wird nur gezeigt,
  wenn vorhanden.

## Backlog (niedrige Priorität)

Gewünscht, aber ohne festen Platz in einer Phase. Wird bei Bedarf eingeplant.

**Zertifikate & CA**

- **Weitere DNS-Anbieter** für DNS-01 neben Cloudflare.

---

## Erledigte Phasen

### Phase 0 – Fundament

**Ziel:** Saubere Basis, auf der alle weiteren Phasen aufbauen.

- [x] Design-Prototyp als Svelte-5-Code (`frontend/`)
- [x] Backend-Gerüst mit uv + FastAPI (`backend/`), Health-Endpunkt, Tests
- [x] Dockerfile (Frontend + Backend in einem Image), Caddy-Image mit Coraza, `compose.yaml`
- [x] Dokumentation in `docs/`, Featureliste, Roadmap
- [x] Git-Repository, CI (Lint, Tests, `svelte-check`, Image-Build)
- [x] Architekturentscheidungen ([architecture.md](architecture.md#entscheidungen))

**Fertig, wenn:** `docker compose up` startet Controller + Caddy, UI und `/api/health` sind erreichbar.

### Phase 1 – Proxy-Manager (Single-Node)

**Ziel:** Funktionsgleich mit den Kernfunktionen von NPM – für einen Caddy im selben Compose-Stack.

- [x] Datenbank (SQLite) mit Migrationen, Datenmodell für Hosts und Config-Versionen
- [x] Admin-Login (Passwort, Sitzung 12 h / 30 Tage), `tesseract admin reset` auf der Kommandozeile
- [x] Proxy-Hosts anlegen/bearbeiten/löschen über den 3-Schritte-Assistenten, Entwürfe
- [x] Optionen: HTTP→HTTPS, WebSockets, Kompression; TLS über Let's Encrypt (HTTP-01)
- [x] Vorab-Prüfungen (Domain frei, DNS, Erreichbarkeit des Ziels)
- [x] Caddy-JSON-Config erzeugen und über die Admin-API übertragen, Sync-Status pro Node
- [x] Versionierung jeder Änderung, Diff-Ansicht, Zurücksetzen
- [x] Basis-Audit-Log (wer hat was geändert)
- [x] Frontend: Übersicht, Hosts, Host anlegen, Verlauf, Einstellungen/Allgemein, Audit-Log an die API angebunden

**Fertig, wenn:** Ein öffentlicher Host mit gültigem Let's-Encrypt-Zertifikat lässt sich komplett
über das UI anlegen, ändern und auf eine alte Version zurücksetzen.

### Phase 2 – mTLS & Identitäten

**Ziel:** Private Dienste nur für freigegebene Geräte – die VPN-Alternative.

- [x] Eigene CA: Root-Schlüssel nur einmal verschlüsselt ausgeliefert (offline), Geräte-Zwischenzertifikat verschlüsselt auf dem Controller
- [x] Personen, Gruppen, Geräte; ein Client-Zertifikat pro Gerät, Geräte-Limit pro Person
- [x] Zugriffsart pro Host (Öffentlich / mTLS) und Verhalten ohne Zertifikat (ablehnen / Hinweisseite)
- [x] Freigaben an Gruppen und Personen, Zugriffsmatrix
- [x] Zugriff pro Pfad in beide Richtungen, z. B. API öffentlich, `/admin` nur per mTLS
- [x] Sperren von Geräten (sofort aus allen Freigabelisten), Export gesperrter Geräte
- [x] Einladungsfluss: Link + QR + separater Bestätigungscode, Admin-Freigabe, Installationsanleitungen je Plattform
- [x] Admin-UI nur mit Admin-Gerätezertifikat (+ Passwort), Notausgang `tesseract admin mtls off`

**Fertig, wenn:** Ein eingeladener Gast registriert ein iPhone und einen Laptop, erreicht genau die
freigegebenen Dienste, und nach dem Sperren eines Geräts schlägt dessen TLS-Handshake fehl.
Bei einem Host mit öffentlicher `/api/*` und geschütztem `/admin/*` antwortet die API ohne
Zertifikat, `/admin/*` nur mit.

### Phase 3 – WAF & Zugriffsschutz

**Ziel:** Öffentliche Dienste absichern.

- [x] Coraza WAF pro Host (Aus / Protokollieren / Blockieren), OWASP CRS, Paranoia-Level, Standards für neue Hosts, WAF für die Oberfläche
- [x] Regel-Ausnahmen pro Host und pro Bereich
- [x] IP-Filter (Sperren / Nur erlauben), benannte IP-Listen (Vorlage Cloudflare)
- [x] Auto-Sperre nach WAF-Treffern, Sperren von Hand, automatischer Ablauf
- [x] Authelia-Integration (Forward-Auth) als Host-Middleware, weitergereichte Header
- [x] Vertrauenswürdige Proxys für die korrekte Client-IP
- [x] DNS-01-Challenge (Cloudflare) für Wildcards und Hosts ohne Port 80
- [x] Host-Bereiche: Pfade mit eigenen Regeln für Zugriff/Freigaben, WAF, IP-Filter, Authelia

**Fertig, wenn:** Ein SQL-Injection-Versuch wird blockiert, protokolliert und führt nach Schwellwert
zur automatischen IP-Sperre.

### Phase 3b – Interne Dienste & Zertifikate

**Ziel:** Der Proxy als zentrale Stelle auch für rein interne Dienste (Grafana im Homelab
& Co.) – mit allen Zertifikaten im Blick.

- [x] Zugriffsart **„Nur aus internen Netzen“**: zentral festgelegte Netze (LAN, VPN), echte
  Verbindungs-IP, Abbruch ohne Antwort für alle anderen, kombinierbar mit mTLS; interne Namen
  (`.lan`, `.home.arpa` …) bekommen ein Zertifikat aus Caddys eigener CA
- [x] **Geteilte Wildcard-Zertifikate** per DNS-01 für alle passenden Hosts
- [x] **Zertifikatsübersicht** wie bei NPM (direkt bei Caddy ausgelesen), bald ablaufende in der Übersicht
- [x] **Eigene Zertifikate** hochladen, Hosts zuordnen, erneuern
- [x] Doku: Split-DNS, NAT-Loopback, Docker und echte Client-IP

**Fertig, wenn:** `grafana.home.beispiel.de` ist im LAN und per VPN erreichbar, von außen
bricht die Verbindung ab, das Zertifikat ist das gemeinsame Wildcard-Zertifikat, und die
Zertifikatsübersicht zeigt es mit Laufzeit und allen Hosts, die es nutzen.

### Phase 4 – Multi-Node

**Ziel:** Beliebig viele Caddy-Server zentral verwalten.

- [x] Tesseract-Agent (Python, eigenes Paket/Image unter `agent/`) neben Caddy auf jedem Node
- [x] Beitritt per einmaligem Token (30 Min.), Agent erzeugt Schlüssel, Bestätigung im Controller
  nach Vergleich des Schlüssel-Fingerabdrucks
- [x] Ausgehende mTLS-Verbindung Agent → Controller (Long-Polling über HTTPS, funktioniert
  hinter NAT, kein offener Admin-Port); zusätzlich Agent-Token
- [x] Config-Verteilung pro Node, Erkennung von Abweichungen (auch beim lokalen Node),
  Überschreiben oder Übernehmen, Unterschiede pro Host
- [x] Modul-Erkennung pro Node (Coraza, DNS Cloudflare) über Caddys `/adapt`
- [x] Status, letzter Kontakt, offline nach 90 s; WAF-Treffer werden gepuffert und nachgeliefert
  und zählen für die Auto-Sperre
- [x] Interne Controller-Domain (z. B. `tesseract.lan`) bekommt ein Zertifikat aus Caddys CA

**Fertig, wenn:** Ein Raspberry Pi hinter NAT tritt bei, bekommt Hosts zugewiesen, und eine
lokale Änderung auf dem Pi wird im UI als Abweichung angezeigt.

### Phase 5 – Beobachtbarkeit

**Ziel:** Sehen, was passiert.

- [x] Zentrale Log-Sammlung von allen Nodes (Zugriffs- und WAF-Logs, Agent puffert und liefert
  nach), Live-Ansicht, Such-Syntax, Grund jeder Ablehnung, WAF-Regel pro Anfrage, Gerät
- [x] Statistik: Sicherheit (mit Herkunftskarte), Traffic & Leistung, Nutzung; lokale
  GeoIP-Datenbank (optional)
- [x] Aktionen aus Logs (IP sperren, Ausnahme anlegen, alle Einträge einer IP)
- [x] Unveränderliches Audit-Log mit verketteten Prüfsummen, Prüfung, Filter, CSV-Export
- [x] Prometheus-Endpunkt inkl. Node- und Caddy-Metriken, Grafana-Dashboard
- [x] Benachrichtigungen per E-Mail, Webhook, ntfy mit Bündelung und Ruhezeiten

**Fertig, wenn:** Ein blockierter Angriff erscheint live in den Logs, in der Statistik und als
ntfy-Meldung.

### Phase 6 – Betrieb & Release

**Ziel:** Stabil genug für den Dauerbetrieb – Version 1.0.

- [x] Verschlüsselte Backups (Zeitplan, Ziele lokal und S3), Wiederherstellungstest,
  Wiederherstellen mit automatischer Neuverteilung an Nodes, `tesseract backup create|restore`
- [x] Wechsel des Zwischenzertifikats mit Übergang, Geräte verlängern, Node-Zertifikate
  erneuern sich selbst, Ablauf-Erinnerungen (Geräte, CA, Nodes, eigene Zertifikate)
- [x] Sicherheits-Review ([security.md](security.md)), Härtung der Images und Container,
  Rate-Limits auf öffentlichen Endpunkten, Sicherheits-Header/CSP, echte Client-IP hinter Caddy
- [x] Installations- und Betriebsanleitung ([installation.md](installation.md),
  [operations.md](operations.md)), Upgrade-Pfad, CI, veröffentlichte Images (amd64/arm64)
  über GitHub Actions bei einem Versions-Tag, [CHANGELOG](../CHANGELOG.md)

### Version 1.1 – Lücken geschlossen

- [x] https zum Ziel ohne Zertifikatsprüfung (selbst signierte Ziele)
- [x] Hosts mit WAF/DNS-01 auf Nodes ohne das Caddy-Modul werden beim Speichern abgelehnt
- [x] Aufgaben für Agents über das Long-Polling: Erreichbarkeit des Ziels vom Node aus,
  Zertifikate des Nodes für die Übersicht
- [x] Nodes per Einzeiler installieren (`/install/node.sh`), auch mit interner Domain und ohne
  Internet
- [x] Behoben: lokale `.env` im Image, Caddy fragte nach dem Einrichten der CA nicht sofort
  nach Client-Zertifikaten, Zertifikatsübersicht bei Agent-Nodes
