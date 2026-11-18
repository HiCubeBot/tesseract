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

In **Phase 1** gibt es noch keinen Agent: Der Controller spricht direkt mit der Admin-API des
Caddy im selben Compose-Netz (`TESSERACT_CADDY_ADMIN_URL`). Die Schnittstelle wird so gebaut,
dass sie später durch den Agent ersetzt werden kann („Node-Treiber“: lokal vs. Agent).

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
- **Nodes:** Agent verbindet sich ausgehend per mTLS; die Caddy-Admin-API ist nie öffentlich.
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

## Offene Entscheidungen

| Thema | Optionen | Notiz |
|---|---|---|
| Datenbank / ORM | SQLite + SQLModel oder SQLAlchemy 2 + Alembic | SQLite reicht für den Controller, Backup einfach. |
| Agent-Protokoll | WebSocket über mTLS vs. gRPC vs. Long-Polling | WebSocket passt zu FastAPI. |
| Log-Speicher | SQLite, DuckDB oder externe Lösung (Loki) | Abhängig vom erwarteten Volumen. |
| Admin-Passkey | WebAuthn zusätzlich/alternativ zum Passwort | Design zeigt „per Passkey“ im Audit-Log. |
