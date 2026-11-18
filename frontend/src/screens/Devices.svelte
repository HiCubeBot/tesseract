<!--
  Geräte
  Aus dem Design-Canvas „Caddy Control“ übernommen (Devices.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const pill = (fg, bg) => 'display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const T = { ok: pill('#7FD9AC', 'rgba(76,195,138,.12)'), warn: pill('#F0BE6E', 'rgba(229,164,67,.14)'), bad: pill('#F59A90', 'rgba(240,113,103,.14)') };
      const laptop = 'M4 5h16v11H4zM2 19h20';
      const phone = 'M7 3h10v18H7zM11 18h2';
      const tablet = 'M5 3h14v18H5zM11 18h2';
      const devices = [
        ['MacBook Air', 'macOS', laptop, 'Anna', '3F:9A:21 … 0B:C1', '02.03.2027', 'heute 09:12', 'aktiv', 'ok'],
        ['iPhone 15', 'iOS', phone, 'Anna', 'A4:10:E8 … 77:2E', '29.11.2026', 'gestern 21:40', 'läuft in 12 Tagen ab', 'warn'],
        ['ThinkPad', 'Windows', laptop, 'Ben', '9C:44:0A … E1:5D', '14.05.2027', 'heute 08:03', 'aktiv', 'ok'],
        ['Pixel 8', 'Android', phone, 'Ben', '51:D2:7F … 3A:90', '17.11.2027', 'heute 09:58', 'aktiv', 'ok'],
        ['MacBook Pro', 'macOS', laptop, 'Clara', 'E0:3B:16 … C4:08', 'unbegrenzt (2125)', 'vor 3 Tagen', 'aktiv', 'ok'],
        ['iPad', 'iPadOS', tablet, 'Opa', '07:F1:92 … 6B:DD', '08.12.2026', 'heute 07:30', 'läuft in 21 Tagen ab', 'warn'],
        ['Laptop', 'Linux', laptop, 'Erik', 'B8:2E:4C … 11:F3', '01.06.2027', 'vor 5 Wochen', 'gesperrt', 'bad']
      ].map(([name, os, icon, person, fp, until, seen, status, t]) => ({
        name, os, icon, person, fp, until, seen, status,
        statusStyle: T[t],
        menuLabel: 'Aktionen für ' + name + ' von ' + person,
        rowStyle: 'border-top: 1px solid #232833;' + (t === 'bad' ? ' opacity: 0.65;' : '')
      }));
      const stats = [
        { label: 'Geräte gesamt', value: '7', c: '#E7E9EE' },
        { label: 'Aktiv', value: '6', c: '#7FD9AC' },
        { label: 'Laufen in 30 Tagen ab', value: '2', c: '#F0BE6E' },
        { label: 'Gesperrt', value: '1', c: '#F59A90' }
      ].map((s) => ({ ...s, valueStyle: 'font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; color: ' + s.c + ';' }));
      return { devices, stats };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="devices" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 18px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Geräte</h1>
<p style="margin: 0; color: #A0A7B4;">Ein Gerät = ein Client-Zertifikat. Es gehört immer zu genau einer Person.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: #161920; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Gesperrte Zertifikate exportieren</button>
</header>

<section aria-label="Gerätestatus" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px;">
{#each dcv.stats as s}
<div style="display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="font-size: 13px; color: #A0A7B4;">{s.label}</span>
<span style={s.valueStyle}>{s.value}</span>
</div>
{/each}
</section>

<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px;">
<label style="flex: 1 1 240px; display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 12px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #A0A7B4;">
<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M20 20l-4-4"></path></svg>
<span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Geräte durchsuchen</span>
<input type="search" placeholder="Gerät, Person oder Fingerabdruck" style="flex: 1; min-width: 0; border: none; outline: none; background: transparent; color: #E7E9EE; font: inherit;">
</label>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;">Person
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;">
<option>Alle Personen</option><option>Anna</option><option>Ben</option><option>Clara</option><option>Opa</option><option>Erik</option>
</select>
</label>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;">Status
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;">
<option>Alle</option><option>Aktiv</option><option>Läuft bald ab</option><option>Unbegrenzt gültig</option><option>Gesperrt</option>
</select>
</label>
</div>

<section aria-label="Geräteliste" style="border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<table style="width: 100%; min-width: 860px; border-collapse: collapse;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">
<th scope="col" style="padding: 12px 16px; font-weight: 600;">Gerät</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Person</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Fingerabdruck</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Gültig bis</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Zuletzt gesehen</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Status</th>
<th scope="col" style="padding: 12px 16px 12px 12px; font-weight: 600; text-align: right;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Aktionen</span></th>
</tr>
</thead>
<tbody>
{#each dcv.devices as d}
<tr style={d.rowStyle}>
<td style="padding: 10px 16px;">
<div style="display: flex; align-items: center; gap: 10px;">
<span style="width: 32px; height: 32px; border-radius: 8px; background: #232833; display: inline-flex; align-items: center; justify-content: center; color: #C9CED8; flex-shrink: 0;">
<svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d={d.icon}></path></svg>
</span>
<div style="display: flex; flex-direction: column;">
<span style="font-weight: 500;">{d.name}</span>
<span style="font-size: 12px; color: #A0A7B4;">{d.os}</span>
</div>
</div>
</td>
<td style="padding: 10px 12px;"><a href="#/users" style="font-weight: 500;">{d.person}</a></td>
<td style="padding: 10px 12px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #A0A7B4;">{d.fp}</td>
<td style="padding: 10px 12px; font-variant-numeric: tabular-nums;">{d.until}</td>
<td style="padding: 10px 12px; color: #A0A7B4;">{d.seen}</td>
<td style="padding: 10px 12px;"><span style={d.statusStyle}>{d.status}</span></td>
<td style="padding: 10px 16px 10px 12px; text-align: right;">
<button type="button" aria-label={d.menuLabel} style="width: 36px; height: 36px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; cursor: pointer; display: inline-flex; align-items: center; justify-content: center;"><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M5 12h.01M12 12h.01M19 12h.01"></path></svg></button>
</td>
</tr>
{/each}
</tbody>
</table>
</section>

</main>
</div>
