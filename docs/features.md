# Featureliste

Abgeleitet aus dem Design-Prototyp „Caddy Control“ (`frontend/src/screens`). Die Spalte
**Phase** verweist auf die [Roadmap](roadmap.md).

## 1. Proxy-Hosts (NPM-Ersatz)

| Feature | Beschreibung | Phase |
|---|---|---|
| Host-Liste | Suche nach Domain/Ziel, Filter (Alle / Aktiv / mTLS / Deaktiviert / Entwürfe) und Node; Hosts per Schalter direkt in der Zeile ein- und ausschalten (bleiben gespeichert, gehen nicht an Caddy) | 1 / 1.5 |
| Hosts aus Docker-Labels | Container mit `tesseract.domain` werden zu Hosts (Port, Ziel, Zugriff, interne Netze, Freigaben, WAF, Prüfart per Label). Lokal über einen Socket-Proxy, Agent-Nodes melden ihre Container. Neue Hosts als Entwurf, Label-Änderungen gelten, gestoppte/entfernte Container schalten den Host ab; gekennzeichnet in Liste und Host-Seite | 1.6 |
| Uptime-Monitor | Jede Minute: Node verbunden? Ziel des Hosts erreichbar (vom Node aus)? Ausfall ab dem zweiten Fehlschlag, Vorfälle, Benachrichtigung „Dienst nicht erreichbar“; je Host abschaltbar | 1.17 |
| Öffentliche Statusseite | Unter Einstellungen › Allgemein einschaltbar (Standard: aus); `/status` ohne Anmeldung: ausgewählte Dienste mit eigenem Namen, Stand und Erreichbarkeit der letzten 90 Tage – ohne Domains und Adressen | 1.17 |
| Host bearbeiten | Eigene Seite mit Tabs Allgemein · Zugriff · Sicherheit · Statistik · Verlauf; Aktiv-Schalter im Kopf, Vorab-Prüfungen wie beim Anlegen, Nachfrage bei ungespeicherten Änderungen | 1.5 |
| Host-Assistent | 3 Schritte: Domain & Ziel → Zugriff → Prüfen & übertragen | 1 |
| Ziel | Schema (http/https), Ziel-IP/Host und Port, Auswahl des Nodes; bei https optional ohne Prüfung des Zertifikats (selbst signiert) | 1 / 4 / 1.1 |
| Optionen | HTTP→HTTPS-Umleitung, WebSockets, Kompression (gzip/zstd) | 1 |
| DNS-Eintrag automatisch | Beim Anlegen wählbar: Tesseract legt den Eintrag bei Cloudflare an und ändert/löscht ihn mit dem Host. Pro Domain ein Standard – CNAME auf einen Namen (z. B. DDNS) oder A/AAAA auf die öffentlichen IPs des Nodes bzw. eigene IPs, optional über den Cloudflare-Proxy; pro Host änderbar. Fremde Einträge bleiben unangetastet | 1.9 |
| Automatische Vorab-Prüfungen | DNS zeigt auf den gewählten Node (öffentliche IPs pro Node unter Nodes › Bearbeiten), Ziel erreichbar (bei Agent-Nodes vom Node aus geprüft), Domain frei | 1 / 1.1 / 1.4.1 |
| TLS über Let's Encrypt | HTTP-01; DNS-01 (z. B. Cloudflare) für Wildcards/Hosts ohne Port 80 | 1 / 3 |
| Oberfläche per DNS-01 | Mit `TESSERACT_CLOUDFLARE_TOKEN` in der `.env` holt auch die Oberfläche ihr Zertifikat per DNS – ohne Portweiterleitung, auch für Namen nur im Heimnetz | 1.4.2 |
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
| Intern ohne Zertifikat | Pro Host mit „Nur mit Zertifikat“ wählbar: Anfragen aus den internen Netzen kommen ohne Client-Zertifikat durch, von außen gilt die Pflicht weiter (z. B. für Fernseher, Drucker, Apps ohne mTLS). Geprüft wird die echte Verbindungs-IP; ohne Zertifikat gibt es dann „403“ statt Handshake-Abbruch | 1.12 |
| Tesseract selbst darf zugreifen | Pro Host mit Zertifikatspflicht: der Controller kommt mit seinem eigenen Client-Zertifikat durch (z. B. Benachrichtigungen an ntfy hinter Tesseract) – unabhängig von IP und Docker-Netz; Zertifikat erneuert sich selbst | 1.21 |
| Verhalten ohne Zertifikat | Verbindung ablehnen (TLS-Handshake schlägt fehl) **oder** Hinweisseite „Kein Zugang“ (mit Dienst, eigener IP, Zeit und Anfrage-ID für Rückfragen) | 2 |
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
| Zertifikat erneut abrufen | `.p12` und Passwort verschlüsselt aufbewahrt (abschaltbar): unter Geräte jederzeit wieder herunterladen, Passwort anzeigen, Kopie löschen; „Aufs Handy“ per QR-Code (Link 15 Min., 3 Abrufe, ohne Passwort) | 1.22 |
| Gerät sperren / entsperren / verlängern | Einzelnes Zertifikat widerrufen und bei Bedarf wieder freigeben (1.25.1); verlängern ohne neue Registrierung (neue .p12, Freigaben bleiben), Erinnerung 30/7 Tage vorher | 2 / 6 |
| Gäste verlängern selbst | Link `https://<controller>/v` auf dem Gerät öffnen – das noch gültige Zertifikat ist der Ausweis, ohne Einladung und Freigabe. Ab einstellbaren Tagen vor Ablauf (Standard 30), nach einem CA-Wechsel sofort; abschaltbar (Einstellungen › Zertifizierungsstelle) | 1.2 |
| Gültigkeit | Befristet (z. B. 1 Jahr) oder „unbegrenzt“ (begrenzt durch Zwischenzertifikat) | 2 |
| Export gesperrter Zertifikate | Liste der widerrufenen Zertifikate | 2 |
| LDAP-Sync | Personen und Gruppen aus einem LDAP-Verzeichnis übernehmen und regelmäßig abgleichen (Name, E-Mail, Gruppen), Freigaben an LDAP-Gruppen; in LDAP deaktiviert oder entfernt → gesperrt samt Geräten; Vorschau, Vorlagen für OpenLDAP, AD, FreeIPA. Geräte und Zertifikate bleiben in Tesseract | 1.3 |

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
| IP von Hand sperren | IP oder Netz für 1 Stunde bis 1 Jahr oder dauerhaft sperren (bis zum Entsperren); gilt auf allen Nodes | 3 / 1.3.1 |
| Authelia als Host-Middleware | Optional pro Host: Caddy fragt vor dem Dienst per `forward_auth` eine bestehende Authelia-Instanz. Nutzer, Regeln und Zwei-Faktor pflegt man in Authelia selbst; Tesseract richtet nur die Weiterleitung ein. Schützt nur Hosts, nicht die Tesseract-Oberfläche (siehe Admin-SSO unter 10.) | 3 |
| robots.txt | Caddy beantwortet `/robots.txt` selbst, noch vor Zertifikat und WAF: Aus (Dienst antwortet), Alles erlauben, Alles verbieten, KI-Crawler verbieten (Liste unter Einstellungen pflegbar), Nur bestimmte Pfade sperren oder eigener Text mit Syntaxprüfung und Vorschau; optional `Sitemap:`; robots.txt des Dienstes als Ausgangspunkt übernehmen. Standard für neue Hosts und „mTLS-Hosts: alles verbieten“ unter Einstellungen; Docker-Label `tesseract.robots` | 1.23 |
| Visualisierung „Weg einer Anfrage“ | Zeigt die Reihenfolge IP-Filter → mTLS → WAF → Auth → Dienst | 3 |

## 6. Nodes

| Feature | Beschreibung | Phase |
|---|---|---|
| Node-Übersicht | Kompakte Karten: Standort, Caddy-Version, Hosts (davon öffentlich), letzter Kontakt, Konfigurationsstand, Status (online, offline, lokal geändert, Fehler), Verbindung zum Controller (Adresse aus Sicht des Agents, intern/privat/Internet); Details mit Modulen, Agent-Version, Zertifikat, IPs | 4 / 1.14 |
| Node hinzufügen | Beitritts-Token (30 Min., einmalig) und Installationsbefehl (`curl … /install/node.sh | sudo sh`) – richtet Caddy und Agent auf dem Server ein → Schlüssel-Fingerabdruck vergleichen und im Controller bestätigen | 4 / 1.1 |
| Agent | Erzeugt eigene Schlüssel, baut mTLS-Verbindung zum Controller auf (Long-Polling über HTTPS); kein offener Admin-Port, funktioniert hinter NAT | 4 |
| Config-Abweichung | Erkennt lokale Änderungen (Diff pro Host) – „Mit Controller überschreiben“ oder „Änderung übernehmen“ (gilt bis zur nächsten Übertragung) | 4 |
| Modul-Übersicht | Welche Caddy-Module (Coraza, DNS Cloudflare) je Node vorhanden sind; Hosts, die ein fehlendes Modul brauchen, werden beim Speichern abgelehnt | 4 / 1.1 |
| Offline-Pufferung | Ohne Controller läuft Caddy mit dem letzten Stand weiter; Zugriffs- und WAF-Logs puffert der Agent und liefert sie nach | 4 / 5 |
| Neustart ohne Controller | Startet Caddy auf einem Node neu, lädt es den zuletzt bekannten Stand (`--resume`); fehlt der, lädt ihn der Agent aus seiner eigenen Kopie (`last-config.json`) – ohne Controller | 1.4 |

## 7. Statistik & Logs

| Feature | Beschreibung | Phase |
|---|---|---|
| Sicherheit | Kennzahlen mit Verlauf und Vorzeitraum (Anfragen, Abgelehnt, ohne Zertifikat, Coraza blockiert/nur erkannt, IP-Filter, Fehlanmeldungen), Top-IPs mit Kennzeichen eigene/intern und Sperren, abgelehnte Anfragen pro Stunde, Coraza-Angriffsarten, Top-IPs, Herkunftskarte aller Anfragen mit Filter Alle / Abgelehnt / Angenommen (Kreisfläche = Anzahl, lokale GeoIP-DB, Kartendaten Natural Earth im Build) | 5 / 1.11 |
| Traffic & Leistung | Anfragen, Besucher, Daten (aus/ein), Antwortzeiten (Median/p95), 5xx-Fehler, Kompression – mit Vorzeitraum; Zusammensetzung (Statuscodes, HTTP-Version, Browser/Apps/Bots), Pfade mit Fehlern, Clients mit Namen, Statuscodes, Hosts im Vergleich; gesamter Zeitraum aus dauerhaft aufbewahrten Tageswerten | 5 / 1.16 |
| Betrieb | Summen seit Beginn, Erreichbarkeit der Nodes und Hosts (30 Tage, Tagesbalken), Zertifikate (Erneuerungen, nächste Abläufe), Rekorde, letzte Ausfälle | 1.17 |
| Karte | Zoombare Weltkarte (Städte mit Stadt-Datenbank), Punkte je nach Zoom zusammengefasst; Ranglisten Länder / Städte / Netzbetreiber (ASN); Filter Alle / Abgelehnt / Angenommen; Länder anklickbar (heranzoomen, Anfragen, Abgelehnte, häufigste Ziele, Städte und Netzbetreiber des Landes, Link zu den Logs) | 1.16 / 1.19 |
| Nutzung | Wer nutzt was (Person × Dienst), Geräte-Aktivität, Heatmap Wochentag × Uhrzeit | 5 |
| Statistik pro Host | Tab „Statistik“ je Host: Anfragen, Besucher ohne Bots, Daten (aus/ein), Antwortzeit, 5xx, Kompression – mit Vergleich zum Vorzeitraum und Verlaufslinie; Verlauf mit Vorzeitraum, Abgelehnt nach Grund, Herkunft, Pfade mit Fehlern, abgelehnte IPs mit „Sperren“. In der Hostliste: Anfragen der letzten 24 h mit Verlaufslinie | 1.15 |
| Logs | Live-Ansicht, Suche mit Filtersyntax (`host:git status:403 ip:…`), Detailansicht mit Regel und Meldung, Anomalie-Score (wenn Coraza ihn schreibt), Grund jeder Ablehnung | 5 |
| Aktionen aus Logs | IP sperren (24 h, alle Nodes), Ausnahme für Fehlalarm anlegen, alle Einträge einer IP | 5 |
| Filter | Zeitraum (24 h / 7 / 30 Tage), Node | 5 |
| Loki | Zusätzlicher Log-Speicher: jeder Eintrag geht auch an Loki (Push-API, Labels `node`, `host`, `reason`, Rest als JSON), gepuffert, falls Loki nicht erreichbar ist. Loki optional im Compose-Stack (Profil `loki`), Auswertung in Grafana per LogQL | 1.2 |
| Logs und Statistik aus Loki/VictoriaLogs | Auf Wunsch fragen Log-Ansicht (Suche, Live, Details, Ausnahme aus dem Log) und Statistik den externen Speicher statt SQLite – so weit zurück, wie er aufbewahrt. Gleiche Filtersyntax, übersetzt nach LogQL bzw. LogsQL; Kennzahlen als Aggregat-Abfragen | 1.6 |
| VictoriaLogs | Statt Loki: dieselben Einträge über `/insert/jsonline` (Stream-Felder `job`, `node`, `host`, `reason`, alle anderen Werte als Felder), Mandant `AccountID[:ProjectID]`; optional im Compose-Stack (Profil `victorialogs`), Abfrage mit LogsQL | 1.4 |

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
| CA importieren | Bestehende PKI übernehmen: Root-Zertifikat mit Root-Schlüssel (Tesseract erzeugt das Zwischenzertifikat) oder mit fertigem Zwischenzertifikat samt Schlüssel; ECDSA oder RSA ab 2048 Bit; Prüfung von CA-Merkmalen, Aussteller, Schlüssel und Laufzeit | 1.4 |
| Root-Wechsel | Neue Root erzeugen oder importieren; das alte Zwischenzertifikat bleibt vertraut, solange Geräte oder Nodes daran hängen; Agents erneuern ihr Node-Zertifikat danach von selbst | 1.4 |
| Integrationen | Authelia-Instanz für die Host-Middleware (URL, weitergereichte Header), IP-Listen, vertrauenswürdige Proxys (X-Forwarded-For), Coraza-Standards, Caddy-Module pro Node | 3 |
| Benachrichtigungen | E-Mail, Webhook, ntfy (Token oder Benutzer/Passwort, klare Fehlermeldung bei fehlenden Rechten; mit eigenem Controller-Zertifikat auch an Ziele hinter mTLS-Hosts); Ereignis × Kanal × Stufe (u. a. Node offline, Dienst nicht erreichbar); Bündeln (max. 1× / 15 Min.), Ruhezeit nachts | 5 |
| Metriken | Prometheus-Endpunkt für Controller und alle Nodes, Schutz per Bearer-Token / mTLS / IP-Liste, `prometheus.yml`-Snippet, Grafana-Dashboard (JSON) | 5 |
| Git-Spiegel | Hosts, Caddy-Config pro Node, IP-Listen und Einstellungen lesbar in einem Git-Repository (HTTPS-Token oder SSH-Deploy-Key); jede Änderung ein Commit mit den Einträgen aus dem Audit-Log als Nachricht. Ohne Schlüssel, Tokens, Personen und IP-Sperren | 1.2 |
| Backup | Zeitplan (stündlich/täglich/wöchentlich), Ziele lokal, S3-kompatibel und Restic-Repository (1.6), verschlüsselt mit Passphrase (AES-256-GCM, scrypt); Root-Schlüssel nie enthalten; Wiederherstellungstest; Wiederherstellen aus Ziel oder Datei, auch per Kommandozeile | 6 |

## 10. Admin-Zugang

| Feature | Beschreibung | Phase |
|---|---|---|
| Doppelter Schutz | Admin-UI nur mit Admin-Gerätezertifikat erreichbar, zusätzlich Passwort. Eigene Anmeldung von Tesseract, unabhängig von der Authelia-Middleware für Hosts | 1 (Passwort) / 2 (mTLS) |
| SSO für Admins | Anmeldung an der Admin-Oberfläche über OpenID Connect (Authelia, Keycloak, Authentik, Dex …); Admin über Gruppe oder freigegebene E-Mail. Betrifft nur Administratoren, nicht die Personen mit Zugriff auf Hosts. Das Admin-Gerätezertifikat bleibt Pflicht | 1.3 |
| Passkey | Anmeldung per WebAuthn (Fingerabdruck, Gesicht, Sicherheitsschlüssel) zusätzlich oder statt Passwort; Passwort-Anmeldung abschaltbar | 1.3 |
| Personen per Zertifikat | Einzelne Personen dürfen Tesseract öffnen – nur per Gerätezertifikat, ohne Passwort. Rollen Lesen, Eigene Dienste (nur freigegebene Hosts), Admin; Prüfung bei jeder Anfrage, gesperrte Geräte sofort ohne Zugriff; Audit-Log mit Person und Gerät; Seite „Mein Zugang“ ([anmeldung.md](anmeldung.md#personen-per-gerätezertifikat)) | 1.24 |
| Angemeldet bleiben | 30 Tage pro Gerät | 1 |
| Passwort-Reset | Nur lokal auf dem Controller: `tesseract admin reset` | 1 |

## Oberfläche

| Feature | Beschreibung | Phase |
|---|---|---|
| DNS-Eintrag für die Tesseract-Domain | Damit Nodes den Controller über den Namen finden: CNAME oder A/AAAA (IPs des lokalen Nodes) bei Cloudflare, nie über den Proxy; beim Start und bei neuen Node-IPs nachgezogen | 1.10 |
| Oberfläche nur aus bestimmten Netzen | `TESSERACT_ADMIN_NETWORKS` (Standard alle Netze): aus anderen Netzen bricht Caddy die Verbindung ab, noch vor Anmeldung und Zertifikat. Einladungen und Verlängern bleiben erreichbar, die Agent-Schnittstelle wahlweise (`TESSERACT_AGENT_API_PUBLIC`, Standard an). Kombinierbar mit „Nur mit Admin-Zertifikat“ | 1.7 / 1.10 |
| GeoIP automatisch | `TESSERACT_GEOIP_AUTO=dbip`: Controller holt DB-IP Lite selbst, prüft sie, erneuert monatlich und übernimmt sie ohne Neustart; Stand und „Jetzt aktualisieren“ unter Einstellungen › Metriken, Quellenangabe unter der Karte | 1.8 |
| Zahlen in der Seitenleiste | Anzahl Proxy-Hosts, Nutzer, Geräte und Nodes neben den Menüpunkten | 1.14 |
| Übersicht | Kennzahlen mit Verlauf (Anfragen, Abgelehnt, Hosts, Nodes, Geräte, Zertifikate), Verkehr der letzten 24 h, Dienste mit Zustand, Hinweise bei Ausfällen, Abweichungen und Anfragen; Nodes, ablaufende Zertifikate, Sperren, Ereignisse | 1 / 1.18 |
| Mehrsprachig (Deutsch, Englisch) | Sprache nach Browser, umschaltbar in der Seitenleiste und auf der Anmeldeseite; Zahlen, Daten und Länder in der gewählten Sprache; API-Fehler übersetzt; öffentliche Seiten nach Browser-Sprache, Kein-Zugang-Seite nach `Accept-Language`; Benachrichtigungen in einstellbarer Sprache. Weitere Sprachen per Übersetzungsdatei ([frontend.md](frontend.md#mehrsprachigkeit-i18n)) | 1.25 |
| Heller und dunkler Modus | Folgt der Systemeinstellung; Umschalter in der Seitenleiste (System → Hell → Dunkel), pro Browser gemerkt | 1.5 |
| Favicon | Logo als SVG-Icon für Tab und Lesezeichen | 1.5 |
