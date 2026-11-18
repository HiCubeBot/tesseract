<!--
  Statistik · Traffic & Leistung
  Aus dem Design-Canvas „Caddy Control“ übernommen (StatsTraffic.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Traffic & Leistung';
      const tabs = [['Sicherheit', '#/stats'], ['Traffic & Leistung', '#/stats-traffic'], ['Nutzung', '#/stats-usage'], ['Logs', '#/logs']].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; font-weight: 500; text-decoration: none; ' + (label === active ? 'background: #2A2F3A; color: #E7E9EE;' : 'color: #A0A7B4;')
      }));
      const kpis = [
        { label: 'Anfragen', value: '1,24 Mio.', sub: '+8 % zum Vortag', c: '#A0A7B4' },
        { label: 'Daten ausgeliefert', value: '86,4 GB', sub: '3,1 GB empfangen', c: '#A0A7B4' },
        { label: 'Antwortzeit (Median)', value: '38 ms', sub: '95 % unter 412 ms', c: '#A0A7B4' },
        { label: 'Serverfehler (5xx)', value: '0,02 %', sub: '212 Anfragen · meist wiki (Node offline)', c: '#F0BE6E' },
        { label: 'Komprimiert ausgeliefert', value: '61 %', sub: 'zstd & gzip · spart rund 31 GB', c: '#A0A7B4' }
      ].map((k) => ({ ...k, subStyle: 'font-size: 12px; color: ' + k.c + ';' }));
      const hours = [];
      for (let i = 0; i < 24; i++) {
        const h = (i + 11) % 24;
        let v = 28000 + 14000 * Math.sin((h - 7) / 24 * Math.PI * 2 - 0.4) + (h >= 20 && h <= 22 ? 42000 : 0) + (h >= 1 && h <= 6 ? -18000 : 0);
        v = Math.max(6000, Math.round(v / 100) * 100);
        hours.push({
          tip: h + ':00 – ' + v.toLocaleString('de-DE') + ' Anfragen',
          style: 'flex: 1; min-width: 0; height: ' + (v / 100000 * 100).toFixed(1) + '%; background: #8B7CF6; border-radius: 4px 4px 0 0;'
        });
      }
      const bar = (pct) => 'display: block; height: 100%; width: ' + pct + '%; background: #8B7CF6; border-radius: 4px;';
      const group = (title, rows) => ({ title, items: rows.map(([label, pct, tip]) => ({ label, value: String(pct).replace('.', ',') + ' %', tip: tip || (label + ': ' + String(pct).replace('.', ',') + ' %'), barStyle: bar(pct) })) });
      const mix = [
        group('Statuscodes', [['2xx erfolgreich', 91.2], ['3xx weiterg.', 6.1], ['4xx abgelehnt', 2.7], ['5xx Fehler', 0.02]]),
        group('Protokoll', [['HTTP/3', 38], ['HTTP/2', 55], ['HTTP/1.1', 7]]),
        group('Clients', [['Browser', 72], ['Apps & API', 9], ['Bots/Crawler', 19, 'Bots/Crawler: 19 % – davon 4/5 auf blog und git']])
      ];
      const rows = [
        ['filme.beispiel.de', 512400, '61,2 GB', 24, 180, '0 %', '100 %'],
        ['fotos.beispiel.de', 288100, '18,9 GB', 41, 390, '0,01 %', '100 %'],
        ['git.beispiel.de', 160300, '3,4 GB', 62, 640, '0,03 %', '99,98 %'],
        ['blog.beispiel.de', 121800, '1,6 GB', 18, 95, '0 %', '100 %'],
        ['home.beispiel.de', 74200, '0,4 GB', 88, 1240, '0,08 %', '99,7 %'],
        ['wiki.beispiel.de', 38900, '0,7 GB', 52, 410, '0,51 %', '94,2 %']
      ];
      const maxP95 = 1240;
      const perf = rows.map(([host, req, out, p50, p95, err, up]) => {
        const bad = parseFloat(err.replace(',', '.')) > 0.05;
        return {
          host, req: req.toLocaleString('de-DE'), out, p50: p50 + ' ms', p95: p95.toLocaleString('de-DE') + ' ms', err, up,
          tip: host + ': 95 % der Antworten schneller als ' + p95 + ' ms',
          barStyle: 'display: block; height: 100%; width: ' + (p95 / maxP95 * 100).toFixed(1) + '%; background: #8B7CF6; border-radius: 4px;',
          errStyle: 'font-variant-numeric: tabular-nums; ' + (bad ? 'color: #F0BE6E; font-weight: 600;' : 'color: #E7E9EE;')
        };
      });
      return { tabs, kpis, hours, mix, perf };
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
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
<label><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Zeitraum</span>
<select style="min-height: 40px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Letzte 24 Stunden</option><option>7 Tage</option><option>30 Tage</option></select>
</label>
<label><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Node</span>
<select style="min-height: 40px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Alle Nodes</option><option>edge-fra</option><option>home-nas</option><option>pi-eltern</option></select>
</label>
</div>
</header>

<section aria-label="Kennzahlen" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px;">
{#each dcv.kpis as k}
<div style="display: flex; flex-direction: column; gap: 3px; padding: 12px 14px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="font-size: 12px; color: #A0A7B4;">{k.label}</span>
<span style="font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums;">{k.value}</span>
<span style={k.subStyle}>{k.sub}</span>
</div>
{/each}
</section>

<div style="display: flex; flex-wrap: wrap; gap: 14px; align-items: stretch;">

<section aria-labelledby="req-title" style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px;">
<h2 id="req-title" style="margin: 0; font-size: 15px; font-weight: 600;">Anfragen pro Stunde</h2>
<span style="font-size: 12px; color: #A0A7B4;">Spitze 20–22 Uhr: Filmabend auf filme.beispiel.de</span>
</div>
<div style="display: flex; gap: 6px;">
<div style="display: flex; flex-direction: column; justify-content: space-between; height: 150px; font-size: 11px; color: #A0A7B4; text-align: right; font-variant-numeric: tabular-nums;"><span>100 k</span><span>50 k</span><span>0</span></div>
<div style="flex: 1; position: relative; height: 150px; border-bottom: 1px solid #2E3440; display: flex; align-items: flex-end; gap: 3px;">
<span style="position: absolute; left: 0; right: 0; top: 0; border-top: 1px dashed #232833;"></span>
<span style="position: absolute; left: 0; right: 0; top: 50%; border-top: 1px dashed #232833;"></span>
{#each dcv.hours as h}
<span title={h.tip} style={h.style}></span>
{/each}
</div>
</div>
<div style="display: flex; justify-content: space-between; padding-left: 38px; font-size: 11px; color: #A0A7B4;"><span>11:00</span><span>17:00</span><span>23:00</span><span>05:00</span><span>jetzt</span></div>
</section>

<section aria-labelledby="mix-title" style="flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="mix-title" style="margin: 0; font-size: 15px; font-weight: 600;">Zusammensetzung</h2>
{#each dcv.mix as g}
<div style="display: flex; flex-direction: column; gap: 5px;">
<span style="font-size: 12px; color: #A0A7B4;">{g.title}</span>
{#each g.items as i}
<div title={i.tip} style="display: grid; grid-template-columns: 92px minmax(0, 1fr) 52px; align-items: center; gap: 8px; min-height: 20px;">
<span style="font-size: 12px;">{i.label}</span>
<span style="height: 8px; border-radius: 4px; background: #232833; display: flex;"><span style={i.barStyle}></span></span>
<span style="font-size: 12px; text-align: right; font-variant-numeric: tabular-nums;">{i.value}</span>
</div>
{/each}
</div>
{/each}
</section>

</div>

<section aria-labelledby="perf-title" style="border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px; padding: 14px 16px 4px;">
<h2 id="perf-title" style="margin: 0; font-size: 15px; font-weight: 600;">Hosts im Vergleich</h2>
<span style="font-size: 12px; color: #A0A7B4;">Antwortzeit = Zeit bis zur Antwort des Dienstes, gemessen am Node</span>
</div>
<table style="width: 100%; min-width: 820px; border-collapse: collapse; font-size: 13px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px;">
<th scope="col" style="padding: 9px 16px; font-weight: 600;">Host</th>
<th scope="col" style="padding: 9px 10px; font-weight: 600; text-align: right;">Anfragen</th>
<th scope="col" style="padding: 9px 10px; font-weight: 600; text-align: right;">Daten raus</th>
<th scope="col" style="padding: 9px 10px; font-weight: 600; text-align: right;">Median</th>
<th scope="col" style="padding: 9px 10px; font-weight: 600; width: 220px;">95 % schneller als</th>
<th scope="col" style="padding: 9px 10px; font-weight: 600; text-align: right;">Fehler (5xx)</th>
<th scope="col" style="padding: 9px 16px 9px 10px; font-weight: 600; text-align: right;">Erreichbar</th>
</tr>
</thead>
<tbody>
{#each dcv.perf as p}
<tr style="border-top: 1px solid #1E222B;">
<td style="padding: 8px 16px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">{p.host}</td>
<td style="padding: 8px 10px; text-align: right; font-variant-numeric: tabular-nums;">{p.req}</td>
<td style="padding: 8px 10px; text-align: right; font-variant-numeric: tabular-nums;">{p.out}</td>
<td style="padding: 8px 10px; text-align: right; font-variant-numeric: tabular-nums;">{p.p50}</td>
<td style="padding: 8px 10px;">
<span title={p.tip} style="display: grid; grid-template-columns: minmax(0, 1fr) 58px; align-items: center; gap: 8px;">
<span style="height: 8px; border-radius: 4px; background: #232833; display: flex;"><span style={p.barStyle}></span></span>
<span style="font-variant-numeric: tabular-nums; text-align: right;">{p.p95}</span>
</span>
</td>
<td style="padding: 8px 10px; text-align: right;"><span style={p.errStyle}>{p.err}</span></td>
<td style="padding: 8px 16px 8px 10px; text-align: right; font-variant-numeric: tabular-nums;">{p.up}</td>
</tr>
{/each}
</tbody>
</table>
</section>

</main>
</div>
