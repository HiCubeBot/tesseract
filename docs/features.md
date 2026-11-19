# Featureliste

Abgeleitet aus dem Design-Prototyp „Caddy Control“ (`frontend/src/screens`). Die Spalte
**Phase** verweist auf die [Roadmap](roadmap.md).

## 1. Proxy-Hosts (NPM-Ersatz)

| Feature | Beschreibung | Phase |
|---|---|---|
| Host-Liste | Suche nach Domain/Ziel, Filter nach Zugriffsart (Alle / Öffentlich / mTLS) und Node | 1 |
| Host-Assistent | 3 Schritte: Domain & Ziel → Zugriff → Prüfen & übertragen | 1 |
| Ziel | Schema (http/https), Ziel-IP/Host und Port, Auswahl des Nodes; bei https optional ohne Prüfung des Zertifikats (selbst signiert) | 1 / 4 / 1.1 |
| Optionen | HTTP→HTTPS-Umleitung, WebSockets, Kompression (gzip/zstd) | 1 |
| Automatische Vorab-Prüfungen | DNS zeigt auf Node, Ziel erreichbar (bei Agent-Nodes vom Node aus geprüft), Domain frei | 1 / 1.1 |
| TLS über Let's Encrypt | HTTP-01; DNS-01 (z. B. Cloudflare) für Wildcards/Hosts ohne Port 80 | 1 / 3 |
| Geteilte Wildcard-Zertifikate | Wildcard-Zertifikat (z. B. `*.home.beispiel.de`) einmal per DNS-01 holen und für alle passenden Hosts verwenden, die trotzdem eigene Einstellungen haben. Verrät einzelne Hostnamen nicht über die öffentlichen Certificate-Transparency-Logs | 3b |
| Zertifikatsübersicht | Alle Zertifikate an einer Stelle (wie bei NPM): Name(n), Aussteller (Let's Encrypt, ZeroSSL, lokal, eigenes), gültig von/bis, Prüfart (HTTP-01/DNS-01), welche Hosts es nutzen, Status (gültig, läuft bald ab, Fehler beim Erneuern), Node; „Bald ablaufende Zertifikate“ in der Übersicht | 3b |
| Eigene Zertifikate | Zertifikat + Schlüssel hochladen (z. B. von einer Firmen-CA) und Hosts zuordnen; Schlüssel verschlüsselt gespeichert | 3b |
| Entwurf / Export | Host als Entwurf speichern, Konfiguration als JSON ansehen | 1 |
| Versionierung | Jede gespeicherte Änderung wird eine Version; Diff „vorher/nachher“ inkl. Caddy-Config-Ausschnitt | 1 |
| Zurücksetzen | Alte Version wiederherstellen = neue Version, die übertragen wird | 1 |
| Docker-Labels *(niedrige Priorität)* | Hosts automatisch aus Labels von Docker-Containern anlegen (z. B. Domain, Port, Zugriff). Erst nach v1.0 – [HiCubeBot/tesseract#14](https://github.com/HiCubeBot/tesseract/issues/14) | Backlog |

## 2. Zugriff per mTLS (VPN-Alternative)

| Feature | Beschreibung | Phase |
|---|---|---|
| Zugriffsart pro Host | **Öffentlich** (nur Let's Encrypt) oder **Nur freigegebene Geräte (mTLS)** | 2 |
| Zugriffsart „Intern“ | Nur aus internen Netzen (LAN, VPN), zentral unter Einstellungen festgelegt; geprüft wird die echte Verbindungs-IP, kein `X-Forwarded-For`. Fremde sehen nichts – die Verbindung wird ohne Antwort abgebrochen. Zertifikat standardmäßig per DNS-01/Wildcard (kein öffentlicher DNS-Eintrag nötig). Optional zusätzlich „nur Admin-Geräte“ per mTLS. Doku zu Split-DNS und NAT-Loopback | 3b |
| Verhalten ohne Zertifikat | Verbindung ablehnen (TLS-Handshake schlägt fehl) **oder** Hinweisseite „Kein Zugang“ | 2 |
| Freigaben | An Gruppen und Personen; gelten automatisch für alle Geräte der Person | 2 |
| Zugriffsmatrix | Gruppe/Person × Dienst, unterscheidet „direkt erlaubt“ und „über Gruppe“; Änderungen gesammelt übertragen oder verwerfen | 2 |
| Automatische Aktualisierung | Neues Gerät einer Person → Freigabelisten werden ergänzt und neu übertragen | 2 |
| Zugriff pro Pfad | Pfade eines Hosts einzeln öffentlich oder per mTLS schützen, z. B. `/api/*` frei aus dem Internet, `/admin/*` nur für freigegebene Geräte. Zwei Modi: **Blacklist** (Host öffentlich, gelistete Pfade nur per mTLS) oder **Whitelist** (Host per mTLS, gelistete Pfade öffentlich). Eigene Freigaben pro Pfad möglich (z. B. `/admin/*` nur für Gruppe Admin). Ohne Zertifikat gibt es dort `403` bzw. die Hinweisseite – ein abgelehnter TLS-Handshake ist pro Pfad technisch nicht möglich | 2 |

## 3. Personen, Gruppen & Geräte

| Feature | Beschreibung | Phase |
|---|---|---|
| Personen | Anlegen, bearbeiten, sperren; Gruppenzugehörigkeit; max. Anzahl Geräte | 2 |
| Gruppen | z. B. Familie, Freunde, Gäste, Admin | 2 |
| Geräte | Ein Gerät = ein Client-Zertifikat, gehört genau einer Person | 2 |
| Geräteliste | Suche nach Gerät/Person/Fingerabdruck; Status (aktiv, läuft bald ab, gesperrt); zuletzt gesehen | 2 |
| Gerät sperren / verlängern | Einzelnes Zertifikat widerrufen; verlängern ohne neue Registrierung (neue .p12, Freigaben bleiben), Erinnerung 30/7 Tage vorher | 2 / 6 |
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
| Host-Bereiche | Pfade mit abweichenden Regeln (z. B. `/api/*`, `/.well-known/*`): Zugriff mit eigenen Freigaben, WAF, IP-Filter, Authelia – baut auf „Zugriff pro Pfad“ (2.) auf | 3 |
| IP-Filter | Modus Sperren / Nur erlauben; IP, CIDR oder benannte IP-Liste | 3 |
| Auto-Sperre | z. B. IP für 24 h sperren nach 20 WAF-Treffern in 10 Min. | 3 |
| Authelia als Host-Middleware | Optional pro Host: Caddy fragt vor dem Dienst per `forward_auth` eine bestehende Authelia-Instanz. Nutzer, Regeln und Zwei-Faktor pflegt man in Authelia selbst; Tesseract richtet nur die Weiterleitung ein. Schützt nur Hosts, nicht die Tesseract-Oberfläche (siehe Admin-SSO unter 10.) | 3 |
| Visualisierung „Weg einer Anfrage“ | Zeigt die Reihenfolge IP-Filter → mTLS → WAF → Auth → Dienst | 3 |

## 6. Nodes

| Feature | Beschreibung | Phase |
|---|---|---|
| Node-Übersicht | Standort, Caddy-Version, Anzahl Hosts, letzter Kontakt, Status (online, offline, lokal geändert, Fehler), Agent-Version, Zertifikat | 4 |
| Node hinzufügen | Beitritts-Token (30 Min., einmalig) und Installationsbefehl (`curl … /install/node.sh | sudo sh`) – richtet Caddy und Agent auf dem Server ein → Schlüssel-Fingerabdruck vergleichen und im Controller bestätigen | 4 / 1.1 |
| Agent | Erzeugt eigene Schlüssel, baut mTLS-Verbindung zum Controller auf (Long-Polling über HTTPS); kein offener Admin-Port, funktioniert hinter NAT | 4 |
| Config-Abweichung | Erkennt lokale Änderungen (Diff pro Host) – „Mit Controller überschreiben“ oder „Änderung übernehmen“ (gilt bis zur nächsten Übertragung) | 4 |
| Modul-Übersicht | Welche Caddy-Module (Coraza, DNS Cloudflare) je Node vorhanden sind; Hosts, die ein fehlendes Modul brauchen, werden beim Speichern abgelehnt | 4 / 1.1 |
| Offline-Pufferung | Ohne Controller läuft Caddy mit dem letzten Stand weiter; Zugriffs- und WAF-Logs puffert der Agent und liefert sie nach | 4 / 5 |

## 7. Statistik & Logs

| Feature | Beschreibung | Phase |
|---|---|---|
| Sicherheit | Abgelehnte Anfragen pro Stunde, Coraza-Angriffsarten, Top-IPs, Herkunftskarte (Kreisfläche = Anzahl, lokale GeoIP-DB, Kartendaten Natural Earth im Build) | 5 |
| Traffic & Leistung | Anfragen, Datenmenge, Antwortzeiten (Median/p95), 5xx-Fehler, Erreichbarkeit, Hosts im Vergleich | 5 |
| Nutzung | Wer nutzt was (Person × Dienst), Geräte-Aktivität, Heatmap Wochentag × Uhrzeit | 5 |
| Logs | Live-Ansicht, Suche mit Filtersyntax (`host:git status:403 ip:…`), Detailansicht mit Regel und Meldung, Anomalie-Score (wenn Coraza ihn schreibt), Grund jeder Ablehnung | 5 |
| Aktionen aus Logs | IP sperren (24 h, alle Nodes), Ausnahme für Fehlalarm anlegen, alle Einträge einer IP | 5 |
| Filter | Zeitraum (24 h / 7 / 30 Tage), Node | 5 |
| Loki | Zusätzlicher Log-Speicher: jeder Eintrag geht auch an Loki (Push-API, Labels `node`, `host`, `reason`, Rest als JSON), gepuffert, falls Loki nicht erreichbar ist. Loki optional im Compose-Stack (Profil `loki`), Auswertung in Grafana per LogQL | 1.2 |

## 8. Audit-Log

| Feature | Beschreibung | Phase |
|---|---|---|
| Protokoll | Jede Änderung und jeder abgewiesene Zugriff – wer, wann, was, von welchem Gerät/IP | 1 (Basis) / 5 |
| Unveränderlich | Einträge nicht bearbeit-/löschbar, Prüfsumme verkettet mit dem vorherigen Eintrag | 5 |
| Filter & Export | Suche, Filter nach Akteur (Admins, System, Gäste, Agents), CSV-Export, Prüfung der Kette | 5 |

## 9. Einstellungen

| Feature | Beschreibung | Phase |
|---|---|---|
| Allgemein | Controller-Domain, Let's-Encrypt-Konto, Standards für alle Nodes | 1 |
| Zertifizierungsstelle | Root-CA offline (z. B. USB-Stick), Geräte-Zwischenzertifikat verschlüsselt auf dem Controller, ECDSA P-384, Root-Zertifikat herunterladen | 2 |
| CA-Wechsel | Neues Zwischenzertifikat mit dem offline aufbewahrten Root-Schlüssel; das alte bleibt vertraut, bis seine Geräte verlängert sind; Warnung, wenn Geräte länger gültig sind als das Zwischenzertifikat; Erinnerung 90/30/7 Tage vorher | 6 |
| Integrationen | Authelia-Instanz für die Host-Middleware (URL, weitergereichte Header), IP-Listen, vertrauenswürdige Proxys (X-Forwarded-For), Coraza-Standards, Caddy-Module pro Node | 3 |
| Benachrichtigungen | E-Mail, Webhook, ntfy; Ereignis × Kanal × Stufe; Bündeln (max. 1× / 15 Min.), Ruhezeit nachts | 5 |
| Metriken | Prometheus-Endpunkt für Controller und alle Nodes, Schutz per Bearer-Token / mTLS / IP-Liste, `prometheus.yml`-Snippet, Grafana-Dashboard (JSON) | 5 |
| Git-Spiegel | Hosts, Caddy-Config pro Node, IP-Listen und Einstellungen lesbar in einem Git-Repository (HTTPS-Token oder SSH-Deploy-Key); jede Änderung ein Commit mit den Einträgen aus dem Audit-Log als Nachricht. Ohne Schlüssel, Tokens, Personen und IP-Sperren | 1.2 |
| Backup | Zeitplan (stündlich/täglich/wöchentlich), Ziele lokal und S3-kompatibel, verschlüsselt mit Passphrase (AES-256-GCM, scrypt); Root-Schlüssel nie enthalten; Wiederherstellungstest; Wiederherstellen aus Ziel oder Datei, auch per Kommandozeile | 6 |

## 10. Admin-Zugang

| Feature | Beschreibung | Phase |
|---|---|---|
| Doppelter Schutz | Admin-UI nur mit Admin-Gerätezertifikat erreichbar, zusätzlich Passwort. Eigene Anmeldung von Tesseract, unabhängig von der Authelia-Middleware für Hosts | 1 (Passwort) / 2 (mTLS) |
| SSO für Admins *(niedrige Priorität)* | Anmeldung an der Admin-Oberfläche über einen externen Identity Provider (OIDC) statt Passwort. Betrifft nur Administratoren, nicht die Personen mit Zugriff auf Hosts. Das Admin-Gerätezertifikat bleibt Pflicht | Backlog |
| Passkey *(niedrige Priorität)* | Anmeldung per WebAuthn zusätzlich oder statt Passwort | Backlog |
| Angemeldet bleiben | 30 Tage pro Gerät | 1 |
| Passwort-Reset | Nur lokal auf dem Controller: `tesseract admin reset` | 1 |
