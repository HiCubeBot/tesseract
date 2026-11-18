<!--
  Statistik · Nutzung
  Aus dem Design-Canvas „Caddy Control“ übernommen (StatsUsage.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Nutzung';
      const tabs = [['Sicherheit', '#/stats'], ['Traffic & Leistung', '#/stats-traffic'], ['Nutzung', '#/stats-usage'], ['Logs', '#/logs']].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; font-weight: 500; text-decoration: none; ' + (label === active ? 'background: #2A2F3A; color: #E7E9EE;' : 'color: #A0A7B4;')
      }));
      const kpis = [
        { label: 'Aktive Personen', value: '5 von 6', sub: 'Dana hat noch kein Gerät', warn: false },
        { label: 'Aktive Geräte', value: '6 von 7', sub: 'Eriks Laptop ist gesperrt', warn: false },
        { label: 'Meistgenutzter Dienst', value: 'filme', sub: '9.880 Anfragen von 4 Personen', warn: false },
        { label: 'Auffälligkeiten', value: '2', sub: 'neuer Ort · gesperrtes Gerät versucht es', warn: true }
      ].map((k) => ({ ...k, subStyle: 'font-size: 12px; color: ' + (k.warn ? '#F0BE6E' : '#A0A7B4') + ';' }));

      const steps = ['#1C2029', '#2C2950', '#3F3880', '#5A4CB8', '#7C6BE8', '#A99DFF'];
      const ink = ['#A0A7B4', '#E7E9EE', '#E7E9EE', '#E7E9EE', '#0E1014', '#0E1014'];
      const lvl = (v) => v <= 0 ? 0 : v < 500 ? 1 : v < 1000 ? 2 : v < 2000 ? 3 : v < 3500 ? 4 : 5;
      const ramp = steps.map((c) => 'display: inline-block; width: 18px; height: 10px; border-radius: 3px; background: ' + c + ';');

      const svcs = ['fotos', 'filme', 'rezepte', 'kalender', 'dateien', 'home'];
      const data = [
        ['Anna', [4210, 2890, null, 640, 1520, 380]],
        ['Ben', [1130, 5120, 210, null, null, null]],
        ['Clara', [2380, 1460, 940, 520, null, null]],
        ['Opa', [3120, 410, null, 1080, null, 2260]],
        ['Dana', [0, 0, 0, null, null, null]]
      ];
      const people = data.map(([name, vals]) => ({
        name,
        cells: vals.map((v, i) => {
          if (v === null) return { text: '–', tip: name + ' hat keinen Zugriff auf ' + svcs[i], style: 'height: 30px; text-align: center; border-radius: 4px; border: 1px dashed #2A2F3A; color: #5E6573;' };
          const l = lvl(v);
          return {
            text: v ? v.toLocaleString('de-DE') : '0',
            tip: name + ' · ' + svcs[i] + ': ' + v.toLocaleString('de-DE') + ' Anfragen',
            style: 'height: 30px; text-align: center; border-radius: 4px; font-variant-numeric: tabular-nums; background: ' + steps[l] + '; color: ' + ink[l] + ';'
          };
        })
      }));

      const days = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
      const week = days.map((day, d) => ({
        day,
        cells: Array.from({ length: 24 }, (_, h) => {
          const weekend = d >= 5;
          let v = 0;
          if (h >= 6 && h < 8) v = 1;
          if (h >= 7 && h < 9 && !weekend) v = 2;
          if (h >= 12 && h < 14) v = weekend ? 3 : 1;
          if (h >= 17 && h < 20) v = 2;
          if (h >= 20 && h < 23) v = d === 6 ? 5 : (weekend || d === 4 ? 4 : 3);
          if (h >= 10 && h < 18 && weekend) v = Math.max(v, 3);
          if (h >= 23 || h < 1) v = 1;
          return { tip: day + ' ' + h + ':00 – Stufe ' + v + ' von 5', style: 'display: block; height: 14px; border-radius: 3px; background: ' + steps[v] + ';' };
        })
      }));

      const pill = (fg, bg) => 'padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const devices = [
        ['MacBook Air', 'Anna', 'heute 09:12', 3940, '2,1 GB', 'fotos', 'Deutschland', ''],
        ['iPhone 15', 'Anna', 'vor 2 Std.', 5700, '4,8 GB', 'filme', 'Spanien', 'Neuer Ort'],
        ['ThinkPad', 'Ben', 'heute 08:03', 2010, '9,6 GB', 'filme', 'Deutschland', ''],
        ['Pixel 8', 'Ben', 'heute 09:58', 4450, '14,2 GB', 'filme', 'Deutschland', ''],
        ['MacBook Pro', 'Clara', 'vor 3 Tagen', 5300, '3,9 GB', 'fotos', 'Österreich', ''],
        ['iPad', 'Opa', 'heute 07:30', 6870, '2,2 GB', 'fotos', 'Deutschland', ''],
        ['Laptop', 'Erik', 'gesperrt', 12, '–', 'filme', 'Deutschland', '12 abgewiesene Versuche']
      ].map(([name, person, seen, req, data, top, where, flag]) => ({
        name, person, seen, req: req.toLocaleString('de-DE'), data, top, where, flag: flag || '–',
        flagStyle: flag ? (flag === 'Neuer Ort' ? pill('#F0BE6E', 'rgba(229,164,67,.14)') : pill('#F59A90', 'rgba(240,113,103,.14)')) : 'color: #5E6573;',
        rowStyle: 'border-top: 1px solid #1E222B;' + (seen === 'gesperrt' ? ' opacity: 0.75;' : '')
      }));
      return { tabs, kpis, svcs, people, ramp, week, devices };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="stats" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 22px 32px; display: flex; flex-direction: column; gap: 14px;">

<header style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px;">
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 18px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Statistik</h1>
<nav aria-label="Ansicht" style="display: flex; gap: 4px; padding: 4px; border-radius: 10px; background: #161920; border: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>
</div>
<label><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Zeitraum</span>
<select style="min-height: 40px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Letzte 7 Tage</option><option>30 Tage</option></select>
</label>
</header>

<section aria-label="Kennzahlen" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px;">
{#each dcv.kpis as k}
<div style="display: flex; flex-direction: column; gap: 3px; padding: 12px 14px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="font-size: 12px; color: #A0A7B4;">{k.label}</span>
<span style="font-size: 22px; font-weight: 700;">{k.value}</span>
<span style={k.subStyle}>{k.sub}</span>
</div>
{/each}
</section>

<div style="display: flex; flex-wrap: wrap; gap: 14px; align-items: stretch;">

<section aria-labelledby="who-title" style="flex: 1 1 440px; min-width: 0; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px;">
<h2 id="who-title" style="margin: 0; font-size: 15px; font-weight: 600;">Wer nutzt was?</h2>
<span style="font-size: 12px; color: #A0A7B4;">Anfragen in 7 Tagen · – = kein Zugriff</span>
</div>
<div style="overflow-x: auto;">
<table style="width: 100%; min-width: 420px; border-collapse: separate; border-spacing: 3px; font-size: 12px;">
<thead>
<tr>
<th scope="col" style="padding: 2px 6px; text-align: left; font-weight: 600; color: #A0A7B4;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Person</span></th>
{#each dcv.svcs as s}
<th scope="col" style="padding: 2px 4px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 500; color: #A0A7B4;">{s}</th>
{/each}
</tr>
</thead>
<tbody>
{#each dcv.people as p}
<tr>
<th scope="row" style="padding: 2px 6px; text-align: left; font-weight: 500; white-space: nowrap;">{p.name}</th>
{#each p.cells as c}
<td title={c.tip} style={c.style}>{c.text}</td>
{/each}
</tr>
{/each}
</tbody>
</table>
</div>
<div style="display: flex; align-items: center; gap: 6px; font-size: 11px; color: #A0A7B4;">wenig
{#each dcv.ramp as r}<span style={r}></span>{/each}
viel</div>
</section>

<section aria-labelledby="when-title" style="flex: 1 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px;">
<h2 id="when-title" style="margin: 0; font-size: 15px; font-weight: 600;">Wann wird genutzt?</h2>
<span style="font-size: 12px; color: #A0A7B4;">alle privaten Dienste · Wochentag × Uhrzeit</span>
</div>
<div style="display: flex; flex-direction: column; gap: 3px;">
{#each dcv.week as w}
<div style="display: grid; grid-template-columns: 26px repeat(24, minmax(0, 1fr)); gap: 3px; align-items: center;">
<span style="font-size: 11px; color: #A0A7B4;">{w.day}</span>
{#each w.cells as c}
<span title={c.tip} style={c.style}></span>
{/each}
</div>
{/each}
<div style="display: grid; grid-template-columns: 26px repeat(4, minmax(0, 1fr)); font-size: 11px; color: #A0A7B4; margin-top: 2px;"><span></span><span>0 Uhr</span><span>6 Uhr</span><span>12 Uhr</span><span>18 Uhr</span></div>
</div>
<span style="font-size: 12px; color: #A0A7B4;">Am meisten los: Sonntag 20–22 Uhr. Opa ist der Frühaufsteher – seine Fotos-Aufrufe ab 6 Uhr.</span>
</section>

</div>

<section aria-labelledby="dev-title" style="border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<h2 id="dev-title" style="margin: 0; padding: 14px 16px 4px; font-size: 15px; font-weight: 600;">Geräte-Aktivität</h2>
<table style="width: 100%; min-width: 820px; border-collapse: collapse; font-size: 13px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px;">
<th scope="col" style="padding: 8px 16px; font-weight: 600;">Gerät</th>
<th scope="col" style="padding: 8px 10px; font-weight: 600;">Zuletzt</th>
<th scope="col" style="padding: 8px 10px; font-weight: 600; text-align: right;">Anfragen</th>
<th scope="col" style="padding: 8px 10px; font-weight: 600; text-align: right;">Daten</th>
<th scope="col" style="padding: 8px 10px; font-weight: 600;">Meistgenutzt</th>
<th scope="col" style="padding: 8px 10px; font-weight: 600;">Ort</th>
<th scope="col" style="padding: 8px 16px 8px 10px; font-weight: 600;">Auffällig</th>
</tr>
</thead>
<tbody>
{#each dcv.devices as d}
<tr style={d.rowStyle}>
<td style="padding: 7px 16px;"><span style="font-weight: 500;">{d.name}</span> <span style="color: #A0A7B4;">· {d.person}</span></td>
<td style="padding: 7px 10px; color: #A0A7B4;">{d.seen}</td>
<td style="padding: 7px 10px; text-align: right; font-variant-numeric: tabular-nums;">{d.req}</td>
<td style="padding: 7px 10px; text-align: right; font-variant-numeric: tabular-nums;">{d.data}</td>
<td style="padding: 7px 10px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">{d.top}</td>
<td style="padding: 7px 10px;">{d.where}</td>
<td style="padding: 7px 16px 7px 10px;"><span style={d.flagStyle}>{d.flag}</span></td>
</tr>
{/each}
</tbody>
</table>
</section>

</main>
</div>
