# Frontend (Svelte 5 + Vite, ohne SvelteKit)

Code-Fassung des Designs **„Caddy Control“** – ein Webinterface für alle Caddy-Nodes.

Es gibt zwei Arten von Seiten:

- **Seiten (`pages/`)** – fertig an die API angebunden (ab Phase 1).
- **Prototyp-Screens (`screens/`)** – 1:1 aus dem Design, mit Beispieldaten. Sie erscheinen
  für alle Pfade, die noch keine echte Seite haben, mit einem gelben Hinweis „Prototyp“,
  und bleiben unter `#/design/<pfad>` als Referenz erreichbar.

## Starten

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (leitet /api an das Backend auf :8000 weiter)
npm run build      # statischer Build nach dist/
npm run check      # Typprüfung mit svelte-check
```

## Aufbau

```
frontend/src/
  app.css                 Design-Tokens + gemeinsame Klassen (.card, .field, .input, .table …)
  App.svelte              Anmelde-Prüfung, wählt Seite oder Prototyp-Screen
  routes.ts               echte Seiten (mit Parametern wie hosts/:id) und Prototyp-Screens
  ScreenIndex.svelte      Übersicht aller Seiten und Screens (#/screens)
  lib/
    api.ts                API-Client, Typen, Anzeige-Hilfen
    session.svelte.ts     Anmeldestatus; bei 401 zurück zum Login
    toast.svelte.ts       kurze Rückmeldungen
    hosts.ts · nodes.ts   Hilfen für Hosts und das Übertragen an Nodes
    router.svelte.ts      kleiner Hash-Router (#/hosts …), keine Abhängigkeit
    dc.svelte.ts          Brücke für die übernommene Screen-Logik (siehe unten)
    icons.ts              Strich-Icons als SVG-Pfade
    components/           wiederverwendbare Bausteine (idiomatisches Svelte 5, TypeScript),
                          u. a. ColumnChart, BarList, WorldMap (Natural Earth 1:110 Mio.,
                          gemeinfrei, über world-atlas; wird erst beim Anzeigen geladen)
  pages/                  echte Seiten: Login, Overview, Hosts, HostWizard, HostHistory, HostSecurity,
                          Certificates, Nodes, Users, Devices, Access, Settings…, Audit, Enroll
  screens/                30 Prototyp-Screens aus dem Canvas
```

### Komponenten (`frontend/src/lib/components`)

| Komponente | Zweck | Wichtige Props |
|---|---|---|
| `Sidebar` | Hauptnavigation | `active` |
| `Button` | Button oder Link | `variant` (primary/secondary/ghost/danger), `size`, `icon`, `label`, `href`, `disabled`, `onClick` |
| `StatusPill` | Status-Kennzeichen | `tone` (ok/warn/bad/mtls/neutral), `label`, `dot` |
| `AccessChip` | Gruppe/Person/Gerät in Freigaben | `kind`, `label`, `removable`, `onRemove` |
| `SegmentedControl` | Filter-Umschalter | `options`, `bind:selected`, `onChange` |
| `Toggle` | Schalter mit Beschreibung | `label`, `description`, `bind:checked` |
| `TextField` | Eingabefeld mit Hinweis/Fehler | `label`, `bind:value`, `hint`, `error`, `mono` |
| `SelectField` | Auswahlfeld | `label`, `options`, `bind:value` |
| `StatCard` | Kennzahl | `label`, `value`, `sub`, `tone`, `subTone` |
| `EventItem` | Zeile im Ereignis-Feed | `time`, `title`, `detail`, `tone` |
| `Alert` | Hinweisbanner | `tone` (info/ok/warn/bad), `title`, `text`, `actionLabel`, `actionHref` |
| `NodeCard` | Node mit Status | `nodeName`, `location`, `caddy`, `hosts`, `seen`, `status` |
| `EmptyState` | Leerer Zustand | `icon`, `title`, `text`, `actionLabel`, `actionHref` |
| `ConfirmDialog` | Bestätigung durch Eintippen | `title`, `text`, `word`, `confirmLabel`, `onConfirm`, `onCancel` |
| `PageHeader` | Seitenkopf mit Aktionen | `title`, `subtitle`, `crumb`, `primaryLabel`, `secondaryLabel` … |
| `AppShell` | Seitenrahmen mit Sidebar | `active`, Inhalt als Kinder |
| `HostForm` | Felder eines Hosts (Domain, Node, Ziel, Optionen) | `bind:value`, `nodes`, `compact` |
| `CheckList` | Ergebnis der Vorab-Prüfungen | `checks`, `busy` |
| `Toasts` | Rückmeldungen unten rechts (einmal in `App.svelte`) | – |

Alle zusammen siehst du unter **`#/kit`**.

```svelte
<script lang="ts">
  import { Button, StatusPill } from './lib/components';
</script>

<StatusPill tone="warn" label="lokal geändert" />
<Button variant="primary" icon="plus" label="Host anlegen" href="#/host-new-1" />
```

### Screens (`frontend/src/screens`)

Die Screens sind automatisch aus dem Canvas übernommen und sehen 1:1 aus wie dort.
Sie nutzen bereits `Sidebar`, haben ihre Darstellung aber noch als Inline-Styles,
und ihre Logik steckt noch in einer Klasse `Component` mit `renderVals()`.
`lib/dc.svelte.ts` macht diese Klasse reaktiv (`this.setState` → Neuzeichnen).

Beim Ausbau einer Seite empfiehlt sich:

1. Wiederkehrende Teile durch die Komponenten ersetzen (Buttons, Pills, Karten …).
2. Die Daten aus `renderVals()` in `$state`/`$derived` überführen bzw. per `fetch` von der Controller-API holen.
3. Danach Klasse und `useDC` entfernen.

## Routen

**Echte Seiten (Phase 1):** `#/login` · `#/` Übersicht · `#/hosts` · `#/hosts/new` ·
`#/hosts/:id` (Bearbeiten-Panel) · `#/hosts/:id/history` · `#/settings` · `#/audit`

Die alten Pfade `#/host-new-1..3` leiten auf `#/hosts/new` um.

**Prototyp-Screens:** `#/host-security` · `#/users` · `#/devices` · `#/access` ·
`#/invite-1..4` (+ `-3m`, `-4m` fürs Handy) · `#/nodes` · `#/stats`, `#/stats-traffic`,
`#/stats-usage`, `#/logs` · `#/settings-integrations`, `#/settings-ca`, `#/settings-notify`,
`#/settings-metrics`, `#/settings-backup` · `#/kit` – jeweils auch unter `#/design/…`,
dort auch die Originale der fertigen Seiten (z. B. `#/design/hosts`).

Alle Seiten außer `#/login` verlangen eine Anmeldung.

## Neue Seite anbinden

1. Seite unter `pages/` anlegen, `AppShell` als Rahmen, Daten über `api` aus `lib/api.ts`.
2. In `routes.ts` unter `pages` eintragen – sie hat dann Vorrang vor dem Prototyp-Screen.
3. Der Prototyp bleibt unter `#/design/<pfad>` als Vorlage erhalten.
