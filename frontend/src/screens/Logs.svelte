<!--
  Statistik · Logs
  Aus dem Design-Canvas „Caddy Control“ übernommen (Logs.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const C = { mtls: '#8B7CF6', waf: '#14A399', ip: '#CF7D45', ok: '#5E6573' };
      const key = (c) => 'display: inline-block; width: 9px; height: 9px; border-radius: 3px; flex-shrink: 0; background: ' + c + ';';
      const filters = [
        ['Alle', null, false], ['Abgelehnt', null, true], ['Ohne Zertifikat', C.mtls, false], ['WAF', C.waf, false], ['IP-Filter', C.ip, false]
      ].map(([label, c, on]) => ({
        label, pressed: on ? 'true' : 'false',
        keyStyle: c ? key(c) : 'display: none;',
        style: 'display: inline-flex; align-items: center; gap: 6px; min-height: 34px; padding: 0 12px; border-radius: 7px; border: none; font: inherit; font-size: 13px; font-weight: 500; cursor: pointer; ' + (on ? 'background: #2A2F3A; color: #E7E9EE;' : 'background: transparent; color: #A0A7B4;')
      }));
      const mono = "font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;";
      const dev = 'font-size: 13px; color: #C9C1FF;';
      const st = (code) => {
        const bad = /^4|^TLS/.test(code);
        return 'font-family: \'JetBrains Mono\', ui-monospace, monospace; font-size: 12px; font-weight: 600; color: ' + (bad ? '#F59A90' : code.startsWith('3') ? '#C9CED8' : '#7FD9AC') + ';';
      };
      const rows = [
        ['10:42:07.118', 'fotos', 'home-nas', 'TLS-Handshake', 'TLS', '203.0.113.92', 'DE', 'Kein Zertifikat', 'mtls'],
        ['10:42:05.902', 'git', 'edge-fra', 'GET /.env', '403', '198.51.100.23', 'US', 'WAF 930130', 'waf'],
        ['10:42:03.441', 'git', 'edge-fra', "GET /search?q=1'+OR+'1'='1", '403', '198.51.100.140', 'RU', 'WAF 942100', 'waf', true],
        ['10:42:01.007', 'blog', 'edge-fra', 'GET /wp-login.php', '403', '192.0.2.77', 'CN', 'Liste „Scanner“', 'ip'],
        ['10:41:58.630', 'blog', 'edge-fra', 'GET /2026/11/caddy-mtls', '200', '192.0.2.10', 'DE', 'ok', 'ok'],
        ['10:41:57.212', 'filme', 'home-nas', 'GET /web/index.html', '200', 'Pixel 8 · Ben', '', 'ok · Gerät erkannt', 'ok', false, true],
        ['10:41:54.771', 'git', 'edge-fra', 'GET /', '302', '192.0.2.10', 'DE', 'zu Authelia', 'ok'],
        ['10:41:52.330', 'home', 'pi-eltern', 'TLS-Handshake', 'TLS', '198.51.100.9', 'US', 'Kein Zertifikat', 'mtls'],
        ['10:41:50.004', 'status', 'edge-fra', 'GET /api/status', '200', '192.0.2.10', 'DE', 'ok', 'ok'],
        ['10:41:47.876', 'git', 'edge-fra', 'GET /../../etc/passwd', '403', '198.51.100.23', 'US', 'WAF 930100', 'waf'],
        ['10:41:45.512', 'fotos', 'home-nas', 'GET /api/v1/photos', '200', 'iPhone 15 · Anna', '', 'ok · Gerät erkannt', 'ok', false, true],
        ['10:41:43.218', 'blog', 'edge-fra', 'GET /xmlrpc.php', '403', '192.0.2.77', 'CN', 'Liste „Scanner“', 'ip']
      ].map(([time, host, node, req, status, who, cc, reason, k, sel, isDev]) => ({
        time, host, node, req, status: status === 'TLS' ? 'abgelehnt' : status, who, cc, reason,
        statusStyle: st(status),
        whoStyle: isDev ? dev : mono,
        keyStyle: key(C[k]),
        rowStyle: 'border-top: 1px solid #1E222B;' + (sel ? ' background: rgba(139,124,246,.10); box-shadow: inset 3px 0 0 #8B7CF6;' : '')
      }));
      return { filters, rows };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="stats" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 22px 32px; display: flex; flex-direction: column; gap: 12px;">

<header style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px;">
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 18px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Statistik</h1>
<nav aria-label="Ansicht" style="display: flex; gap: 4px; padding: 4px; border-radius: 10px; background: #161920; border: 1px solid #232833;">
<a href="#/stats" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; color: #A0A7B4; font-weight: 500; text-decoration: none;">Sicherheit</a>
<a href="#/stats-traffic" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; color: #A0A7B4; font-weight: 500; text-decoration: none;">Traffic &amp; Leistung</a>
<a href="#/stats-usage" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; color: #A0A7B4; font-weight: 500; text-decoration: none;">Nutzung</a>
<a href="#/logs" aria-current="page" style="display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 7px; background: #2A2F3A; color: #E7E9EE; font-weight: 500; text-decoration: none;">Logs</a>
</nav>
</div>
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px; font-size: 13px; color: #A0A7B4;">
<span style="display: inline-flex; align-items: center; gap: 6px;"><span style="width: 8px; height: 8px; border-radius: 50%; background: #4CC38A;"></span>3 von 4 Nodes liefern</span>
<span>vps-hel puffert lokal und liefert nach</span>
<label style="display: inline-flex; align-items: center; gap: 8px; color: #E7E9EE; cursor: pointer;"><input type="checkbox" role="switch" checked style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">Live</label>
</div>
</header>

<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
<label style="flex: 1 1 260px; display: flex; align-items: center; gap: 8px; min-height: 42px; padding: 0 12px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #A0A7B4;">
<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M20 20l-4-4"></path></svg>
<span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Logs durchsuchen</span>
<input type="search" placeholder="host:git status:403 ip:198.51.100.0/24" style="flex: 1; min-width: 0; border: none; outline: none; background: transparent; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">
</label>
<div role="group" aria-label="Ergebnis" style="display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 10px; background: #161920; border: 1px solid #232833;">
{#each dcv.filters as f}
<button type="button" aria-pressed={f.pressed} style={f.style}><span style={f.keyStyle}></span>{f.label}</button>
{/each}
</div>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Node</span>
<select style="min-height: 42px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;"><option>Alle Nodes</option><option>edge-fra</option><option>home-nas</option><option>pi-eltern</option></select>
</label>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-start;">

<section aria-label="Log-Einträge" style="flex: 999 1 600px; min-width: 0; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<table style="width: 100%; min-width: 760px; border-collapse: collapse; font-size: 13px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px;">
<th scope="col" style="padding: 10px 14px; font-weight: 600;">Zeit</th>
<th scope="col" style="padding: 10px 8px; font-weight: 600;">Host · Node</th>
<th scope="col" style="padding: 10px 8px; font-weight: 600;">Anfrage</th>
<th scope="col" style="padding: 10px 8px; font-weight: 600;">Status</th>
<th scope="col" style="padding: 10px 8px; font-weight: 600;">Wer</th>
<th scope="col" style="padding: 10px 14px 10px 8px; font-weight: 600;">Grund</th>
</tr>
</thead>
<tbody>
{#each dcv.rows as r}
<tr style={r.rowStyle}>
<td style="padding: 8px 14px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #A0A7B4; white-space: nowrap;">{r.time}</td>
<td style="padding: 8px; white-space: nowrap;"><span style="font-weight: 500;">{r.host}</span> <span style="font-size: 12px; color: #A0A7B4;">· {r.node}</span></td>
<td style="padding: 8px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{r.req}</td>
<td style="padding: 8px;"><span style={r.statusStyle}>{r.status}</span></td>
<td style="padding: 8px; white-space: nowrap;"><span style={r.whoStyle}>{r.who}</span> <span style="font-size: 12px; color: #A0A7B4;">{r.cc}</span></td>
<td style="padding: 8px 14px 8px 8px; white-space: nowrap;"><span style="display: inline-flex; align-items: center; gap: 6px;"><span style={r.keyStyle}></span>{r.reason}</span></td>
</tr>
{/each}
</tbody>
</table>
</section>

<aside aria-labelledby="entry-title" style="flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 12px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #3A3460;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<span style="font-size: 12px; color: #A0A7B4; font-family: 'JetBrains Mono', ui-monospace, monospace;">heute 10:42:03.441 · edge-fra</span>
<h2 id="entry-title" style="margin: 0; font-size: 17px; font-weight: 600;">Von Coraza blockiert</h2>
</div>
<div style="padding: 10px 12px; border-radius: 8px; background: #0B0D10; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere;">GET git.beispiel.de/search?q=1'+OR+'1'='1</div>
<dl style="margin: 0; display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 7px 12px; font-size: 13px;">
<dt style="color: #A0A7B4;">Regel</dt><dd style="margin: 0;"><span style="font-family: 'JetBrains Mono', ui-monospace, monospace;">942100</span> · SQL-Injection erkannt (libinjection)</dd>
<dt style="color: #A0A7B4;">Anomalie-Score</dt><dd style="margin: 0;">5 · Grenze 5</dd>
<dt style="color: #A0A7B4;">Antwort</dt><dd style="margin: 0;">403, nie beim Dienst angekommen</dd>
<dt style="color: #A0A7B4;">Client</dt><dd style="margin: 0;"><span style="font-family: 'JetBrains Mono', ui-monospace, monospace;">198.51.100.140</span> · Russland</dd>
<dt style="color: #A0A7B4;">Diese IP heute</dt><dd style="margin: 0;">488 Anfragen, 471 blockiert</dd>
</dl>
<div style="display: flex; flex-direction: column; gap: 8px; padding-top: 10px; border-top: 1px solid #232833;">
<button type="button" style="min-height: 42px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">IP sperren (Liste „Scanner“)</button>
<button type="button" style="min-height: 42px; border-radius: 8px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Fehlalarm: Ausnahme für git anlegen</button>
<a href="#" style="font-size: 13px; font-weight: 500;">Alle Einträge dieser IP</a>
</div>
</aside>

</div>
</main>
</div>
