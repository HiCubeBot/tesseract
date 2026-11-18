<!--
  Einstellungen · Benachrichtigungen
  Aus dem Design-Canvas „Caddy Control“ übernommen (SettingsNotify.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Benachrichtigungen';
      const tabs = [
        ['Allgemein', '#/settings'], ['Integrationen', '#/settings-integrations'], ['Zertifizierungsstelle', '#/settings-ca'],
        ['Benachrichtigungen', '#/settings-notify'], ['Metriken', '#/settings-metrics'], ['Backup', '#/settings-backup']
      ].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 42px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (label === active ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const pill = (fg, bg) => 'padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const mono = "font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #C9CED8; overflow-wrap: anywhere;";
      const channels = [
        { name: 'ntfy (Push)', target: 'https://ntfy.beispiel.de/tesseract', badge: 'aktiv', on: true, action: 'Bearbeiten' },
        { name: 'E-Mail', target: 'SMTP noch nicht eingerichtet', badge: 'aus', on: false, action: 'Einrichten' },
        { name: 'Webhook', target: '[WEBHOOK-URL] · JSON', badge: 'aktiv', on: true, action: 'Bearbeiten' }
      ].map((c) => ({
        ...c,
        badgeStyle: c.on ? pill('#7FD9AC', 'rgba(76,195,138,.12)') : pill('#A0A7B4', '#232833'),
        targetStyle: c.on ? mono : 'font-size: 12px; color: #A0A7B4;',
        cardStyle: 'display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;' + (c.on ? '' : ' opacity: 0.8;')
      }));
      const L = {
        krit: pill('#F59A90', 'rgba(240,113,103,.14)'),
        warn: pill('#F0BE6E', 'rgba(229,164,67,.14)'),
        akt: pill('#C9C1FF', 'rgba(139,124,246,.16)'),
        info: pill('#A0A7B4', '#232833')
      };
      const label = { krit: 'kritisch', warn: 'Warnung', akt: 'Aktion nötig', info: 'Info' };
      const events = [
        ['Node offline', 'krit', 1, 0, 1],
        ['Host-Zertifikat: Erneuerung fehlgeschlagen', 'krit', 1, 1, 1],
        ['Backup fehlgeschlagen', 'krit', 1, 1, 1],
        ['Config-Abweichung auf einem Node', 'warn', 1, 0, 1],
        ['Viele abgewiesene Verbindungen', 'warn', 1, 0, 1],
        ['Anmeldung von neuem Admin-Gerät', 'warn', 1, 1, 0],
        ['Gerät wartet auf Freigabe', 'akt', 1, 0, 0],
        ['Geräte-Zertifikat läuft bald ab', 'info', 1, 0, 0],
        ['Einladung angenommen', 'info', 1, 0, 0],
        ['IP automatisch gesperrt (WAF)', 'info', 0, 0, 1]
      ].map(([name, lv, a, b, c]) => ({
        name, level: label[lv], levelStyle: L[lv],
        c1: !!a, c2: !!b, c3: !!c,
        a1: name + ' per ntfy', a2: name + ' per E-Mail', a3: name + ' per Webhook'
      }));
      return { tabs, channels, events };
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
<p style="margin: 0; color: #A0A7B4;">Wohin Tesseract meldet, wenn etwas passiert.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Speichern</button>
</header>

<nav aria-label="Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>

<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">

<section aria-label="Kanäle" style="flex: 1 1 330px; min-width: 0; display: flex; flex-direction: column; gap: 10px;">
{#each dcv.channels as c}
<div style={c.cardStyle}>
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<span style="font-weight: 600;">{c.name}</span>
<span style={c.badgeStyle}>{c.badge}</span>
</div>
<span style={c.targetStyle}>{c.target}</span>
<div style="display: flex; gap: 8px;">
<button type="button" style="flex: 1; min-height: 36px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">{c.action}</button>
<button type="button" style="flex: 1; min-height: 36px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">Test senden</button>
</div>
</div>
{/each}
<div style="display: flex; flex-direction: column; gap: 4px; padding: 12px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<label style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; cursor: pointer;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Ruhezeit 22–7 Uhr</span><span style="font-size: 12px; color: #A0A7B4;">nachts nur kritische Meldungen</span></span>
<input type="checkbox" role="switch" checked style="width: 20px; height: 20px; margin: 0; accent-color: #8B7CF6;">
</label>
<label style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; border-top: 1px solid #1E222B; cursor: pointer;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Gleiche Meldungen bündeln</span><span style="font-size: 12px; color: #A0A7B4;">höchstens 1× pro 15 Minuten</span></span>
<input type="checkbox" role="switch" checked style="width: 20px; height: 20px; margin: 0; accent-color: #8B7CF6;">
</label>
</div>
</section>

<section aria-labelledby="ev-title" style="flex: 999 1 560px; min-width: 0; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<h2 id="ev-title" style="margin: 0; padding: 14px 18px 4px; font-size: 15px; font-weight: 600;">Was wird wohin gemeldet?</h2>
<table style="width: 100%; min-width: 560px; border-collapse: collapse;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px;">
<th scope="col" style="padding: 10px 18px; font-weight: 600;">Ereignis</th>
<th scope="col" style="padding: 10px 12px; font-weight: 600;">Stufe</th>
<th scope="col" style="padding: 10px 12px; font-weight: 600; text-align: center;">ntfy</th>
<th scope="col" style="padding: 10px 12px; font-weight: 600; text-align: center;">E-Mail</th>
<th scope="col" style="padding: 10px 18px 10px 12px; font-weight: 600; text-align: center;">Webhook</th>
</tr>
</thead>
<tbody>
{#each dcv.events as e}
<tr style="border-top: 1px solid #1E222B;">
<td style="padding: 8px 18px; font-weight: 500;">{e.name}</td>
<td style="padding: 8px 12px;"><span style={e.levelStyle}>{e.level}</span></td>
<td style="padding: 8px 12px; text-align: center;"><input type="checkbox" aria-label={e.a1} checked={e.c1} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;"></td>
<td style="padding: 8px 12px; text-align: center;"><input type="checkbox" aria-label={e.a2} checked={e.c2} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;"></td>
<td style="padding: 8px 18px 8px 12px; text-align: center;"><input type="checkbox" aria-label={e.a3} checked={e.c3} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;"></td>
</tr>
{/each}
</tbody>
</table>
</section>

</div>
</main>
</div>
