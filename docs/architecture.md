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

## Offene Entscheidungen

| Thema | Optionen | Notiz |
|---|---|---|
| Datenbank / ORM | SQLite + SQLModel oder SQLAlchemy 2 + Alembic | SQLite reicht für den Controller, Backup einfach. |
| Per-Host-Freigabe bei mTLS | a) Caddy `client_auth` mit Liste erlaubter Leaf-Zertifikate je Host · b) gemeinsamer CA-Pool + Matcher auf Fingerabdruck/Subject | Design deutet a) an („Liste wird ergänzt und neu übertragen“). Widerruf über Entfernen aus der Liste; Caddy hat keine native CRL-Prüfung. |
| Hinweisseite „Kein Zugang“ | `client_auth mode verify_if_given` + Matcher, sonst `require_and_verify` | Nur bei „ablehnen“ scheitert bereits der Handshake. |
| Schlüsselerzeugung auf dem Gerät | WebCrypto + CSR im Browser vs. serverseitig erzeugtes PKCS#12 / `.mobileconfig` | iOS/Android benötigen meist ein Profil/PKCS#12. |
| Agent-Protokoll | WebSocket über mTLS vs. gRPC vs. Long-Polling | WebSocket passt zu FastAPI. |
| Log-Speicher | SQLite, DuckDB oder externe Lösung (Loki) | Abhängig vom erwarteten Volumen. |
| Admin-Passkey | WebAuthn zusätzlich/alternativ zum Passwort | Design zeigt „per Passkey“ im Audit-Log. |
