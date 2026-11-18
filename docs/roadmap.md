# Roadmap

Das Projekt wird in Phasen umgesetzt. Jede Phase endet mit einem lauffähigen Stand, der
für sich nutzbar ist. Details zu den einzelnen Features: [features.md](features.md).

| Phase | Name | Ergebnis |
|---|---|---|
| 0 | Fundament | Projektstruktur, Docker, Doku – **aktuell** |
| 1 | Proxy-Manager (Single-Node) | Ersetzt NPM für einen lokalen Caddy |
| 2 | mTLS & Identitäten | Private Dienste ohne VPN, Einladungen |
| 3 | WAF & Zugriffsschutz | Coraza, IP-Filter, Authelia |
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
- [ ] Git-Repository, CI (Lint, Tests, `svelte-check`, Image-Build)
- [ ] Architekturentscheidungen aus [architecture.md](architecture.md#offene-entscheidungen) treffen

**Fertig, wenn:** `docker compose up` startet Controller + Caddy, UI und `/api/health` sind erreichbar.

## Phase 1 – Proxy-Manager (Single-Node)

**Ziel:** Funktionsgleich mit den Kernfunktionen von NPM – für einen Caddy im selben Compose-Stack.

- Datenbank (SQLite) mit Migrationen, Datenmodell für Hosts und Config-Versionen
- Admin-Login (Passwort, Sitzung 30 Tage), `tesseract admin reset` auf der Kommandozeile
- Proxy-Hosts anlegen/bearbeiten/löschen über den 3-Schritte-Assistenten
- Optionen: HTTP→HTTPS, WebSockets, Kompression; TLS über Let's Encrypt (HTTP-01)
- Vorab-Prüfungen (DNS, Erreichbarkeit des Ziels)
- Caddy-JSON-Config erzeugen und über die Admin-API übertragen
- Versionierung jeder Änderung, Diff-Ansicht, Zurücksetzen
- Basis-Audit-Log (wer hat was geändert)
- Frontend: Screens Übersicht, Hosts, Host anlegen, Verlauf, Einstellungen/Allgemein an die API anbinden

**Fertig, wenn:** Ein öffentlicher Host mit gültigem Let's-Encrypt-Zertifikat lässt sich komplett
über das UI anlegen, ändern und auf eine alte Version zurücksetzen.

## Phase 2 – mTLS & Identitäten

**Ziel:** Private Dienste nur für freigegebene Geräte – die VPN-Alternative.

- Eigene CA: Root offline (Import/Signieren per Datei), Geräte-Zwischenzertifikat verschlüsselt auf dem Controller
- Personen, Gruppen, Geräte; ein Client-Zertifikat pro Gerät
- Zugriffsart pro Host (Öffentlich / mTLS) und Verhalten ohne Zertifikat (ablehnen / Hinweisseite)
- Freigaben an Gruppen und Personen, Zugriffsmatrix
- Sperren und Verlängern von Geräten, Widerrufsliste
- Einladungsfluss: Link + QR + separater Bestätigungscode, Admin-Freigabe, Installationsanleitungen je Plattform
- Admin-UI selbst nur mit Admin-Gerätezertifikat (+ Passwort/Passkey)

**Fertig, wenn:** Ein eingeladener Gast registriert ein iPhone und einen Laptop, erreicht genau die
freigegebenen Dienste, und nach dem Sperren eines Geräts schlägt dessen TLS-Handshake fehl.

## Phase 3 – WAF & Zugriffsschutz

**Ziel:** Öffentliche Dienste absichern.

- Coraza WAF pro Host (Aus / Protokollieren / Blockieren), OWASP CRS, Paranoia-Level
- Regel-Ausnahmen pro Host und pro Pfadbereich
- IP-Filter (Sperren / Nur erlauben), benannte IP-Listen, Auto-Sperre nach WAF-Treffern
- Authelia als optionale Middleware pro Host (Caddy `forward_auth` auf eine bestehende Instanz), weitergereichte Header – nicht als Login für die Tesseract-Oberfläche
- Vertrauenswürdige Proxys (z. B. Cloudflare) für korrekte Client-IP
- DNS-01-Challenge (Cloudflare) für Wildcards

**Fertig, wenn:** Ein SQL-Injection-Versuch wird blockiert, protokolliert und führt nach Schwellwert
zur automatischen IP-Sperre.

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
