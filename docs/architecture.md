# Architektur

## Überblick

```
                Internet
                   │
     ┌─────────────┼───────────────────────────────┐
     │  Node (z. B. edge-fra)                       │
     │  ┌──────────────────────────┐                │
     │  │ Caddy                    │  :80 / :443    │
     │  │  IP-Filter → mTLS → WAF  │                │
     │  │  (Coraza) → Auth → Proxy │──► Dienste     │
     │  └────────▲─────────────────┘                │
     │           │ Admin-API (nur lokal)            │
     │  ┌────────┴─────────┐                        │
     │  │ Tesseract-Agent  │                        │
     │  └────────┬─────────┘                        │
     └───────────┼──────────────────────────────────┘
                 │ ausgehende mTLS-Verbindung (auch hinter NAT)
     ┌───────────▼──────────────────────────────────┐
     │ Controller (dieses Repo)                      │
     │  FastAPI  ── API /api/*                       │
     │  Svelte-UI ── ausgeliefert unter /            │
     │  SQLite · CA (Zwischenzertifikat) · Backups   │
     └───────────────────────────────────────────────┘
```

### Komponenten

| Komponente | Technik | Aufgabe |
|---|---|---|
| **Controller** | Python 3.13, FastAPI, uv | Single Source of Truth: Hosts, Personen, Geräte, Freigaben, CA, Versionen, Audit. Erzeugt die Caddy-Config für jeden Node. |
| **Web-UI** | Svelte 5, Vite, TypeScript | Verwaltungsoberfläche; wird als statischer Build vom Controller ausgeliefert. |
| **Caddy** | Caddy 2 + `coraza-caddy` + DNS-Module | Reverse Proxy, ACME, mTLS-Prüfung, WAF. |
| **Agent** (ab Phase 4) | Python | Läuft auf jedem Node, hält die Verbindung zum Controller, spielt Config über die lokale Caddy-Admin-API ein, liefert Status, Logs, Metriken. |

Der Caddy im selben Compose-Netz ist der Node `local`: Der Controller spricht direkt mit seiner
Admin-API (`TESSERACT_CADDY_ADMIN_URL`). Alle weiteren Nodes (ab Phase 4) haben einen Agent,
der sich ausgehend beim Controller meldet und die Config abholt – siehe
[Nodes mit Agent](#nodes-mit-agent-phase-4) und [agent.md](agent.md).

## Weg einer Anfrage

1. **IP-Filter** – gesperrte IPs / Nur-erlauben-Listen (Client-IP ggf. aus vertrauenswürdigem Proxy)
2. **TLS + mTLS** – bei privaten Hosts wird ein Client-Zertifikat der Tesseract-CA verlangt
3. **Coraza WAF** – OWASP CRS, je nach Modus protokollieren oder blockieren
4. **Authelia** (optional, pro Host) – Caddy `forward_auth` an eine bestehende Authelia-Instanz.
   Reine Middleware für Hosts: Tesseract erzeugt nur die Caddy-Direktive, Nutzer und
   Zwei-Faktor verwaltet Authelia. Die Tesseract-Oberfläche nutzt diese Middleware **nicht**
   und hat ihre eigene Anmeldung (optionales Admin-SSO per OIDC steht im Backlog).
5. **Reverse Proxy** zum Ziel

## Sicherheitsmodell

- **Eigene PKI:** Root-CA (ECDSA P-384) liegt offline und wird nur zum Signieren neuer
  Zwischenzertifikate gebraucht. Das Geräte-Zwischenzertifikat liegt verschlüsselt auf dem
  Controller und signiert Geräte-, Admin- und Node-Zertifikate.
- **Ein Gerät = ein Zertifikat.** Rechte hängen an Personen/Gruppen, nicht an Geräten; ein
  verlorenes Gerät wird einzeln gesperrt.
- **Admin-UI doppelt geschützt:** Admin-Gerätezertifikat (mTLS) + Passwort/Passkey.
  Passwort-Reset nur lokal per CLI.
- **Einzige öffentliche Fläche ohne Zertifikat:** die Einladungsseite (Rate-Limits!).
- **Einladung:** Link + separat übermittelter Bestätigungscode + Freigabe durch den Admin.
- **Nodes:** Agent verbindet sich ausgehend per mTLS (Node-Zertifikat vom Zwischenzertifikat,
  zusätzlich Agent-Token); die Caddy-Admin-API ist nie öffentlich.
- **Audit-Log:** append-only, Einträge über Prüfsummen verkettet.

## mTLS in Caddy (umgesetzt in Phase 2)

| Fall | TLS-Richtlinie (per SNI) | HTTP-Ebene |
|---|---|---|
| Ganzer Host geschützt, „Verbindung ablehnen“ | `require_and_verify` + Leaf-Verifier mit allen freigegebenen Geräte-Zertifikaten → gesperrte Geräte scheitern im Handshake | zusätzlich Fingerabdruck-Prüfung |
| Ganzer Host geschützt, „Hinweisseite“ | `verify_if_given` | ohne freigegebenes Zertifikat 403 + Hinweisseite |
| Öffentlicher Host mit geschützten Pfaden | `verify_if_given` | nur die Pfade verlangen ein freigegebenes Zertifikat (403) |
| Geschützter Host mit öffentlichen Pfaden | `verify_if_given` | alles außer den Pfaden verlangt ein Zertifikat |

- Vertrauensanker ist das Geräte-Zwischenzertifikat (`trusted_ca_certs`); dazu immer eine
  leere Catch-all-Richtlinie für alle übrigen Hosts.
- Die Freigabeliste = aktive Geräte nicht gesperrter Personen, die direkt oder über eine
  Gruppe freigegeben sind. Sie wird bei jedem neuen, gesperrten oder abgelaufenen Gerät und
  jeder Änderung an Personen/Gruppen neu erzeugt und übertragen. Eine CRL ist dadurch nicht nötig.
- Geschützte Hosts werden auf Port 80 immer auf HTTPS umgeleitet.
- Pfade werden von Caddys `path`-Matcher verglichen (ohne Groß-/Kleinschreibung, normalisiert);
  `/admin` deckt automatisch `/admin/*` ab.
- Schlüssel der Geräte erzeugt der Controller beim Ausstellen und liefert sie als `.p12`
  mit Einmal-Passwort aus – gespeichert wird nur das Zertifikat.

## Coraza WAF (Phase 3)

- Pro Host `off` / `detect` (nur protokollieren) / `block`, Paranoia-Level 1–4,
  Regel-Ausnahmen (`SecRuleRemoveById`). Neue Hosts übernehmen die Standards aus
  Einstellungen › Integrationen (Werkseinstellung: nur protokollieren, Level 1).
- Erzeugte Direktiven: `coraza.conf-recommended` + OWASP CRS (im Modul eingebaut),
  `SecResponseBodyAccess Off` (kein Puffern der Antworten), Paranoia per `tx.blocking_paranoia_level`.
- Reihenfolge im Host: Zertifikats-Sperre → WAF → WebSocket-Sperre → Kompression → Proxy.
- Treffer schreibt das Modul als `WAF rule violation detected` mit `client_ip` und `hostname`
  ins Caddy-Log – Grundlage für die Auto-Sperre.

## IP-Filter und Proxys (Phase 3)

- Pro Host `off` / `block` / `allow` mit einzelnen IPs/Netzen und benannten IP-Listen
  (werden beim Erzeugen aufgelöst). Der Filter ist die erste Route im Host – noch vor
  Zertifikats-Sperre und WAF. Leere „Nur erlauben“-Liste wird abgelehnt.
- Caddy-Matcher `client_ip`: berücksichtigt `X-Forwarded-For` nur von **vertrauenswürdigen
  Proxys** (`trusted_proxies` am Server, z. B. Liste „Cloudflare“ aus der Vorlage).
- Ändert sich eine Liste, werden alle Nodes neu übertragen; benutzte Listen lassen sich
  nicht löschen.

## Authelia als Host-Middleware (Phase 3)

- Einstellungen › Integrationen: Adresse der Authelia-Instanz (vom Node aus) und die
  Header, die an den Dienst gehen (Standard `Remote-User`, `-Groups`, `-Email`, `-Name`).
- Pro Host „Login über Authelia“ → Caddy-`forward_auth` an `/api/authz/forward-auth`
  (Authelia ≥ 4.38). Bei 2xx werden die Header übernommen – vorher immer gelöscht, damit
  ein Client sie nicht fälschen kann; sonst geht Authelias Antwort (Login-Weiterleitung)
  an den Browser. Ist Authelia nicht erreichbar, bleibt der Host zu (502), ohne Adresse 503.
- Reihenfolge: IP-Filter → Zertifikat → WAF → Authelia → Dienst.
- Die Tesseract-Oberfläche nutzt Authelia nicht (Admin-SSO steht im Backlog).

## Zertifikate per DNS-01 (Phase 3)

- Pro Host Prüfung `http` (HTTP-01, Port 80) oder `dns` (DNS-01 über Cloudflare).
  Wildcard-Hosts (`*.beispiel.de`) gehen nur mit DNS-01 und werden **nach** den konkreten
  Namen geroutet.
- Der Cloudflare-API-Token (Recht „Zone · DNS · Bearbeiten“) liegt AES-GCM-verschlüsselt in
  den Einstellungen, wird nie ausgeliefert, im Audit-Log nur als „geändert“ vermerkt und in
  `GET /api/nodes/{id}/config` geschwärzt. In die an Caddy übertragene Config muss er im Klartext.
- Eine eigene ACME-Richtlinie je Prüfart; die Let's-Encrypt-E-Mail gilt für beide.

## Host-Bereiche (Phase 3)

- Ein Bereich = Pfade (z. B. `/api`, `/admin`) mit abweichenden Regeln; jede Einstellung
  ist „wie Host“ (`null`) oder überschrieben: Zugriff (öffentlich / Zertifikat mit eigenen
  Freigaben), WAF-Modus + zusätzliche Ausnahmen, Authelia an/aus, IP-Filter.
- Caddy: pro Bereich eine Route mit `path`-Matcher und einer vollständigen eigenen Kette
  (IP → Zertifikat → WAF → Authelia → Dienst) vor der Kette des Hosts; der erste passende
  Bereich gewinnt (Reihenfolge im UI).
- Bereiche mit „öffentlich“ machen einen geschützten Host weich (`verify_if_given`), Bereiche
  mit Zertifikat lassen auch einen öffentlichen Host nach Zertifikaten fragen. Für den
  Handshake zählen alle Geräte, die irgendwo auf dem Host durchdürfen.
- Die einfachen „Pfad-Ausnahmen“ aus Phase 2 bleiben für den Alltag; Bereiche sind die
  ausführliche Variante.

## Auto-Sperre (Phase 3)

- Caddy schreibt WAF-Treffer (Logger `http.handlers.waf`, Level ERROR) als JSON in eine
  eigene Datei (`TESSERACT_CADDY_WAF_LOG`, im Compose-Stack `/var/log/tesseract/waf.log`,
  Rechte 0644, Rotation bei 10 MB). Der Controller liest dieselbe Datei über ein gemeinsames
  Volume (`TESSERACT_WAF_LOG_PATH`) alle 5 Sekunden weiter.
- Pro IP werden Treffer im Zeitfenster gezählt; ab der Schwelle (Standard 20 in 10 Min.) wird
  die IP für die eingestellte Dauer (Standard 24 h) gesperrt – außer sie liegt in den
  Ausnahmen (Standard: localhost). Sperren laufen automatisch ab.
- Gesperrte IPs stehen als eine `client_ip`-Route **nach** der Controller-Route und vor allen
  Hosts – so sperrt sich der Admin nicht von der Oberfläche aus.
- Von Hand sperren/entsperren: `POST /api/bans`, `DELETE /api/bans/{id}`.
- Die Agents liefern die Treffer der anderen Nodes (`POST /api/agent/waf`, gepuffert).

## Interne Dienste (Phase 3b)

- Schalter **„Nur aus internen Netzen“** pro Host (kombinierbar mit „Nur mit Zertifikat“).
  Die internen Netze (LAN, VPN) stehen zentral unter Einstellungen › Integrationen.
- Erste Route im Host: `not remote_ip <interne Netze>` → `static_response` mit `abort` –
  Fremde bekommen keine Antwort, auch auf Port 80 nicht. `remote_ip` ist die echte
  Verbindungs-IP; `X-Forwarded-For` zählt hier bewusst nicht.
- Zertifikat: öffentliche Namen nur mit DNS-01 (der Host ist von außen nicht erreichbar);
  interne Namen (`.lan`, `.home.arpa`, `.home`, `.internal` …) bekommen eins aus Caddys
  eigener CA – deren Root muss dann auf den Geräten vertraut werden.
- Netz-Voraussetzungen (Doku): Split-DNS – der interne DNS-Server zeigt auf die LAN-IP des
  Proxys; bei NAT-Loopback über den Router kann sonst die Router-IP als Absender ankommen;
  bei Docker-Portfreigaben prüfen, dass Caddy die echte Client-IP sieht.

## Geteilte Wildcard-Zertifikate (Phase 3b)

- Unter Einstellungen › Integrationen eingetragene Wildcards (z. B. `*.home.beispiel.de`)
  holt Caddy per DNS-01 (`tls.certificates.automate` + eigene ACME-Richtlinie) – auch ohne
  eigenen Host.
- Hosts genau eine Ebene darunter stehen in `automatic_https.skip_certificates` und bekommen
  kein Einzelzertifikat; Caddy liefert für ihren Namen das Wildcard-Zertifikat aus
  (am echten Caddy geprüft). Deren Namen erscheinen so nicht in den CT-Logs.
- Nur mit hinterlegtem Cloudflare-Token; interne Hosts mit öffentlichem Namen sind
  damit auch ohne eigenes DNS-01 möglich.

## Zertifikatsübersicht (Phase 3b)

- Caddys Admin-API listet verwaltete Zertifikate nicht auf. Der Controller baut deshalb pro
  Host (plus Controller-Domain und je Wildcard ein Beispielname) eine TLS-Verbindung zu
  Caddy auf (`TESSERACT_CADDY_TLS_ADDRESS`, sonst Host der Admin-URL mit Port 443) und liest
  das ausgelieferte Zertifikat – auch bei strengem mTLS (TLS 1.3 liefert das
  Server-Zertifikat vor der Client-Prüfung) und bei internen Hosts (Abbruch erst danach).
- Gruppiert nach Fingerabdruck: Namen, Aussteller (Let's Encrypt, ZeroSSL, Caddy-CA …),
  Laufzeit, Prüfart, nutzende Hosts. Status „läuft bald ab“ unter 21 Tagen (Caddy erneuert
  ~30 Tage vorher); Caddys lokale CA ist absichtlich kurzlebig und zählt nicht.
- Ergebnis 5 Minuten zwischengespeichert, „Neu prüfen“ erzwingt das Auslesen.
- `GET /api/certificates[?refresh=true]`

## Eigene Zertifikate (Phase 3b)

- Hochladen von Zertifikat (PEM, mit Kette) und unverschlüsseltem Schlüssel; geprüft wird,
  dass der Schlüssel zum Zertifikat passt. Der Schlüssel liegt AES-GCM-verschlüsselt in der DB
  und wird nie ausgeliefert; in der Config-Anzeige geschwärzt.
- Pro Host wählbar. Caddy bekommt das Zertifikat per `tls.certificates.load_pem` mit Tag
  `tesseract-custom-<id>`, eine TLS-Richtlinie per SNI mit `certificate_selection.any_tag`,
  und der Host steht in `skip_certificates` (kein automatisches Zertifikat).
- „Erneuern“ ersetzt Zertifikat und Schlüssel und überträgt sofort; benutzte Zertifikate
  lassen sich nicht löschen. Die Übersicht kennzeichnet sie als „Eigenes · Name“.

## Nodes mit Agent (Phase 4)

- `nodes.kind`: `local` (Controller lädt per Admin-API) oder `agent`. Für Agent-Nodes merkt
  sich „Übertragen“ nur den Soll-Stand (`desired_hash`); der Agent holt ihn per Long-Polling
  ab (`GET /api/agent/config`, bis 25 s). Das braucht keine eingehende Verbindung zum Node
  und keine WebSockets durch Proxys.
- Beitritt: Token (SHA-256 in der DB, 30 Min., einmalig) → CSR des Agents → Bestätigung durch
  den Admin → Zertifikat `node:<name>` (EKU clientAuth, 2 Jahre) + Agent-Token, beides einmal
  abholbar. Node-Zertifikate stehen in keiner Freigabeliste.
- Authentifizierung: Caddy prüft das Client-Zertifikat auf der Controller-Domain
  (`verify_if_given`, Zwischenzertifikat) und reicht den Fingerabdruck weiter; der Controller
  vergleicht ihn **und** das Agent-Token. `/api/agent/*` gehört zu den Pfaden, die auch bei
  geschützter Oberfläche ohne Admin-Zertifikat erreichbar sind.
- Config für Agent-Nodes ohne Route der Controller-Domain; die Admin-Adresse meldet der Agent
  (`admin_listen`).
- Abweichung: `applied_hash` (geladen) vs. `running_hash` (läuft in Caddy, `GET /config/` –
  am echten Caddy geprüft: gleiche Prüfsumme wie die geladene Config). Bei Abweichung wird die
  laufende Config gespeichert und als Pfad-Diff (mit Host) angezeigt. Überschreiben =
  `force_seq + 1`, Übernehmen = `accepted_hash`. Den lokalen Node prüft der Controller alle 30 s.
- Module: Probe-Caddyfiles über `POST /adapt` – der Adapter scheitert, wenn ein Modul fehlt.
- WAF-Treffer der Agents laufen in dieselbe Auto-Sperre (`app.state.autoban`) wie die des
  lokalen Caddy; Sperren gehen an alle Nodes.

## Offene Entscheidungen

| Thema | Optionen | Notiz |
|---|---|---|
| Datenbank / ORM | SQLite + SQLModel oder SQLAlchemy 2 + Alembic | SQLite reicht für den Controller, Backup einfach. |
| Log-Speicher | SQLite, DuckDB oder externe Lösung (Loki) | Abhängig vom erwarteten Volumen. |
| Admin-Passkey | WebAuthn zusätzlich/alternativ zum Passwort | Design zeigt „per Passkey“ im Audit-Log. |
