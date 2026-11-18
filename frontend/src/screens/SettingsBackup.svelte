<!--
  Einstellungen · Backup
  Aus dem Design-Canvas „Caddy Control“ übernommen (SettingsBackup.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Backup';
      const tabs = [
        ['Allgemein', '#/settings'], ['Integrationen', '#/settings-integrations'], ['Zertifizierungsstelle', '#/settings-ca'],
        ['Benachrichtigungen', '#/settings-notify'], ['Metriken', '#/settings-metrics'], ['Backup', '#/settings-backup']
      ].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 42px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (label === active ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const stats = [
        { label: 'Letzte Sicherung', value: 'heute 03:00', sub: 'erfolgreich · 2,4 MB · 2 Ziele', c: '#7FD9AC' },
        { label: 'Nächste Sicherung', value: 'morgen 03:00', sub: 'täglich', c: '#E7E9EE' },
        { label: 'Letzter Wiederherstellungstest', value: 'vor 23 Tagen', sub: 'monatlich empfohlen · jetzt testen', c: '#F0BE6E' }
      ].map((s) => ({ ...s, valueStyle: 'font-size: 18px; font-weight: 700; color: ' + s.c + ';' }));
      const parts = [
        { label: 'Hosts, Personen, Geräte, Zugriffe', hint: 'die komplette Konfiguration', on: true, fixed: true },
        { label: 'Verlauf aller Hosts', hint: 'für Zurücksetzen nach einer Wiederherstellung', on: true },
        { label: 'Audit-Log', hint: 'mit Prüfsummen-Kette', on: true },
        { label: 'Schlüssel der Zwischenzertifikate', hint: 'ohne sie können keine Geräte mehr ausgestellt werden', on: true },
        { label: 'Metrik-Verlauf', hint: 'liegt meist sowieso in Prometheus', on: false }
      ].map((p) => ({ ...p, on: !!p.on, fixed: !!p.fixed }));
      const targets = [
        { name: 'Lokal', where: '/var/lib/tesseract/backups', note: 'auf dem Controller selbst – schützt nicht vor Hardware-Ausfall', on: true },
        { name: 'S3-kompatibel', where: '[BUCKET-URL]', note: 'z. B. MinIO auf dem NAS oder ein externer Anbieter', on: true },
        { name: 'Git-Spiegel der Configs', where: '[REPO-URL]', note: 'nach jeder Übertragung, unverschlüsselt ohne Schlüssel und Tokens', on: false }
      ].map((t) => ({
        ...t, state: t.on ? 'aktiv' : 'aus',
        cardStyle: 'display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border-radius: 10px; background: #0E1014; border: 1px solid ' + (t.on ? '#2E3440' : '#232833') + ';'
      }));
      const dot = (c) => 'width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: ' + c + ';';
      const restore = 'min-height: 34px; padding: 0 10px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 12px; cursor: pointer;';
      const backups = [
        ['heute 03:00', '2,4 MB · lokal + S3', true],
        ['gestern 03:00', '2,4 MB · lokal + S3', true],
        ['15.11. 03:00', '2,3 MB · lokal + S3', true],
        ['14.11. 03:00', 'S3 nicht erreichbar · nur lokal', false],
        ['13.11. 03:00', '2,3 MB · lokal + S3', true]
      ].map(([when, detail, ok]) => ({
        when, detail,
        dotStyle: dot(ok ? '#4CC38A' : '#E5A443'),
        dlLabel: 'Sicherung vom ' + when + ' herunterladen',
        restoreStyle: restore
      }));
      return { tabs, stats, parts, targets, backups };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="settings" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 14px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Einstellungen</h1>
<p style="margin: 0; color: #A0A7B4;">Sicherungen des Controllers. Nodes brauchen keine – sie bekommen ihre Config vom Controller.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Jetzt sichern</button>
</header>

<nav aria-label="Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>

<section aria-label="Status" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
{#each dcv.stats as s}
<div style="display: flex; flex-direction: column; gap: 3px; padding: 12px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="font-size: 12px; color: #A0A7B4;">{s.label}</span>
<span style={s.valueStyle}>{s.value}</span>
<span style="font-size: 12px; color: #A0A7B4;">{s.sub}</span>
</div>
{/each}
</section>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; align-items: start;">

<section aria-labelledby="what-title" style="display: flex; flex-direction: column; gap: 4px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="what-title" style="margin: 0 0 4px; font-size: 15px; font-weight: 600;">Zeitplan &amp; Inhalt</h2>
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 6px;">
<label style="display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #A0A7B4;">Zeitplan
<select style="min-height: 38px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 13px;"><option>Täglich 03:00</option><option>Stündlich</option><option>Wöchentlich</option></select>
</label>
<label style="display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #A0A7B4;">Behalten
<select style="min-height: 38px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 13px;"><option>14 Sicherungen</option><option>30 Sicherungen</option></select>
</label>
</div>
{#each dcv.parts as p}
<label style="display: flex; align-items: center; gap: 10px; min-height: 40px; border-top: 1px solid #1E222B; cursor: pointer;">
<input type="checkbox" checked={p.on} disabled={p.fixed} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">{p.label}</span><span style="font-size: 12px; color: #A0A7B4;">{p.hint}</span></span>
</label>
{/each}
<div style="display: flex; gap: 10px; padding: 10px 12px; margin-top: 4px; border-radius: 8px; background: #0E1014; font-size: 12px; color: #A0A7B4; line-height: 1.45;">Der Root-Schlüssel ist nie enthalten – er liegt offline. Alles wird mit deiner Passphrase verschlüsselt (gesetzt · <a href="#">ändern</a>).</div>
</section>

<section aria-labelledby="where-title" style="display: flex; flex-direction: column; gap: 10px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="where-title" style="margin: 0; font-size: 15px; font-weight: 600;">Ziele</h2>
{#each dcv.targets as t}
<div style={t.cardStyle}>
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<span style="font-weight: 600;">{t.name}</span>
<label style="display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: #A0A7B4; cursor: pointer;">{t.state}<input type="checkbox" role="switch" checked={t.on} aria-label={t.name} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;"></label>
</div>
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #C9CED8; overflow-wrap: anywhere;">{t.where}</span>
<span style="font-size: 12px; color: #A0A7B4;">{t.note}</span>
</div>
{/each}
</section>

<section aria-labelledby="list-title" style="display: flex; flex-direction: column; gap: 4px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="list-title" style="margin: 0 0 4px; font-size: 15px; font-weight: 600;">Sicherungen</h2>
{#each dcv.backups as b}
<div style="display: flex; align-items: center; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style={b.dotStyle}></span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column;">
<span style="font-weight: 500;">{b.when}</span>
<span style="font-size: 12px; color: #A0A7B4;">{b.detail}</span>
</span>
<button type="button" aria-label={b.dlLabel} style="width: 34px; height: 34px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; cursor: pointer; display: inline-flex; align-items: center; justify-content: center;"><svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10l5 5l5-5M5 20h14"></path></svg></button>
<button type="button" style={b.restoreStyle}>Wiederherstellen</button>
</div>
{/each}
<span style="font-size: 12px; color: #A0A7B4; line-height: 1.45; margin-top: 4px;">Wiederherstellen ersetzt den Stand des Controllers. Die Nodes bekommen danach automatisch die passende Config.</span>
</section>

</div>
</main>
</div>
