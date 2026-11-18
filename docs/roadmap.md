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
| 4 | Multi-Node | Agent, mehrere Server, auch hinter NAT |
| 5 | Beobachtbarkeit | Logs, Statistik, Audit, Metriken, Benachrichtigungen |
| 6 | Betrieb & Release | Backup, CA-Rotation, Härtung, v1.0 |
| – | Backlog | Niedrige Priorität, ohne festen Zeitpunkt |

---

## Phase 0 – Fundament

**Ziel:** Saubere Basis, auf der alle weiteren Phasen aufbauen.

- [x] Design-Prototyp als Svelte-5-Code (`frontend/`)
- [x] Backend-Gerüst mit uv + FastAPI (`backend/`), Health-Endpunkt, Tests
- [x] Dockerfile (Frontend + Backend in einem Image), Caddy-Image mit Coraza, `compose.yaml`
- [x] Dokumentation in `docs/`, Featureliste, Roadmap
- [x] Git-Repository
- [ ] CI (Lint, Tests, `svelte-check`, Image-Build)
- [ ] Architekturentscheidungen aus [architecture.md](architecture.md#offene-entscheidungen) treffen

**Fertig, wenn:** `docker compose up` startet Controller + Caddy, UI und `/api/health` sind erreichbar.

## Phase 1 – Proxy-Manager (Single-Node)

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

Offen / bewusst verschoben:
- Coraza-WAF in der erzeugten Config (auch für die Controller-Domain) → Phase 3
- Erreichbarkeit des Ziels wird vom Controller aus geprüft, nicht vom Node → Phase 4 (Agent)
- Upstream-HTTPS mit selbstsigniertem Zertifikat (`insecure_skip_verify`) fehlt noch

**Fertig, wenn:** Ein öffentlicher Host mit gültigem Let's-Encrypt-Zertifikat lässt sich komplett
über das UI anlegen, ändern und auf eine alte Version zurücksetzen.

## Phase 2 – mTLS & Identitäten

**Ziel:** Private Dienste nur für freigegebene Geräte – die VPN-Alternative.

- [x] Eigene CA: Root-Schlüssel nur einmal verschlüsselt ausgeliefert (offline), Geräte-Zwischenzertifikat verschlüsselt auf dem Controller
- [x] Personen, Gruppen, Geräte; ein Client-Zertifikat pro Gerät, Geräte-Limit pro Person
- [x] Zugriffsart pro Host (Öffentlich / mTLS) und Verhalten ohne Zertifikat (ablehnen / Hinweisseite)
- [x] Freigaben an Gruppen und Personen, Zugriffsmatrix
- [x] Zugriff pro Pfad in beide Richtungen, z. B. API öffentlich, `/admin` nur per mTLS
- [x] Sperren von Geräten (sofort aus allen Freigabelisten), Export gesperrter Geräte
- [x] Einladungsfluss: Link + QR + separater Bestätigungscode, Admin-Freigabe, Installationsanleitungen je Plattform
- [x] Admin-UI nur mit Admin-Gerätezertifikat (+ Passwort), Notausgang `tesseract admin mtls off`

Offen / bewusst verschoben:
- Verlängern eines Geräts ohne neue Registrierung und Ablauf-Erinnerungen → Phase 6
- Passkey als Alternative zum Passwort → Backlog/Phase 6
- Import einer bestehenden CA bzw. Signieren eines neuen Zwischenzertifikats mit dem Root-Schlüssel → Phase 6
- Eigene Freigaben pro Pfad (heute gelten die Freigaben des Hosts für alle geschützten Pfade) → Phase 3 („Host-Bereiche“)

**Fertig, wenn:** Ein eingeladener Gast registriert ein iPhone und einen Laptop, erreicht genau die
freigegebenen Dienste, und nach dem Sperren eines Geräts schlägt dessen TLS-Handshake fehl.
Bei einem Host mit öffentlicher `/api/*` und geschütztem `/admin/*` antwortet die API ohne
Zertifikat, `/admin/*` nur mit.

## Phase 3 – WAF & Zugriffsschutz

**Ziel:** Öffentliche Dienste absichern.

- [x] Coraza WAF pro Host (Aus / Protokollieren / Blockieren), OWASP CRS, Paranoia-Level, Standards für neue Hosts, WAF für die Oberfläche
- [x] Regel-Ausnahmen pro Host und pro Bereich
- [x] IP-Filter (Sperren / Nur erlauben), benannte IP-Listen (Vorlage Cloudflare)
- [x] Auto-Sperre nach WAF-Treffern, Sperren von Hand, automatischer Ablauf
- [x] Authelia-Integration (Forward-Auth) als Host-Middleware, weitergereichte Header
- [x] Vertrauenswürdige Proxys für die korrekte Client-IP
- [x] DNS-01-Challenge (Cloudflare) für Wildcards und Hosts ohne Port 80
- [x] Host-Bereiche: Pfade mit eigenen Regeln für Zugriff/Freigaben, WAF, IP-Filter, Authelia

Offen / bewusst verschoben:
- „Aktionen aus Logs“ (Ausnahme direkt aus einem Treffer anlegen, IP aus dem Log sperren) → Phase 5 mit der Log-Ansicht
- weitere DNS-Anbieter neben Cloudflare → Backlog
- echter Zertifikatsabruf per DNS-01 nur mit Format-Prüfung getestet (braucht echte Zone)

**Fertig, wenn:** Ein SQL-Injection-Versuch wird blockiert, protokolliert und führt nach Schwellwert
zur automatischen IP-Sperre.

## Phase 3b – Interne Dienste & Zertifikate

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

## Phase 4 – Multi-Node

**Ziel:** Beliebig viele Caddy-Server zentral verwalten.

- Tesseract-Agent (Python, eigenes Paket/Image) neben Caddy auf jedem Node
- Beitritt per einmaligem Token (30 Min.), Agent erzeugt Schlüssel, Bestätigung im Controller
- Ausgehende mTLS-Verbindung Agent → Controller (funktioniert hinter NAT, kein offener Admin-Port)
- Config-Verteilung pro Node, Erkennung von Abweichungen, Überschreiben oder Übernehmen
- Modul-Erkennung pro Node (coraza, DNS-Provider)
- Status, letzter Kontakt, Offline-Pufferung

**Fertig, wenn:** Ein Raspberry Pi hinter NAT tritt bei, bekommt Hosts zugewiesen, und eine
lokale Änderung auf dem Pi wird im UI als Abweichung angezeigt.

## Phase 5 – Beobachtbarkeit

**Ziel:** Sehen, was passiert.

- Zentrale Log-Sammlung von allen Nodes (Zugriffs- und WAF-Logs), Live-Ansicht, Such-Syntax
- Statistik: Sicherheit, Traffic & Leistung, Nutzung; lokale GeoIP-Datenbank
- Aktionen aus Logs (IP sperren, Ausnahme anlegen)
- Unveränderliches Audit-Log mit verketteten Prüfsummen, CSV-Export
- Prometheus-Endpunkt inkl. Node-Metriken, Grafana-Dashboard
- Benachrichtigungen per E-Mail, Webhook, ntfy mit Bündelung und Ruhezeiten

**Fertig, wenn:** Ein blockierter Angriff erscheint live in den Logs, in der Statistik und als
ntfy-Meldung.

## Phase 6 – Betrieb & Release

**Ziel:** Stabil genug für den Dauerbetrieb – Version 1.0.

- Verschlüsselte Backups (Zeitplan, Ziele), Wiederherstellen mit automatischer Neuverteilung an Nodes
- Wechsel des Zwischenzertifikats, Ablauf-Erinnerungen für Geräte
- Sicherheits-Review, Härtung der Images, Rate-Limits auf öffentlichen Endpunkten (Einladungsseite)
- Installations- und Betriebsanleitung, Upgrade-Pfad, veröffentlichte Images

## Backlog (niedrige Priorität)

Gewünscht, aber ohne festen Platz in einer Phase. Wird erst nach v1.0 oder bei Bedarf eingeplant.

- **SSO für die Admin-Oberfläche** – Anmeldung der Administratoren über OIDC (z. B. Authelia,
  Keycloak, Authentik). Betrifft nur Admins, nicht die angelegten Personen mit Zugriff auf Hosts.
  Das Admin-Gerätezertifikat (mTLS) bleibt als erste Hürde bestehen.
- **LDAP-Sync für Personen** – Personen und Gruppen aus LDAP übernehmen und regelmäßig abgleichen.
  Freigaben können dann an LDAP-Gruppen hängen; Geräte und Zertifikate verwaltet weiter Tesseract.
  Wer in LDAP deaktiviert wird, wird in Tesseract samt Geräten gesperrt.
- **Docker-Labels** – Hosts automatisch aus Container-Labels anlegen (Domain, Ziel-Port,
  Zugriff …), ähnlich wie bei anderen Reverse Proxys. Erst nach v1.0.
  Issue: [HiCubeBot/tesseract#14](https://github.com/HiCubeBot/tesseract/issues/14)
