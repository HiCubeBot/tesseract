# Featureliste

Abgeleitet aus dem Design-Prototyp „Caddy Control“ (`frontend/src/screens`). Die Spalte
**Phase** verweist auf die [Roadmap](roadmap.md).

## 1. Proxy-Hosts (NPM-Ersatz)

| Feature | Beschreibung | Phase |
|---|---|---|
| Host-Liste | Suche nach Domain/Ziel, Filter nach Zugriffsart (Alle / Öffentlich / mTLS) und Node | 1 |
| Host-Assistent | 3 Schritte: Domain & Ziel → Zugriff → Prüfen & übertragen | 1 |
| Ziel | Schema (http/https), Ziel-IP/Host und Port, Auswahl des Nodes | 1 / 4 |
| Optionen | HTTP→HTTPS-Umleitung, WebSockets, Kompression (gzip/zstd) | 1 |
| Automatische Vorab-Prüfungen | DNS zeigt auf Node, Ziel erreichbar, Domain frei | 1 |
| TLS über Let's Encrypt | HTTP-01; DNS-01 (z. B. Cloudflare) für Wildcards/Hosts ohne Port 80 | 1 / 3 |
| Entwurf / Export | Host als Entwurf speichern, Konfiguration als JSON ansehen | 1 |
| Versionierung | Jede gespeicherte Änderung wird eine Version; Diff „vorher/nachher“ inkl. Caddy-Config-Ausschnitt | 1 |
| Zurücksetzen | Alte Version wiederherstellen = neue Version, die übertragen wird | 1 |

## 2. Zugriff per mTLS (VPN-Alternative)

| Feature | Beschreibung | Phase |
|---|---|---|
| Zugriffsart pro Host | **Öffentlich** (nur Let's Encrypt) oder **Nur freigegebene Geräte (mTLS)** | 2 |
| Verhalten ohne Zertifikat | Verbindung ablehnen (TLS-Handshake schlägt fehl) **oder** Hinweisseite „Kein Zugang“ | 2 |
| Freigaben | An Gruppen und Personen; gelten automatisch für alle Geräte der Person | 2 |
| Zugriffsmatrix | Gruppe/Person × Dienst, unterscheidet „direkt erlaubt“ und „über Gruppe“; Änderungen gesammelt übertragen oder verwerfen | 2 |
| Automatische Aktualisierung | Neues Gerät einer Person → Freigabelisten werden ergänzt und neu übertragen | 2 |

## 3. Personen, Gruppen & Geräte

| Feature | Beschreibung | Phase |
|---|---|---|
| Personen | Anlegen, bearbeiten, sperren; Gruppenzugehörigkeit; max. Anzahl Geräte | 2 |
| Gruppen | z. B. Familie, Freunde, Gäste, Admin | 2 |
| Geräte | Ein Gerät = ein Client-Zertifikat, gehört genau einer Person | 2 |
| Geräteliste | Suche nach Gerät/Person/Fingerabdruck; Status (aktiv, läuft bald ab, gesperrt); zuletzt gesehen | 2 |
| Gerät sperren / verlängern | Einzelnes Zertifikat widerrufen oder neu ausstellen | 2 |
| Gültigkeit | Befristet (z. B. 1 Jahr) oder „unbegrenzt“ (begrenzt durch Zwischenzertifikat) | 2 |
| Export gesperrter Zertifikate | Liste der widerrufenen Zertifikate | 2 |
| LDAP-Sync *(niedrige Priorität)* | Personen und Gruppen aus einem LDAP-Verzeichnis übernehmen und abgleichen, damit Freigaben über LDAP-Gruppen laufen können. Geräte und Zertifikate bleiben in Tesseract | Backlog |

## 4. Einladungen

| Feature | Beschreibung | Phase |
|---|---|---|
| Person einladen (Admin) | Person + Gruppe + Geräteanzahl anlegen, Einladungslink und QR-Code erzeugen | 2 |
| Bestätigungscode | Separat (mündlich/Telefon) mitzuteilen – ein abgefangener Link allein reicht nicht | 2 |
| Freigabe durch Admin | Registrierungsanfrage (Gerät, OS, Code korrekt) annehmen oder ablehnen; Einladung widerrufen | 2 |
| Gast: Gerät registrieren | Geräteerkennung, Schlüssel wird nur für dieses Gerät erzeugt | 2 |
| Gast: Zertifikat installieren | Anleitung je Plattform (iOS, Android, macOS, Windows, Linux), Verbindungstest | 2 |
| Mobile Ansichten | Eigene Handy-Layouts für Registrierung und Installation | 2 |
| Mehrere Geräte | Gleicher Link für weitere Geräte, solange Plätze frei sind | 2 |
| Öffentliche Einladungsseite | Einziger Teil von Tesseract, der ohne Zertifikat erreichbar ist | 2 |

## 5. Sicherheit pro Host

| Feature | Beschreibung | Phase |
|---|---|---|
| Coraza WAF | Aus / Nur protokollieren / Blockieren; OWASP Core Rule Set; Paranoia-Level | 3 |
| Regel-Ausnahmen | Pro Host für Fehlalarme, direkt aus einem Log-Eintrag anlegbar | 3 |
| Host-Bereiche | Pfade mit abweichenden Regeln (z. B. `/api/*`, `/.well-known/*`) | 3 |
| IP-Filter | Modus Sperren / Nur erlauben; IP, CIDR oder benannte IP-Liste | 3 |
| Auto-Sperre | z. B. IP für 24 h sperren nach 20 WAF-Treffern in 10 Min. | 3 |
| Authelia als Host-Middleware | Optional pro Host: Caddy fragt vor dem Dienst per `forward_auth` eine bestehende Authelia-Instanz. Nutzer, Regeln und Zwei-Faktor pflegt man in Authelia selbst; Tesseract richtet nur die Weiterleitung ein. Schützt nur Hosts, nicht die Tesseract-Oberfläche (siehe Admin-SSO unter 10.) | 3 |
| Visualisierung „Weg einer Anfrage“ | Zeigt die Reihenfolge IP-Filter → mTLS → WAF → Auth → Dienst | 3 |

## 6. Nodes

| Feature | Beschreibung | Phase |
|---|---|---|
| Node-Übersicht | Standort, Caddy-Version, Anzahl Hosts, letzter Kontakt, Status | 4 |
| Node hinzufügen | Beitritts-Token (30 Min., einmalig) → Agent starten → im Controller bestätigen | 4 |
| Agent | Erzeugt eigene Schlüssel, baut mTLS-Verbindung zum Controller auf; kein offener Admin-Port, funktioniert hinter NAT | 4 |
| Config-Abweichung | Erkennt lokale Änderungen (Diff) – „Mit Controller überschreiben“ oder „Änderung übernehmen“ | 4 |
| Modul-Übersicht | Welche Caddy-Module (coraza, dns.cloudflare …) je Node vorhanden sind; Features werden sonst gesperrt | 4 |
| Offline-Pufferung | Node puffert Logs lokal und liefert nach | 4 |

## 7. Statistik & Logs

| Feature | Beschreibung | Phase |
|---|---|---|
| Sicherheit | Abgelehnte Anfragen pro Stunde, Coraza-Angriffsarten, Top-IPs, Herkunftskarte (lokale GeoIP-DB) | 5 |
| Traffic & Leistung | Anfragen, Datenmenge, Antwortzeiten (Median/p95), 5xx-Fehler, Erreichbarkeit, Hosts im Vergleich | 5 |
| Nutzung | Wer nutzt was (Person × Dienst), Geräte-Aktivität, Heatmap Wochentag × Uhrzeit | 5 |
| Logs | Live-Ansicht, Suche mit Filtersyntax (`host:git status:403 ip:…`), Detailansicht mit Regel, Anomalie-Score | 5 |
| Aktionen aus Logs | IP sperren (in Liste), Ausnahme für Fehlalarm anlegen, alle Einträge einer IP | 5 |
| Filter | Zeitraum (24 h / 7 / 30 Tage), Node | 5 |

## 8. Audit-Log

| Feature | Beschreibung | Phase |
|---|---|---|
| Protokoll | Jede Änderung und jeder abgewiesene Zugriff – wer, wann, was, von welchem Gerät/IP | 1 (Basis) / 5 |
| Unveränderlich | Einträge nicht bearbeit-/löschbar, Prüfsumme verkettet mit dem vorherigen Eintrag | 5 |
| Filter & Export | Suche, Filter nach Akteur (Admin, System, Gäste), CSV-Export | 5 |

## 9. Einstellungen

| Feature | Beschreibung | Phase |
|---|---|---|
| Allgemein | Controller-Domain, Let's-Encrypt-Konto, Standards für alle Nodes | 1 |
| Zertifizierungsstelle | Root-CA offline (z. B. USB-Stick), Geräte-Zwischenzertifikat verschlüsselt auf dem Controller, ECDSA P-384, Root-Zertifikat herunterladen | 2 |
| CA-Wechsel | Wechsel auf neues Zwischenzertifikat vorbereiten; Warnung, wenn Geräte länger gültig sind als das Zwischenzertifikat; Erinnerung 30 Tage vorher | 6 |
| Integrationen | Authelia-Instanz für die Host-Middleware (URL, weitergereichte Header), IP-Listen, vertrauenswürdige Proxys (X-Forwarded-For), Coraza-Standards, Caddy-Module pro Node | 3 |
| Benachrichtigungen | E-Mail, Webhook, ntfy; Ereignis × Kanal × Stufe; Bündeln (max. 1× / 15 Min.), Ruhezeit nachts | 5 |
| Metriken | Prometheus-Endpunkt für Controller und alle Nodes, Schutz per Bearer-Token / mTLS / IP-Liste, `prometheus.yml`-Snippet, Grafana-Dashboard (JSON) | 5 |
| Backup | Zeitplan (stündlich/täglich/wöchentlich), Ziele, verschlüsselt mit Passphrase; Root-Schlüssel nie enthalten; Wiederherstellen | 6 |

## 10. Admin-Zugang

| Feature | Beschreibung | Phase |
|---|---|---|
| Doppelter Schutz | Admin-UI nur mit Admin-Gerätezertifikat erreichbar, zusätzlich Passwort oder Passkey. Eigene Anmeldung von Tesseract, unabhängig von der Authelia-Middleware für Hosts | 1 (Passwort) / 2 (mTLS) |
| SSO für Admins *(niedrige Priorität)* | Anmeldung an der Admin-Oberfläche über einen externen Identity Provider (OIDC) statt Passwort. Betrifft nur Administratoren, nicht die Personen mit Zugriff auf Hosts. Das Admin-Gerätezertifikat bleibt Pflicht | Backlog |
| Angemeldet bleiben | 30 Tage pro Gerät | 1 |
| Passwort-Reset | Nur lokal auf dem Controller: `tesseract admin reset` | 1 |
