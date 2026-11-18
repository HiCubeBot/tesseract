# Tesseract

**Ein Webinterface für alle deine Caddy-Nodes** – als Alternative zum Nginx Proxy Manager (NPM),
mit **mTLS statt VPN** und eingebauter **Coraza WAF**.

- **Öffentliche Hosts** bekommen automatisch Zertifikate von Let's Encrypt – wie bei NPM.
- **Private Dienste** sind nur für freigegebene Geräte erreichbar: Jedes Gerät erhält ein eigenes
  Client-Zertifikat aus Tesseracts eigener CA. Ohne gültiges Zertifikat kommt nicht einmal der
  TLS-Handshake zustande – kein VPN-Client, keine offene Login-Seite.
- **Coraza WAF** mit OWASP Core Rule Set, IP-Filter und Auto-Sperre pro Host.
- **Mehrere Nodes** (VPS, NAS, Raspberry Pi …) werden zentral verwaltet. Jeder Node meldet sich
  per Agent beim Controller – auch hinter NAT, ohne offenen Admin-Port.
- **Einladungen per Link**: Gäste registrieren ihr Gerät selbst und installieren das Zertifikat
  mit einer Schritt-für-Schritt-Anleitung.

> Status: **Phase 3 und 3b fertig** – Proxy-Hosts mit Let's Encrypt (HTTP-01/DNS-01, Wildcards),
> eigene CA und Geräte-Zertifikate (mTLS) statt VPN, Einladungen per Link, Coraza WAF,
> IP-Filter, Auto-Sperre, Authelia als Middleware, Regeln pro Pfad, interne Dienste,
> geteilte Wildcard- und eigene Zertifikate mit Zertifikatsübersicht. Bereiche ohne Funktion
> (Nodes, Statistik, Logs …) zeigt das UI als Prototyp. Siehe [Roadmap](docs/roadmap.md).

## Projektstruktur

```
tesseract/
├─ frontend/          Svelte 5 + Vite (TypeScript) – Web-UI
├─ backend/           Python 3.13, FastAPI, verwaltet mit uv – Controller
│  ├─ src/tesseract/  Anwendungscode
│  └─ tests/          pytest
├─ docker/caddy/      Caddy-Image mit Coraza- und DNS-Modulen
├─ docs/              gesamte Dokumentation
├─ Dockerfile         Controller-Image (baut Frontend + Backend)
└─ compose.yaml       Controller + Caddy
```

## Schnellstart

### Mit Docker Compose

```bash
cp .env.example .env    # Domain und E-Mail eintragen
docker compose up -d --build
```

Danach ist das UI unter `https://<TESSERACT_DOMAIN>` erreichbar (lokal: `https://localhost`),
die API-Doku unter `/api/docs`. Das Admin-Passwort steht beim ersten Start im Log:

```bash
docker compose logs tesseract | grep "Erster Start"
```

### Entwicklung

Backend (Port 8000):

```bash
cd backend
uv sync
cp .env.example .env
uv run tesseract
```

Frontend (Port 5173, leitet `/api` an das Backend weiter):

```bash
cd frontend
npm install
npm run dev
```

Tests und Linting:

```bash
cd backend && uv run pytest && uv run ruff check .
```

## Dokumentation

Alles liegt in [`docs/`](docs/README.md):

| Dokument | Inhalt |
|---|---|
| [Features](docs/features.md) | vollständige Featureliste |
| [Roadmap](docs/roadmap.md) | Projektphasen und Meilensteine |
| [Architektur](docs/architecture.md) | Komponenten, Datenfluss, Sicherheitsmodell |
| [Backend](docs/backend.md) | FastAPI-Controller, uv, Konfiguration |
| [Frontend](docs/frontend.md) | Svelte-UI, Komponenten, Screens |
| [Deployment](docs/deployment.md) | Docker, Compose, Caddy-Image |
| [Mitarbeit](docs/contributing.md) | Git-Workflow, Branches, Pull Requests |
