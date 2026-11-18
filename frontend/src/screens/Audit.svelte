<!--
  Audit-Log
  Aus dem Design-Canvas „Caddy Control“ übernommen (Audit.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const cats = ['Alle', 'Zugriff', 'Hosts', 'Personen & Geräte', 'Nodes', 'Anmeldung'].map((label, i) => ({
        label, pressed: i === 0 ? 'true' : 'false',
        style: 'min-height: 36px; padding: 0 12px; border-radius: 7px; border: none; font: inherit; font-size: 13px; font-weight: 500; cursor: pointer; ' + (i === 0 ? 'background: #2A2F3A; color: #E7E9EE;' : 'background: transparent; color: #A0A7B4;')
      }));
      const C = {
        'Zugriff': ['#C9C1FF', 'rgba(139,124,246,.16)'],
        'Abgewiesen': ['#F59A90', 'rgba(240,113,103,.14)'],
        'Hosts': ['#7FD9AC', 'rgba(76,195,138,.12)'],
        'Geräte': ['#F0BE6E', 'rgba(229,164,67,.14)'],
        'Personen': ['#F0BE6E', 'rgba(229,164,67,.14)'],
        'Nodes': ['#A9C7F5', 'rgba(110,160,240,.14)'],
        'Anmeldung': ['#C9CED8', '#232833']
      };
      const kinds = {
        admin: { initials: 'AD', style: 'background: #2A2F3A; color: #E7E9EE;' },
        guest: { initials: 'G', style: 'background: rgba(139,124,246,.22); color: #D6D0FF;' },
        system: { initials: 'S', style: 'background: #1C2029; color: #A0A7B4; border: 1px solid #2E3440;' }
      };
      const rows = [
        ['10:42:07', 'System', 'system', 'Abgewiesen', 'Unbekanntes Zertifikat', 'fotos.beispiel.de · 203.0.113.42 via home-nas'],
        ['10:24:51', 'Dana', 'guest', 'Geräte', 'Gerät registriert', 'Danas iPhone · wartet auf Freigabe'],
        ['10:20:13', 'Dana', 'guest', 'Personen', 'Einladung geöffnet', 'Link 7KQ2-XM9P'],
        ['10:15:30', 'System', 'system', 'Nodes', 'Config übertragen', 'home-nas · Version 142 · 3 Änderungen'],
        ['10:14:58', 'admin', 'admin', 'Zugriff', 'Zugriff geändert', 'fotos.beispiel.de · + Ben', true],
        ['10:05:02', 'admin', 'admin', 'Personen', 'Person eingeladen', 'Dana · Gruppe Freunde'],
        ['09:58:40', 'System', 'system', 'Geräte', 'Zertifikat ausgestellt', 'Pixel 8 von Ben · bis 17.11.2027'],
        ['09:31:12', 'System', 'system', 'Nodes', 'Node offline', 'vps-hel · kein Kontakt seit 5 Min.'],
        ['09:02:19', 'admin', 'admin', 'Anmeldung', 'Angemeldet', 'Passkey · ThinkPad · 192.0.2.10'],
        ['gestern 21:04', 'System', 'system', 'Nodes', 'Abweichung erkannt', 'pi-eltern · home.beispiel.de'],
        ['gestern 18:40', 'admin', 'admin', 'Geräte', 'Gerät gesperrt', 'Laptop von Erik']
      ].map(([time, actor, kind, cat, action, target, sel]) => ({
        time, actor, cat, action, target,
        actorInitials: kinds[kind].initials,
        actorStyle: 'width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; ' + kinds[kind].style,
        catStyle: 'display: inline-block; min-width: 76px; text-align: center; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; color: ' + C[cat][0] + '; background: ' + C[cat][1] + ';',
        rowStyle: 'border-top: 1px solid #232833;' + (sel ? ' background: rgba(139,124,246,.08); box-shadow: inset 3px 0 0 #8B7CF6;' : '')
      }));
      return { cats, rows };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="audit" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 16px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Audit-Log</h1>
<p style="margin: 0; color: #A0A7B4;">Jede Änderung und jeder abgewiesene Zugriff – wer, wann, was. Einträge lassen sich nicht bearbeiten oder löschen.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: #161920; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Als CSV exportieren</button>
</header>

<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
<label style="flex: 1 1 220px; display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 12px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #A0A7B4;">
<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M20 20l-4-4"></path></svg>
<span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Log durchsuchen</span>
<input type="search" placeholder="Person, Gerät, Host, IP …" style="flex: 1; min-width: 0; border: none; outline: none; background: transparent; color: #E7E9EE; font: inherit;">
</label>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;">Zeitraum
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Letzte 24 Stunden</option><option>7 Tage</option><option>30 Tage</option></select>
</label>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;">Wer
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Alle</option><option>Admin</option><option>Gäste</option><option>System</option></select>
</label>
<div role="group" aria-label="Kategorie" style="display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 10px; background: #161920; border: 1px solid #232833;">
{#each dcv.cats as c}
<button type="button" aria-pressed={c.pressed} style={c.style}>{c.label}</button>
{/each}
</div>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">

<section aria-label="Einträge" style="flex: 999 1 600px; min-width: 0; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<table style="width: 100%; min-width: 720px; border-collapse: collapse;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">
<th scope="col" style="padding: 11px 16px; font-weight: 600;">Zeit</th>
<th scope="col" style="padding: 11px 12px; font-weight: 600;">Wer</th>
<th scope="col" style="padding: 11px 12px; font-weight: 600;">Aktion</th>
<th scope="col" style="padding: 11px 16px 11px 12px; font-weight: 600;">Betrifft</th>
</tr>
</thead>
<tbody>
{#each dcv.rows as r}
<tr style={r.rowStyle}>
<td style="padding: 9px 16px; font-variant-numeric: tabular-nums; color: #A0A7B4; white-space: nowrap;">{r.time}</td>
<td style="padding: 9px 12px;">
<span style="display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;"><span style={r.actorStyle}>{r.actorInitials}</span>{r.actor}</span>
</td>
<td style="padding: 9px 12px;">
<span style="display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;"><span style={r.catStyle}>{r.cat}</span><span style="font-weight: 500;">{r.action}</span></span>
</td>
<td style="padding: 9px 16px 9px 12px; color: #C9CED8;">{r.target}</td>
</tr>
{/each}
</tbody>
</table>
</section>

<aside aria-labelledby="detail-title" style="flex: 1 1 320px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 18px 20px; border-radius: 12px; background: #161920; border: 1px solid #3A3460;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<span style="font-size: 12px; color: #A0A7B4;">Heute, 10:14:58</span>
<h2 id="detail-title" style="margin: 0; font-size: 17px; font-weight: 600;">Zugriff geändert</h2>
</div>
<dl style="margin: 0; display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 8px 12px; font-size: 13px;">
<dt style="color: #A0A7B4;">Wer</dt><dd style="margin: 0;">admin · per Passkey</dd>
<dt style="color: #A0A7B4;">Von</dt><dd style="margin: 0;">ThinkPad (Admin-Gerät)</dd>
<dt style="color: #A0A7B4;">IP</dt><dd style="margin: 0; font-family: 'JetBrains Mono', ui-monospace, monospace;">192.0.2.10</dd>
</dl>
<div style="display: flex; flex-direction: column; gap: 6px;">
<span style="font-size: 13px; color: #A0A7B4;">Änderung</span>
<div style="border-radius: 8px; background: #0B0D10; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.7; padding: 8px 0;">
<div style="padding: 0 12px; color: #C9CED8;">fotos.beispiel.de · freigegeben für</div>
<div style="padding: 0 12px; color: #C9CED8;">  Gruppe Familie</div>
<div style="padding: 0 12px; color: #7FD9AC; background: rgba(76,195,138,.10);">+ Ben (direkt) · 2 Geräte</div>
</div>
</div>
<div style="display: flex; flex-direction: column; gap: 6px;">
<span style="font-size: 13px; color: #A0A7B4;">Folge</span>
<a href="#/nodes" style="font-size: 13px; font-weight: 500;">Config an home-nas übertragen · 10:15:30</a>
</div>
<div style="display: flex; flex-direction: column; gap: 4px; padding-top: 12px; border-top: 1px solid #232833;">
<span style="font-size: 12px; color: #A0A7B4;">Prüfsumme (verkettet mit vorherigem Eintrag)</span>
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #C9CED8;">sha256 9e41…c07a</span>
</div>
</aside>

</div>
</main>
</div>
