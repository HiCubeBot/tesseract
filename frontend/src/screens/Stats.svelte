<!--
  Statistik · Sicherheit
  Aus dem Design-Canvas „Caddy Control“ übernommen (Stats.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const C = { mtls: '#8B7CF6', waf: '#14A399', ip: '#CF7D45' };
      const key = (c) => 'display: inline-block; width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; background: ' + c + ';';
      const fmt = (n) => n.toLocaleString('de-DE');
      const kpis = [
        { label: 'Anfragen', value: '1,24 Mio.', sub: '3 von 4 Nodes liefern Logs', c: '#5E6573' },
        { label: 'Abgelehnt gesamt', value: fmt(18430), sub: '1,5 % aller Anfragen', c: '#A0A7B4' },
        { label: 'Ohne Zertifikat', value: fmt(9112), sub: 'mTLS-Handshake abgelehnt', c: C.mtls },
        { label: 'Von Coraza blockiert', value: fmt(6204), sub: '2 IPs automatisch gesperrt', c: C.waf },
        { label: 'Vom IP-Filter', value: fmt(3114), sub: 'davon 71 % Liste „Scanner“', c: C.ip }
      ].map((k) => ({ ...k, keyStyle: key(k.c) }));

      // Grobe Landmaske: 64 Spalten (5,625° Länge) x 28 Zeilen (5° Breite, 80° N bis 55° S)
      const R = [
        [[14,19],[21,28],[34,35],[43,49]],
        [[11,18],[19,28],[34,34],[42,42],[48,52]],
        [[4,7],[8,19],[22,27],[35,37],[37,63]],
        [[3,7],[7,20],[23,25],[28,28],[34,37],[37,63]],
        [[4,7],[7,14],[18,20],[24,24],[33,37],[37,61]],
        [[9,14],[18,21],[31,31],[34,39],[39,60]],
        [[9,22],[31,32],[33,39],[39,57],[60,60]],
        [[10,20],[32,34],[35,39],[40,55],[57,57]],
        [[10,18],[30,32],[34,35],[36,40],[41,53],[57,57]],
        [[11,18],[31,33],[38,42],[42,53],[56,56]],
        [[11,17],[30,37],[38,41],[42,53]],
        [[12,14],[17,17],[29,38],[38,42],[44,48],[49,53]],
        [[13,16],[17,18],[29,38],[39,41],[45,47],[49,51]],
        [[15,16],[29,39],[40,40],[45,46],[49,51],[53,53]],
        [[17,17],[19,21],[29,39],[45,45],[49,50],[54,54]],
        [[18,23],[30,40],[50,50],[52,52]],
        [[18,23],[33,39],[49,53]],
        [[18,25],[34,39],[51,51],[53,53],[55,55],[57,57]],
        [[18,25],[34,39],[57,57]],
        [[18,25],[34,39],[40,40],[55,57]],
        [[19,24],[34,38],[40,40],[52,58]],
        [[19,24],[34,37],[52,59]],
        [[19,23],[35,37],[52,59]],
        [[19,22],[35,35],[53,58]],
        [[19,21],[57,57],[63,63]],
        [[19,20],[62,62]],
        [[19,19]],
        [[19,19]]
      ];
      const land = [];
      R.forEach((ranges, r) => ranges.forEach(([a, b]) => {
        for (let c = a; c <= b; c++) {
          land.push('position: absolute; width: 3px; height: 3px; border-radius: 50%; background: #343A47; left: calc(' + ((c + 0.5) / 64 * 100).toFixed(2) + '% - 1.5px); top: calc(' + ((r + 0.5) / 28 * 100).toFixed(2) + '% - 1.5px);');
        }
      }));
      const pos = (lat, lon) => ({ x: (lon + 180) / 360 * 100, y: (80 - lat) / 140 * 100 });
      const origins = [
        ['Deutschland', 51, 10, 3960, 'meist ohne Zertifikat'],
        ['China', 35, 105, 2140, 'IP-Filter & WAF'],
        ['USA', 39, -98, 1810, 'WAF'],
        ['Niederlande', 52, 5, 1420, 'WAF (VPS-Scanner)'],
        ['Russland', 56, 38, 1180, 'WAF'],
        ['Singapur', 1, 104, 610, 'WAF'],
        ['Brasilien', -15, -48, 540, 'WAF'],
        ['Indien', 21, 78, 470, 'WAF'],
        ['Vietnam', 16, 107, 390, 'IP-Filter']
      ];
      const spots = origins.map(([name, lat, lon, n, why]) => {
        const p = pos(lat, lon);
        const d = Math.round(8 + Math.sqrt(n / 4000) * 30);
        return {
          tip: name + ': ' + fmt(n) + ' abgelehnt · ' + why,
          style: 'position: absolute; width: ' + d + 'px; height: ' + d + 'px; left: calc(' + p.x.toFixed(2) + '% - ' + (d / 2) + 'px); top: calc(' + p.y.toFixed(2) + '% - ' + (d / 2) + 'px); border-radius: 50%; background: rgba(139,124,246,.55); box-shadow: 0 0 0 2px #161920; cursor: default;'
        };
      });
      const spotLabels = origins.slice(0, 5).map(([name, lat, lon, n]) => {
        const p = pos(lat, lon);
        const below = name === 'Niederlande';
        return {
          text: name + ' ' + fmt(n),
          style: 'position: absolute; left: calc(' + p.x.toFixed(2) + '% + ' + (below ? -40 : 14) + 'px); top: calc(' + p.y.toFixed(2) + '% ' + (below ? '- 28px' : '- 7px') + '); font-size: 11px; color: #E7E9EE; white-space: nowrap; pointer-events: none;'
        };
      });

      const ips = [
        ['203.0.113.17', 'Niederlande', 'WAF', 1204, 'gesperrt', 'waf'],
        ['198.51.100.23', 'USA', 'WAF', 860, 'Sperren', 'waf'],
        ['192.0.2.77', 'China', 'Liste „Scanner“', 731, 'gesperrt', 'ip'],
        ['203.0.113.92', 'Deutschland', 'ohne Zertifikat', 512, 'Sperren', 'mtls'],
        ['198.51.100.140', 'Russland', 'WAF', 488, 'Sperren', 'waf']
      ].map(([ip, where, reason, n, action, k]) => ({
        ip, where, reason, count: fmt(n), action,
        keyStyle: key(C[k]),
        actionStyle: action === 'gesperrt'
          ? 'min-width: 64px; text-align: center; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; color: #A0A7B4; background: #232833;'
          : 'min-width: 64px; text-align: center; padding: 6px 8px; border-radius: 7px; font-size: 12px; font-weight: 500; color: #E7E9EE; border: 1px solid #2E3440; cursor: pointer;'
      }));

      const legend = [['Ohne Zertifikat', C.mtls], ['WAF', C.waf], ['IP-Filter', C.ip]].map(([label, c]) => ({ label, keyStyle: key(c) }));
      const max = 1500;
      const seg = (v, c, top) => 'display: block; width: 100%; height: ' + (v / max * 100).toFixed(2) + '%; background: ' + c + '; border-radius: ' + (top ? '4px 4px 0 0' : '0') + ';' + (v ? '' : ' display: none;');
      const hours = [];
      for (let i = 0; i < 24; i++) {
        const m = 300 + Math.round(120 * Math.sin(i / 3.2) + (i % 5) * 18);
        const w = 180 + Math.round(90 * Math.cos(i / 2.1)) + (i === 19 ? 520 : 0) + (i === 20 ? 260 : 0);
        const p = 90 + ((i * 37) % 70);
        hours.push({
          tip: (i + 11) % 24 + ':00 – ohne Zertifikat ' + m + ', WAF ' + w + ', IP-Filter ' + p,
          ipStyle: seg(p, C.ip, true),
          wafStyle: seg(w, C.waf, false),
          mtlsStyle: seg(m, C.mtls, false)
        });
      }

      const rules = [
        ['Scanner-Erkennung', '913', 2104], ['Path Traversal / LFI', '930', 1380], ['SQL-Injection', '942', 1122],
        ['Protokollverstöße', '920', 906], ['Cross-Site-Scripting', '941', 452], ['Befehlsausführung', '932', 240]
      ].map(([label, id, n]) => ({
        label, value: fmt(n), tip: 'OWASP CRS ' + id + 'xxx · ' + label + ': ' + fmt(n),
        barStyle: 'display: block; height: 100%; width: ' + (n / 2104 * 100).toFixed(1) + '%; background: ' + C.waf + '; border-radius: 0 4px 4px 0;'
      }));

      const hostMax = 4640;
      const part = (v, c, last) => 'display: ' + (v ? 'block' : 'none') + '; height: 100%; width: ' + (v / hostMax * 100).toFixed(1) + '%; background: ' + c + '; border-radius: ' + (last ? '0 4px 4px 0' : '0') + ';';
      const hosts = [
        ['fotos', 4210, 310, 120], ['git', 0, 2950, 1480], ['filme', 3100, 210, 90], ['wiki', 0, 1620, 400], ['blog', 0, 900, 600]
      ].map(([name, m, w, p]) => ({
        name, total: fmt(m + w + p),
        tip: name + '.beispiel.de – ohne Zertifikat ' + fmt(m) + ', WAF ' + fmt(w) + ', IP-Filter ' + fmt(p),
        mtls: part(m, C.mtls, false), waf: part(w, C.waf, false), ip: part(p, C.ip, true)
      }));

      return { kpis, land, spots, spotLabels, ips, legend, hours, rules, hosts };
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
<a href="#/stats" aria-current="page" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; background: #2A2F3A; color: #E7E9EE; font-weight: 500; text-decoration: none;">Sicherheit</a>
<a href="#/stats-traffic" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; color: #A0A7B4; font-weight: 500; text-decoration: none;">Traffic &amp; Leistung</a>
<a href="#/stats-usage" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; color: #A0A7B4; font-weight: 500; text-decoration: none;">Nutzung</a>
<a href="#/logs" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; color: #A0A7B4; font-weight: 500; text-decoration: none;">Logs</a>
</nav>
</div>
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Zeitraum</span>
<select style="min-height: 40px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Letzte 24 Stunden</option><option>7 Tage</option><option>30 Tage</option></select>
</label>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Node</span>
<select style="min-height: 40px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Alle Nodes</option><option>edge-fra</option><option>home-nas</option><option>pi-eltern</option><option>vps-hel</option></select>
</label>
</div>
</header>

<section aria-label="Kennzahlen" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px;">
{#each dcv.kpis as k}
<div style="display: flex; flex-direction: column; gap: 3px; padding: 12px 14px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: #A0A7B4;"><span style={k.keyStyle}></span>{k.label}</span>
<span style="font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums;">{k.value}</span>
<span style="font-size: 12px; color: #A0A7B4;">{k.sub}</span>
</div>
{/each}
</section>

<div style="display: flex; flex-wrap: wrap; gap: 14px; align-items: stretch;">

<section aria-labelledby="map-title" style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px;">
<h2 id="map-title" style="margin: 0; font-size: 15px; font-weight: 600;">Herkunft abgelehnter Anfragen</h2>
<span style="font-size: 12px; color: #A0A7B4;">Kreisgröße = Anzahl · GeoIP-Datenbank lokal</span>
</div>
<div role="img" aria-label="Weltkarte: die meisten abgelehnten Anfragen kommen aus Deutschland, China, den USA, den Niederlanden und Russland" style="position: relative; width: 100%; max-width: 640px; aspect-ratio: 360 / 140; margin: 0 auto;">
{#each dcv.land as d}
<span style={d}></span>
{/each}
{#each dcv.spots as s}
<span title={s.tip} style={s.style}></span>
{/each}
{#each dcv.spotLabels as l}
<span style={l.style}>{l.text}</span>
{/each}
</div>
</section>

<section aria-labelledby="ip-title" style="flex: 1 1 330px; min-width: 0; display: flex; flex-direction: column; gap: 2px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="ip-title" style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">Top abgelehnte IPs</h2>
{#each dcv.ips as i}
<div style="display: flex; align-items: center; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style={i.keyStyle}></span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">{i.ip}</span>
<span style="font-size: 12px; color: #A0A7B4;">{i.where} · {i.reason}</span>
</span>
<span style="font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums;">{i.count}</span>
<span style={i.actionStyle}>{i.action}</span>
</div>
{/each}
</section>

</div>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px;">

<section aria-labelledby="time-title" style="display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px;">
<h2 id="time-title" style="margin: 0; font-size: 15px; font-weight: 600;">Abgelehnt pro Stunde</h2>
<span style="display: flex; gap: 10px; font-size: 12px; color: #A0A7B4;">
{#each dcv.legend as g}
<span style="display: inline-flex; align-items: center; gap: 5px;"><span style={g.keyStyle}></span>{g.label}</span>
{/each}
</span>
</div>
<div style="display: flex; gap: 6px;">
<div style="display: flex; flex-direction: column; justify-content: space-between; height: 130px; font-size: 11px; color: #A0A7B4; text-align: right; font-variant-numeric: tabular-nums;"><span>1.500</span><span>750</span><span>0</span></div>
<div style="flex: 1; position: relative; height: 130px; border-bottom: 1px solid #2E3440; display: flex; align-items: flex-end; gap: 3px;">
<span style="position: absolute; left: 0; right: 0; top: 0; border-top: 1px dashed #232833;"></span>
<span style="position: absolute; left: 0; right: 0; top: 50%; border-top: 1px dashed #232833;"></span>
{#each dcv.hours as h}
<div title={h.tip} style="flex: 1; min-width: 0; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; gap: 2px; position: relative;">
<span style={h.ipStyle}></span>
<span style={h.wafStyle}></span>
<span style={h.mtlsStyle}></span>
</div>
{/each}
</div>
</div>
<div style="display: flex; justify-content: space-between; padding-left: 34px; font-size: 11px; color: #A0A7B4;"><span>11:00</span><span>17:00</span><span>23:00</span><span>05:00</span><span>jetzt</span></div>
</section>

<section aria-labelledby="waf-title" style="display: flex; flex-direction: column; gap: 6px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 6px;">
<h2 id="waf-title" style="margin: 0; font-size: 15px; font-weight: 600;">Coraza · Angriffsarten</h2>
<span style="font-size: 12px; color: #A0A7B4;">6.204 blockiert</span>
</div>
{#each dcv.rules as r}
<div title={r.tip} style="display: grid; grid-template-columns: 130px minmax(0, 1fr) 46px; align-items: center; gap: 8px; min-height: 24px;">
<span style="font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{r.label}</span>
<span style="height: 10px; display: flex;"><span style={r.barStyle}></span></span>
<span style="font-size: 12px; text-align: right; font-variant-numeric: tabular-nums;">{r.value}</span>
</div>
{/each}
<a href="#/logs" style="font-size: 12px; font-weight: 500; margin-top: 2px;">Treffer in den Logs ansehen</a>
</section>

<section aria-labelledby="host-title" style="display: flex; flex-direction: column; gap: 6px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 6px;">
<h2 id="host-title" style="margin: 0; font-size: 15px; font-weight: 600;">Am meisten abgelehnt</h2>
<span style="font-size: 12px; color: #A0A7B4;">nach Host</span>
</div>
{#each dcv.hosts as h}
<div title={h.tip} style="display: grid; grid-template-columns: 70px minmax(0, 1fr) 46px; align-items: center; gap: 8px; min-height: 28px;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">{h.name}</span>
<span style="height: 10px; display: flex; gap: 2px;"><span style={h.mtls}></span><span style={h.waf}></span><span style={h.ip}></span></span>
<span style="font-size: 12px; text-align: right; font-variant-numeric: tabular-nums;">{h.total}</span>
</div>
{/each}
<span style="font-size: 12px; color: #A0A7B4; margin-top: 2px;">Private Dienste werden fast nur am fehlenden Zertifikat abgewiesen.</span>
</section>

</div>
</main>
</div>
