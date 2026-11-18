<!--
  Einstellungen · Zertifizierungsstelle
  Aus dem Design-Canvas „Caddy Control“ übernommen (SettingsCA.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Zertifizierungsstelle';
      const tabs = [
        ['Allgemein', '#/settings'], ['Integrationen', '#/settings-integrations'], ['Zertifizierungsstelle', '#/settings-ca'],
        ['Benachrichtigungen', '#/settings-notify'], ['Metriken', '#/settings-metrics'], ['Backup', '#/settings-backup']
      ].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 42px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (label === active ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const pill = (fg, bg) => 'padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const inters = [
        { name: 'Geräte', detail: 'signiert Geräte-Zertifikate · bis 11/2028 · 7 ausgestellt', badge: 'aktiv', t: 'ok', sel: true },
        { name: 'Admin', detail: 'signiert Admin-Geräte · bis 11/2028 · 2 ausgestellt', badge: 'aktiv', t: 'ok' },
        { name: 'Nodes', detail: 'Agent ↔ Controller · bis 11/2027 · 4 ausgestellt', badge: 'in 12 Monaten', t: 'warn' }
      ].map((c) => ({
        ...c, current: c.sel ? 'true' : 'false',
        badgeStyle: c.t === 'ok' ? pill('#7FD9AC', 'rgba(76,195,138,.12)') : pill('#F0BE6E', 'rgba(229,164,67,.14)'),
        style: 'display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 10px 14px; border-radius: 10px; text-decoration: none; ' + (c.sel ? 'background: rgba(139,124,246,.10); border: 1px solid #8B7CF6;' : 'background: #161920; border: 1px solid #232833;')
      }));
      const roll = [
        { n: '1', text: 'Root-Schlüssel kurz einstecken' },
        { n: '2', text: 'Neues Zwischenzertifikat signieren' },
        { n: '3', text: 'Beide parallel an alle Nodes verteilen' },
        { n: '4', text: 'Geräte nach und nach erneuern' }
      ];
      return { tabs, inters, roll };
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
<p style="margin: 0; color: #A0A7B4;">Die eigene CA stellt Geräte-, Admin- und Node-Zertifikate aus.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: #161920; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Root-Zertifikat herunterladen</button>
</header>

<nav aria-label="Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>

<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">

<section aria-label="Aufbau der CA" style="flex: 1 1 360px; min-width: 0; display: flex; flex-direction: column; gap: 10px;">
<div style="display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="width: 36px; height: 36px; border-radius: 9px; background: #232833; display: inline-flex; align-items: center; justify-content: center; color: #C9CED8; flex-shrink: 0;"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4"></path></svg></span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px;">
<span style="font-weight: 600;">Tesseract Root CA</span>
<span style="font-size: 12px; color: #A0A7B4;">ECDSA P-384 · bis 03/2036 · Schlüssel liegt nicht auf dem Controller</span>
</span>
<span style="padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #C9CED8; background: #232833;">offline</span>
</div>
<div style="display: flex; flex-direction: column; gap: 8px; margin-left: 18px; padding-left: 18px; border-left: 2px solid #2A2F3A;">
{#each dcv.inters as c}
<a href="#" aria-current={c.current} style={c.style}>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px;">
<span style="font-weight: 600; color: #E7E9EE;">{c.name}</span>
<span style="font-size: 12px; color: #A0A7B4;">{c.detail}</span>
</span>
<span style={c.badgeStyle}>{c.badge}</span>
</a>
{/each}
</div>
<p style="margin: 4px 0 0; font-size: 12px; color: #A0A7B4; line-height: 1.5;">Der Root-Schlüssel wird nur zum Signieren neuer Zwischenzertifikate gebraucht – zum Beispiel von einem USB-Stick – und danach nicht gespeichert.</p>
</section>

<section aria-labelledby="ca-title" style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 18px 20px; border-radius: 12px; background: #161920; border: 1px solid #3A3460;">
<div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="ca-title" style="margin: 0; font-size: 18px; font-weight: 600;">Geräte-Zwischenzertifikat</h2>
<span style="padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #7FD9AC; background: rgba(76,195,138,.12);">aktiv</span>
</div>
<dl style="margin: 0; display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: 8px 14px; font-size: 13px;">
<dt style="color: #A0A7B4;">Signiert</dt><dd style="margin: 0;">Geräte-Zertifikate aller Personen</dd>
<dt style="color: #A0A7B4;">Gültig</dt><dd style="margin: 0;">17.11.2025 – 17.11.2028</dd>
<dt style="color: #A0A7B4;">Algorithmus</dt><dd style="margin: 0;">ECDSA P-384</dd>
<dt style="color: #A0A7B4;">Fingerabdruck</dt><dd style="margin: 0; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">SHA256 5C:E1:08 … 9A:37</dd>
<dt style="color: #A0A7B4;">Schlüssel</dt><dd style="margin: 0;">verschlüsselt auf dem Controller</dd>
<dt style="color: #A0A7B4;">Ausgestellt</dt><dd style="margin: 0;">7 Geräte · 6 aktiv, 1 gesperrt</dd>
</dl>

<div style="display: flex; gap: 12px; padding: 12px 14px; border-radius: 10px; background: rgba(229,164,67,.08); border: 1px solid #5A4520;">
<span style="width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(229,164,67,.2); color: #F0BE6E; font-size: 13px; font-weight: 700;">!</span>
<span style="display: flex; flex-direction: column; gap: 3px; font-size: 13px; line-height: 1.5;">
<span style="font-weight: 600; color: #F0BE6E;">1 Gerät ist länger gültig als dieses Zwischenzertifikat</span>
<span style="color: #C9CED8;">Claras MacBook Pro („unbegrenzt“) funktioniert nur bis 11/2028. Tesseract erinnert Clara 30 Tage vorher und schickt einen Link für ein neues Zertifikat.</span>
</span>
</div>

<div style="display: flex; flex-direction: column; gap: 8px;">
<span style="font-size: 13px; font-weight: 600;">Wechsel auf ein neues Zwischenzertifikat</span>
<ol style="margin: 0; padding: 0; list-style: none; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px;">
{#each dcv.roll as r}
<li style="display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border-radius: 8px; background: #0E1014; border: 1px solid #232833;">
<span style="font-size: 12px; font-weight: 700; color: #A0A7B4;">{r.n}</span>
<span style="font-size: 13px; line-height: 1.4;">{r.text}</span>
</li>
{/each}
</ol>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Wechsel vorbereiten</button>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Zertifikat herunterladen (.pem)</button>
</div>
</section>

</div>
</main>
</div>
