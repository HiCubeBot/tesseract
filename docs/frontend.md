# Frontend (Svelte 5 + Vite, ohne SvelteKit)

Code-Fassung des Designs **„Caddy Control“** – ein Webinterface für alle Caddy-Nodes.

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
  app.css                 Design-Tokens (Farben, Schrift, Radien) als CSS-Variablen
  App.svelte              wählt anhand der URL den Screen
  routes.ts               alle Screens mit Pfad und Titel
  ScreenIndex.svelte      Übersicht aller Screens (#/screens)
  lib/
    router.svelte.ts      kleiner Hash-Router (#/hosts …), keine Abhängigkeit
    dc.svelte.ts          Brücke für die übernommene Screen-Logik (siehe unten)
    icons.ts              Strich-Icons als SVG-Pfade
    components/           wiederverwendbare Bausteine (idiomatisches Svelte 5, TypeScript)
  screens/                30 Screens aus dem Canvas
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

`#/` Übersicht · `#/login` · `#/hosts` · `#/host-security` · `#/host-history` · `#/host-new-1..3` ·
`#/users` · `#/devices` · `#/access` · `#/invite-1..4` (+ `-3m`, `-4m` fürs Handy) · `#/nodes` ·
`#/stats`, `#/stats-traffic`, `#/stats-usage`, `#/logs` · `#/audit` ·
`#/settings`, `#/settings-integrations`, `#/settings-ca`, `#/settings-notify`, `#/settings-metrics`, `#/settings-backup` ·
`#/kit` · `#/screens`

Alle Daten sind Beispieldaten aus dem Mockup – es gibt noch kein Backend.
