# Changelog

Alle wichtigen Änderungen. Format nach [Keep a Changelog](https://keepachangelog.com/de/),
Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Upgrade-Hinweise:
[docs/operations.md](docs/operations.md#aktualisieren-upgrade-pfad).

## [1.26.4] – 2026-11-25

### Behoben
- **Handy fragt nicht nach dem Zertifikat („Empty Response“ von unterwegs):** Über HTTP/3
  (QUIC) schicken Browser keine Client-Zertifikate und zeigen auch keine Auswahl. Wo das
  Zertifikat nur optional abgefragt wird (Oberfläche, Hinweisseite, intern ohne Zertifikat),
  kam die Anfrage so still ohne Zertifikat an und wurde von außen abgebrochen. Sobald ein Host
  Client-Zertifikate abfragt, spricht Caddy jetzt nur HTTP/1.1 und HTTP/2.
- Log-Ansicht: zeigt das Protokoll (HTTP/1.1, 2 oder 3) einer Anfrage.

## [1.26.3] – 2026-11-25

### Behoben
- **Zugriff per Gerätezertifikat von unterwegs:** Mit `TESSERACT_ADMIN_NETWORKS` brach Caddy
  auch für Personen mit „Zugriff auf Tesseract“ jede Verbindung von außerhalb ab („Empty
  Response“, z. B. über mobile Daten). Ihre Geräte sind jetzt ausgenommen – erkannt am
  Fingerabdruck des Zertifikats. Für alle anderen, auch die Passwort-Anmeldung, gelten die
  Admin-Netze weiter.

## [1.26.2] – 2026-11-25

### Behoben
- **Neues Gerät kommt trotz Freigabe nicht durch:** Hatte ein Gerät einen Host schon einmal ohne
  Zertifikat geöffnet (z. B. die Kein-Zugang-Seite), nahm der Browser diese TLS-Sitzung bei jeder
  neuen Verbindung wieder auf – ohne Zertifikat, auch nachdem eins installiert war. Erst ein
  Neuladen der Caddy-Config (z. B. Freigabe entfernen und wieder hinzufügen) half. Betroffen
  waren Hosts mit Hinweisseite, „aus internen Netzen ohne Zertifikat“ oder öffentlichen Pfaden.
  Jetzt schaltet Tesseract die TLS-Sitzungswiederaufnahme ab, sobald ein Host Zertifikate
  abfragt, und schließt die Verbindung nach einer Ablehnung („Kein Zugang“) – die nächste
  Anfrage startet mit Zertifikat.

## [1.26.1] – 2026-11-25

### Behoben
- **QR-Codes nicht scanbar:** Das SVG hatte eine feste Größe ohne `viewBox` – beim Verkleinern
  schnitt der Browser rechts und unten ab. Jetzt skalierbar mit Ruhezone von 4 Modulen, scharfen
  Kanten und etwas größer (Zertifikat aufs Handy 200 px, Einladung 180 px).

## [1.26.0] – 2026-11-25

### Geändert
- **Profil statt Knopfleiste:** Unten in der Seitenleiste stehen nur noch zwei Knöpfe – Profil
  und Abmelden. Die neue Seite Profil (`#/profile`) zeigt das Konto und stellt Sprache
  (Wie Browser, Deutsch, English) und Farbschema (Wie System, Hell, Dunkel) ein; für Admins mit
  Links zu Passwort und Passkeys. Auch für Personen, die per Gerätezertifikat angemeldet sind.

## [1.25.1] – 2026-11-25

### Hinzugefügt
- **Geräte entsperren:** Gesperrte Geräte lassen sich unter Geräte wieder freigeben – das
  bisherige Zertifikat gilt dann wieder für alle Freigaben (Audit `device_unrevoked`). Nicht
  möglich, solange die Person gesperrt ist oder ihr Geräte-Kontingent voll ist.

### Behoben
- Geräteliste: „Zertifikat“ steht jetzt bei jedem nicht gesperrten Gerät. Ohne hinterlegte Kopie
  (vor 1.22 ausgestellt oder „Aufbewahren“ aus) bietet der Knopf an, ein neues auszustellen.
- Nodes: „Node hinzufügen“ war doppelt vorhanden – jetzt nur noch oben.
- Statistik › Karte: Der Tooltip zeigt bei „Alle“ „… Anfragen“ statt „… abgelehnt“, bei
  „Angenommen“ „… angenommen“.
- Übersetzung: Auswahl Alle/Abgelehnt/Angenommen, „unbegrenzt“ und der leere Kartentext.

## [1.25.0] – 2026-11-25

### Hinzugefügt
- **Mehrsprachigkeit** ([#31](https://github.com/HiCubeBot/tesseract/issues/31)): Die Oberfläche
  gibt es auf Deutsch und Englisch. Die Sprache folgt dem Browser und lässt sich in der
  Seitenleiste (DE/EN) und auf der Anmeldeseite umschalten; Zahlen, Daten und Ländernamen in der
  gewählten Sprache. Fehlermeldungen der API, Ereignisse und Metriken werden mit übersetzt.
- Öffentliche Seiten (Einladung, Verlängern, Statusseite) folgen der Browser-Sprache; die
  Kein-Zugang-Seite von Caddy kommt nach `Accept-Language` auf Deutsch oder Englisch.
- Benachrichtigungen (ntfy, E-Mail, Webhook) in einstellbarer Sprache: Einstellungen ›
  Benachrichtigungen › „Sprache der Meldungen“.
- Für Entwickler: Texte über `t('…')` mit Deutsch als Schlüssel, Übersetzungen in
  `frontend/src/lib/i18n/en.json`; `npm run check` meldet neue feste Texte und fehlende
  Übersetzungen ([docs/frontend.md](docs/frontend.md#mehrsprachigkeit-i18n)).

## [1.24.0] – 2026-11-25

### Hinzugefügt
- **Zugriff auf Tesseract für einzelne Personen – nur per mTLS**
  ([#33](https://github.com/HiCubeBot/tesseract/issues/33)): Unter Nutzer › Person ›
  „Zugriff auf Tesseract“ die Rolle wählen – Lesen, Eigene Dienste oder Admin (Standard: kein
  Zugriff). Die Person öffnet die Oberfläche dann von jedem ihrer aktiven Geräte, ohne Passwort
  und Login-Formular. Der Controller erkennt Gerät → Person → Rolle bei jeder Anfrage; gesperrte
  oder abgelaufene Geräte verlieren den Zugriff sofort. Rechte zentral geprüft (Positivliste),
  die Oberfläche zeigt nur, was die Rolle darf.
- „Eigene Dienste“ sieht nur freigegebene Hosts (Statistik, Verlauf); neue Seite „Mein Zugang“
  mit Rolle, eigenen Geräten und freigegebenen Diensten.
- Audit-Log zeigt Person und Gerät statt „admin“, z. B. `Anna (iPhone)`.
- Mit „Oberfläche nur mit Admin-Zertifikat“ lässt Caddy auch die Geräte dieser Personen durch.
- `/api/auth/me` liefert Rolle, Person und Gerät; Migration 0030

## [1.23.0] – 2026-11-25

### Hinzugefügt
- **robots.txt pro Host** ([#32](https://github.com/HiCubeBot/tesseract/issues/32)): Caddy
  beantwortet `/robots.txt` selbst, noch vor Zertifikat und WAF – der Dienst muss nichts tun.
  Unter Hosts › Sicherheit › robots.txt: Alles erlauben, Alles verbieten, KI-Crawler verbieten
  (Suchmaschinen bleiben erlaubt), Nur bestimmte Pfade sperren oder eigener Text mit
  Syntaxprüfung und Vorschau; optional `Sitemap:`. „robots.txt des Dienstes übernehmen“ lädt
  die Datei vom Ziel als Startpunkt.
- Einstellungen › Allgemein › robots.txt: Standard für neue Hosts, Liste der KI-Crawler und
  „Hosts nur mit Zertifikat: alles verbieten“ (Standard an – mTLS-Hosts ohne eigene Einstellung
  liefern `Disallow: /` statt der Kein-Zugang-Seite).
- Docker-Label `tesseract.robots` (`off`, `allow`, `deny`, `deny-ai`); Migration 0029

## [1.22.1] – 2026-11-25

### Behoben
- **Fehler 421 beim Seitenwechsel:** Mit einem Wildcard-Zertifikat schicken Browser Anfragen an
  Tesseract manchmal über eine noch offene Verbindung eines anderen Hosts. Caddy weist das bei
  Client-Zertifikaten mit 421 (Misdirected Request) ab – zu Recht, sonst ließe sich mTLS
  umgehen –, und die Browser versuchen es nicht von selbst erneut. Die Oberfläche wiederholt
  solche Anfragen jetzt automatisch über eine eigene Verbindung; F5 ist nicht mehr nötig.

## [1.22.0] – 2026-11-24

### Hinzugefügt
- **Gerätezertifikate später erneut abrufen:** Die `.p12` neuer und verlängerter Geräte samt
  Passwort wird verschlüsselt aufbewahrt. Unter Geräte › „Zertifikat“ lässt sie sich jederzeit
  wieder herunterladen, das Passwort anzeigen oder die Kopie löschen (Audit-Log vermerkt jeden
  Abruf). Abschaltbar unter Einstellungen › Zertifizierungsstelle; Ausschalten löscht alle
  Kopien, gesperrte Geräte verlieren ihre sofort. Geräte von vor 1.22 haben keine Kopie –
  einmal „Verlängern“
- **Aufs Handy per QR-Code:** Nach dem Ausstellen, Verlängern oder Abrufen erzeugt „Aufs Handy
  (QR-Code)“ einen Download-Link (15 Minuten, höchstens 3 Abrufe, ohne Passwort im Link) – mit
  der Kamera scannen, die `.p12` landet direkt auf dem Handy (`/api/dl/…`); Migration 0028

## [1.21.0] – 2026-11-24

### Hinzugefügt
- **Tesseract selbst darf zugreifen:** Der Controller hat jetzt ein eigenes Client-Zertifikat aus
  der Zertifizierungsstelle (1 Jahr gültig, erneuert sich selbst, auch nach einem Wechsel des
  Zwischenzertifikats) und nutzt es für Benachrichtigungen an ntfy und Webhooks. Bei Hosts mit
  Zertifikatspflicht lässt es sich unter Zugriff freigeben („Tesseract selbst darf zugreifen“) –
  unabhängig von IP-Adresse und Docker-Netz, ohne das Docker-Netz als intern freizugeben;
  Migration 0027

## [1.20.1] – 2026-11-24

### Behoben
- **ntfy hinter Tesseract mit WAF:** Nachrichten gingen mit „403“ verloren, weil Coraza (Regel
  920340, Inhalt ohne `Content-Type`) sie blockierte. Tesseract sendet jetzt
  `Content-Type: text/plain; charset=utf-8`
- **ntfy: verständliche Fehlermeldung statt „Client error '403 Forbidden'“** – sagt, ob die
  Anmeldung fehlt, der Benutzer kein Schreibrecht auf das Thema hat (mit passendem
  `ntfy access …`-Befehl) oder die Antwort gar nicht von ntfy, sondern von einem Proxy davor kommt
- ntfy mit **Benutzer und Passwort**: im Feld „Zugangstoken“ geht jetzt auch `benutzer:passwort`
  (Basic Auth) statt eines Tokens `tk_…`

## [1.20.0] – 2026-11-23

### Geändert
- **Öffentliche Statusseite nur noch auf Wunsch:** Einstellungen › Allgemein › „Öffentliche
  Statusseite“ schaltet sie ein, **standardmäßig ist sie aus**. Solange sie aus ist, antwortet
  `/api/status` mit 404, und Caddy lässt `/status` und `/api/status` nicht an
  `TESSERACT_ADMIN_NETWORKS` bzw. dem Admin-Zertifikat vorbei. Wer die Statusseite seit 1.17
  nutzt, muss sie nach dem Update einmal einschalten

## [1.19.0] – 2026-11-23

### Hinzugefügt
- **Länder auf der Karte anklickbar:** Ein Klick auf ein Land (oder in der Länderliste) zoomt
  heran, hebt es hervor und zeigt daneben Anfragen, Abgelehnte, die häufigsten Ziele und einen
  Link zu den Log-Einträgen; Städte und Netzbetreiber dann nur für dieses Land. Erneuter Klick
  oder „×“ hebt die Auswahl auf. Die kleine Karte unter Sicherheit sowie die Länderlisten unter
  Sicherheit und in der Host-Statistik öffnen die Karte direkt mit dem Land
  (`#/stats-map?country=DE`, `GET /api/stats/geo?country=DE`)

## [1.18.0] – 2026-11-23

### Geändert
- **Übersicht überarbeitet:** Kennzahlen mit Verlauf – Anfragen und Abgelehnte der letzten
  24 Stunden (mit Vergleich zum Vortag), aktive Hosts (mit nicht erreichbaren aus dem
  Uptime-Monitor), Nodes online, freigegebene Geräte, bald ablaufende Zertifikate; jede Kachel
  führt zur passenden Seite. Verkehr der letzten 24 Stunden als Diagramm, „Dienste“ mit Zustand
  und Anfragen je Host, Hinweis bei Ausfällen, „Alles läuft“, wenn nichts zu tun ist. Lädt jede
  Minute neu; „Config erneut übertragen“ nur noch bei Nodes, die es brauchen

## [1.17.0] – 2026-11-23

### Hinzugefügt
- **Uptime-Monitor:** Tesseract prüft jede Minute, ob die Nodes verbunden sind und die Ziele der
  Hosts antworten – beim lokalen Node der Controller selbst, bei Agent-Nodes der Agent (vom
  Node aus, also auch für interne Ziele). Ein Ausfall zählt ab dem zweiten Fehlschlag in Folge;
  Beginn und Ende landen als Vorfall und im Audit-Log, neue Benachrichtigungen „Dienst nicht
  erreichbar“ / „wieder erreichbar“. Je Host abschaltbar (Allgemein › Überwachung)
- **Statistik › Betrieb:** Anfragen, Daten und Abgelehnte seit Beginn der Aufzeichnung,
  Erreichbarkeit der Nodes und Hosts der letzten 30 Tage als Tagesbalken (ohne Ausfall / unter
  30 Min. / ab 30 Min.), Zertifikate (Erneuerungen, nächste Abläufe), Rekorde (stärkster Tag,
  stärkste Stunde, meiste Daten, größte Abweisungs-Welle, schnellster und langsamster Host) und
  die letzten Ausfälle (`GET /api/monitor`, `GET /api/stats/operations`)
- **Öffentliche Statusseite** unter `https://<TESSERACT_DOMAIN>/status`: je Host wählbar („Auf der
  öffentlichen Statusseite zeigen“, mit eigenem Namen), zeigt nur Name, aktuellen Stand und die
  Erreichbarkeit der letzten 90 Tage – keine Domains oder Adressen. Ohne Anmeldung erreichbar,
  auch bei `TESSERACT_ADMIN_NETWORKS` (`GET /api/status`); Migration 0026

## [1.16.0] – 2026-11-23

### Hinzugefügt
- **Statistik › Karte:** eigener Tab mit zoombarer Weltkarte (Mausrad, Doppelklick, Ziehen,
  Pinch), nahe Punkte werden je nach Zoom zusammengefasst („Karlsruhe +8“). Daneben Ranglisten
  nach Ländern, Städten und Netzbetreibern; Filter Alle / Abgelehnt / Angenommen, Zeitraum,
  Node (`GET /api/stats/geo`)
- **Städte und Netzbetreiber:** `TESSERACT_GEOIP_AUTO=dbip-city` holt die Stadt-Datenbank,
  `+asn` zusätzlich die ASN-Datenbank von DB-IP (z. B. `dbip-city+asn`); eigene ASN-Datei mit
  `TESSERACT_GEOIP_ASN_DB`. Logs speichern Stadt, Koordinaten und Netzbetreiber (auch in
  Loki/VictoriaLogs)
- **Gesamter Zeitraum** unter Traffic & Leistung: Tesseract verdichtet jeden abgeschlossenen Tag
  zu Tageswerten je Host und Node (Anfragen, Daten, Statuscodes, Protokolle, Clients,
  Kompression, Besucher, Median) und hebt sie dauerhaft auf – auch wenn die Einzeleinträge nach
  der Aufbewahrungszeit gelöscht werden. Dazu Rekorde (`GET /api/stats/records`); Migration 0025

### Geändert
- **Sicherheit:** Kennzahlen mit Verlauf und Veränderung zum Vorzeitraum – Anfragen, Abgelehnt,
  ohne Zertifikat, von Coraza blockiert (und „nur erkannt“), vom IP-Filter, Fehlanmeldungen an
  der Oberfläche. Top abgelehnte IPs mit Stadt, Kennzeichen „eigene“ (Adressen freigegebener
  Geräte oder der eigenen Sitzung) und „intern“, „Eigene ausblenden“, direkt „Sperren“ bzw.
  „Wohin?“ für eigene Adressen
- **Traffic & Leistung:** Kennzahlen wie bei den Hosts (Anfragen, Besucher, Daten, Antwortzeit,
  Serverfehler, Kompression) mit Vorzeitraum; Diagramm wählbar je Kennzahl; Zusammensetzung nach
  Statuscodes, HTTP-Version und Clients (Browser, Apps & API, Bots); Pfade (aufgerufen, mit
  Fehlern), Browser/Apps/Bots mit Namen, Statuscodes mit Bedeutung
- Diagramme beschriften die Zeitachse je nach Breite, damit sich nichts überlappt

## [1.15.0] – 2026-11-23

### Hinzugefügt
- **Statistik pro Host:** neuer Tab „Statistik“ auf jeder Host-Seite – Anfragen, Besucher
  (verschiedene Adressen ohne Bots), ausgelieferte und empfangene Daten, Antwortzeit (Median,
  p95), Serverfehler und Anteil komprimierter Antworten, jeweils mit Veränderung zum
  Vorzeitraum und Verlaufslinie. Dazu Anfragen pro Stunde/6 Stunden/Tag mit gestricheltem
  Vorzeitraum, Abgelehnt nach Grund, Herkunft mit abgelehnten Anfragen je Land, Pfade
  (IDs und Bilder zusammengefasst) mit Fehlern und die häufigsten abgelehnten IPs zum Sperren
  (`GET /api/stats/host`)
- **Anfragen der letzten 24 Stunden in der Hostliste** mit Verlaufslinie je Host
  (`GET /api/stats/activity`)
- Logs speichern zusätzlich empfangene Bytes, HTTP-Version und die Kompression der Antwort
  (auch in Loki/VictoriaLogs); Migration 0024
- Beides funktioniert mit SQLite und mit Loki/VictoriaLogs über dieselbe Abfrageschicht

## [1.14.0] – 2026-11-23

### Hinzugefügt
- **Zahlen in der Seitenleiste:** Proxy-Hosts (ohne Entwürfe), Nutzer, gültige Geräte und
  beigetretene Nodes, aufgefrischt bei jedem Seitenwechsel (`GET /api/counts`)

### Geändert
- **Node-Übersicht als kompakte Karten:** Caddy-Version, Hosts mit Anteil öffentlicher Hosts,
  letzter Kontakt, Konfigurationsstand und die Verbindung zum Controller – Adresse aus Sicht des
  Agents und Art der Verbindung (intern, privat, Internet). „Config ansehen“, „Neu
  synchronisieren“ und ein Menü für Bearbeiten, Details, neues Token und Löschen. Darunter eine
  Kurzanleitung „Neuen Node verbinden“. Agents ab 1.14 melden ihre Controller-Adresse mit;
  Migration 0023

## [1.13.0] – 2026-11-23

### Geändert
- **Kein-Zugang-Seite überarbeitet:** Grund als Kennzeichen („403 · Gerätezertifikat“), Hinweis
  zur Einladung und zur Zertifikatsauswahl im Browser, dazu Dienst, eigene IP, Zeit,
  Verarbeitungszeit und Anfrage-ID für Rückfragen. Heller und dunkler Modus nach
  Systemeinstellung
- **README auf Englisch** (die Doku unter `docs/` bleibt deutsch)

## [1.12.0] – 2026-11-22

### Hinzugefügt
- **Aus internen Netzen ohne Zertifikat:** Bei Hosts mit „Nur mit Zertifikat“ (oder geschützten
  Pfaden) pro Host wählbar (Zugriff › „Aus internen Netzen ohne Zertifikat“). Geräte im LAN/VPN
  kommen dann ohne Client-Zertifikat durch, von außen gilt die Zertifikatspflicht weiter.
  Geprüft wird die echte Verbindungs-IP gegen die internen Netze aus Einstellungen ›
  Integrationen. Weil die IP erst nach dem Handshake bekannt ist, bekommen Fremde ohne
  Zertifikat „403 Kein Zugang“ statt eines Handshake-Abbruchs. Migration 0022

## [1.11.0] – 2026-11-22

### Geändert
- **Herkunftskarte für alle Anfragen:** Statistik › Sicherheit zeigt jetzt, woher Anfragen
  insgesamt kommen, mit Filter „Alle“, „Abgelehnt“ (orange) und „Angenommen“ (grün). Anfragen
  ohne Land (private oder lokale Adressen) werden darunter gezählt. Geht auch mit Loki und
  VictoriaLogs (`GET /api/stats/countries?which=all|denied|allowed`)

## [1.10.0] – 2026-11-21

### Hinzugefügt
- **Node-Schnittstelle und Admin-Netze:** `TESSERACT_AGENT_API_PUBLIC` (Standard `true`) nimmt
  die Schnittstelle für die Nodes (`/api/agent/…`, Installationsskript) von
  `TESSERACT_ADMIN_NETWORKS` aus – die Oberfläche bleibt aufs Heimnetz beschränkt, Nodes melden
  sich von überall. `false` beschränkt auch die Nodes. Anzeige unter Einstellungen › Allgemein
- **DNS-Eintrag für die Tesseract-Domain:** Einstellungen › Integrationen › DNS-Einträge legt
  bei Cloudflare einen CNAME oder A/AAAA für `TESSERACT_DOMAIN` an (nie über den Proxy), damit
  Nodes außerhalb des Heimnetzes den Controller finden; beim Start nachgezogen
- Neue öffentliche IPs eines Nodes ziehen die A/AAAA-Einträge seiner Hosts (und beim lokalen
  Node die der Tesseract-Domain) nach

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
