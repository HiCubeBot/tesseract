# Sicherheit

Stand des Sicherheits-Reviews zu Version 1.0 (Phase 6). Ergänzt das
[Sicherheitsmodell](architecture.md#sicherheitsmodell).

## Angriffsfläche

| Fläche | Erreichbar für | Schutz |
|---|---|---|
| Hosts (Ports 80/443 der Nodes) | Internet bzw. internes Netz | IP-Filter, mTLS, Coraza WAF, Authelia – pro Host |
| Oberfläche + API (Controller-Domain) | wer die Domain erreicht | Passwort (Argon2), Session-Cookie `HttpOnly`/`Secure`/`SameSite=Strict`, optional nur mit Admin-Gerätezertifikat |
| Einladungsseite `/e/…`, `/api/enroll/*` | öffentlich | Token (nur SHA-256 gespeichert), separater Bestätigungscode, Admin-Freigabe, Bremse pro IP, Rate-Limit |
| Selbst verlängern `/v`, `/api/renew` | öffentlich | Ausweis ist das gültige, nicht gesperrte Gerätezertifikat (von Caddy geprüft, Fingerabdruck per Header); nur im Zeitfenster vor Ablauf; abschaltbar; Rate-Limit 30/Min. |
| `/api/agent/*` | öffentlich | Beitritt: einmaliges Token (30 Min.) + Bestätigung mit Schlüssel-Fingerabdruck; danach Node-Zertifikat **und** Agent-Token |
| `/metrics` | öffentlich, wenn eingeschaltet | Bearer-Token, Admin-Zertifikat oder IP-Liste |
| Caddy-Admin-API | nur internes Docker-Netz | nie veröffentlicht |
| Controller-Port 8000 | nur internes Docker-Netz | nie veröffentlichen – siehe „Vertrauen in Caddy“ |

## Maßnahmen (Phase 6)

- **Rate-Limits pro IP** (zusätzlich zu den Sperren bei Fehlversuchen): Anmeldung 20/Min.,
  Einladungsseite und `/api/enroll/*` 60/Min., Beitritt von Agents 30/Min., `/metrics`
  120/Min. Antwort `429` mit `Retry-After`.
- **Echte Client-IP hinter Caddy:** Der Controller übernimmt `X-Forwarded-For` nur aus
  privaten Netzen (`TESSERACT_FORWARDED_ALLOW_IPS`). Vorher sah er nur Caddys IP – die
  Anmelde-Bremse hätte nach fünf Fehlversuchen alle ausgesperrt, und das Audit-Log zeigte die
  falsche Adresse.
- **Sicherheits-Header** auf jeder Antwort (`nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`); HTML zusätzlich mit
  strenger Content-Security-Policy (`script-src 'self'`, `frame-ancestors 'none'` …).
- **Keine externen Abrufe der Oberfläche:** Schriften (vorher Google Fonts) und Kartendaten
  liegen im eigenen Build. Die IP der Admins geht an niemanden.
- **Container gehärtet:** Controller und Agent mit schreibgeschütztem Dateisystem
  (`read_only`, Daten nur im Volume), `no-new-privileges`, alle Linux-Capabilities entfernt;
  Caddy behält nur `NET_BIND_SERVICE`. Alle Images laufen als Nicht-Root-Nutzer (außer Caddy,
  das Ports 80/443 öffnet).
- **Abhängigkeiten** ohne bekannte Schwachstellen (`pip-audit`, `npm audit`), die CI prüft
  das bei jedem Push.

## Geheimnisse

| Was | Wo | Wie |
|---|---|---|
| Root-Schlüssel der CA | offline beim Admin | nie auf dem Controller, nur kurz beim CA-Wechsel entschlüsselt |
| Schlüssel des Zwischenzertifikats, Cloudflare-/ntfy-/S3-Token, SMTP-Passwort, Backup-Passphrase | DB | AES-256-GCM mit dem Hauptschlüssel (`secret.key` bzw. `TESSERACT_SECRET_KEY`) |
| Admin-Passwort | DB | Argon2id |
| Session-, Einladungs-, Agent-, Metrik-Token | DB | nur SHA-256 |
| Sicherungen | Ziel (lokal, S3) | AES-256-GCM, Schlüssel per scrypt aus der Passphrase, Kopf authentifiziert |
| Git-Spiegel | Git-Repository | **unverschlüsselt**, aber ohne Geheimnisse und Personen; Token/SSH-Schlüssel verschlüsselt in der DB, an `git` nur über Umgebung bzw. kurzlebige Datei (0600) |
| Schlüssel der Geräte (`.p12` + Passwort) | DB, wenn „Zertifikate aufbewahren“ an ist (Standard) | AES-256-GCM mit dem Hauptschlüssel; Abruf nur angemeldet und im Audit-Log, Download-Link 15 Min./3 Abrufe ohne Passwort; gesperrt = gelöscht. Ausgeschaltet: einmal ausgeliefert, nie gespeichert |
| Client-Zertifikat des Controllers | DB + `<data>/controller-client/` (0600) | Schlüssel in der DB mit dem Hauptschlüssel verschlüsselt |

## Vertrauen in Caddy (bewusst)

Der Controller vertraut zwei Angaben von Caddy: dem Fingerabdruck des Client-Zertifikats
(`X-Tesseract-Client-Fingerprint`) und der Client-IP (`X-Forwarded-For`). Caddy überschreibt
beide Header bei jeder Anfrage. Wer den Controller-Port **direkt** erreicht, könnte sie
fälschen – deshalb bleibt Port 8000 im internen Docker-Netz (so in `compose.yaml`).
Seit 1.24 hängt daran auch die Anmeldung von Personen per Gerätezertifikat
([anmeldung.md](anmeldung.md#personen-per-gerätezertifikat)) – umso wichtiger, dass der Port
nicht von außen erreichbar ist.

## Bekannte Grenzen

- Server-seitige Anfragen an vom Admin eingetragene Adressen (Erreichbarkeit des Ziels,
  Authelia-Test, Webhook, S3, ntfy) sind gewollt und nur für angemeldete Admins möglich.
- Abgelehnte TLS-Handshakes (strenges mTLS) erscheinen nicht in den Logs.
- Fragt ein Host Client-Zertifikate ab, ist die TLS-Sitzungswiederaufnahme (Session Tickets)
  aus: Eine ohne Zertifikat begonnene Sitzung würde sonst ohne Zertifikat fortgesetzt, und ein
  neu installiertes Gerätezertifikat käme nicht an. Jede neue Verbindung macht daher einen
  vollständigen Handshake; nach „Kein Zugang“ schließt Caddy die Verbindung.
- Aus demselben Grund ist dann HTTP/3 aus: Über QUIC schicken Browser keine Client-Zertifikate.
  Caddy spricht in dem Fall nur HTTP/1.1 und HTTP/2 – für alle Hosts dieses Nodes.
- Sobald ein Host Client-Zertifikate nutzt, prüft Caddy streng, dass SNI und Host-Header
  übereinstimmen (`strict_sni_host`), sonst ließe sich mTLS über die Verbindung eines offenen
  Hosts umgehen. Browser verwenden bei Wildcard-Zertifikaten aber Verbindungen anderer Hosts
  weiter und bekommen dann 421 (Misdirected Request). Das bleibt bewusst so; die Oberfläche
  wiederholt solche Anfragen selbst. Bei anderen Diensten hinter Tesseract kann vereinzelt
  eine 421-Seite erscheinen – ein Neuladen hilft.
- Admin-Anmeldung per Passwort, Passkey oder SSO (OIDC) – siehe [anmeldung.md](anmeldung.md).
  Passwort-Anmeldung lässt sich abschalten.

## Sicherheitslücken melden

Bitte nicht als öffentliches Issue, sondern über „Report a vulnerability“
(GitHub Security Advisories) im Repository.
