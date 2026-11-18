<!--
  Proxy-Hosts
  Aus dem Design-Canvas „Caddy Control“ übernommen (Hosts.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const lock = 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4';
      const globe = 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18';
      const pill = 'display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap;';
      const dot = (c) => 'display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: ' + c + ';';
      const rows = [
        ['fotos.beispiel.de', '10.0.1.20:2342', 'home-nas', 'mtls', '4 Personen · 6 Geräte', 'LE · 64 Tage', 'ok', true],
        ['filme.beispiel.de', '10.0.1.20:8096', 'home-nas', 'mtls', '5 Personen · 6 Geräte', 'LE · 64 Tage', 'ok'],
        ['rezepte.beispiel.de', '10.0.1.21:9000', 'home-nas', 'mtls', '3 Personen · 3 Geräte', 'LE · 51 Tage', 'ok'],
        ['kalender.beispiel.de', '127.0.0.1:5232', 'edge-fra', 'mtls', '3 Personen · 4 Geräte', 'LE · 80 Tage', 'ok'],
        ['home.beispiel.de', '192.168.178.5:8123', 'pi-eltern', 'mtls', '2 Personen · 3 Geräte', 'LE · 33 Tage', 'warn'],
        ['blog.beispiel.de', '127.0.0.1:2368', 'edge-fra', 'pub', 'Öffentlich', 'LE · 72 Tage', 'ok'],
        ['git.beispiel.de', '127.0.0.1:3000', 'edge-fra', 'pub', 'Öffentlich', 'LE · 72 Tage', 'ok'],
        ['status.beispiel.de', '127.0.0.1:3001', 'edge-fra', 'pub', 'Öffentlich', 'LE · 72 Tage', 'ok'],
        ['wiki.beispiel.de', '127.0.0.1:8090', 'vps-hel', 'pub', 'Öffentlich', 'LE · 9 Tage · Node offline', 'bad']
      ];
      const statusDot = { ok: '#4CC38A', warn: '#E5A443', bad: '#F07167' };
      const tlsColor = { ok: '#A0A7B4', warn: '#F0BE6E', bad: '#F59A90' };
      const prot = { 'fotos.beispiel.de': 'WAF', 'filme.beispiel.de': 'WAF', 'blog.beispiel.de': 'WAF', 'git.beispiel.de': 'IP · WAF · Authelia', 'status.beispiel.de': 'IP', 'wiki.beispiel.de': 'WAF · Authelia' };
      const hosts = rows.map(([domain, target, node, kind, mode, tls, st, sel]) => ({
        domain, target, node, mode, tls, prot: prot[domain] || '–',
        modeIcon: kind === 'mtls' ? lock : globe,
        modeStyle: pill + (kind === 'mtls' ? ' color: #C9C1FF; background: rgba(139,124,246,.16);' : ' color: #7FD9AC; background: rgba(76,195,138,.12);'),
        dotStyle: dot(statusDot[st]),
        tlsStyle: 'color: ' + tlsColor[st] + ';',
        rowStyle: 'border-top: 1px solid #232833;' + (sel ? ' background: rgba(139,124,246,.08); box-shadow: inset 3px 0 0 #8B7CF6;' : '')
      }));
      return { hosts };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="hosts" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 16px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Proxy-Hosts</h1>
<p style="margin: 0; color: #A0A7B4;">Öffentlich mit Let's Encrypt – oder nur für freigegebene Geräte (mTLS).</p>
</div>
<a href="#/host-new-1" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Host anlegen</a>
</header>

<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px;">
<div role="group" aria-label="Zugriffsart filtern" style="display: flex; gap: 4px; padding: 4px; border-radius: 10px; background: #161920; border: 1px solid #232833;">
<button type="button" aria-pressed="true" style="min-height: 36px; padding: 0 14px; border-radius: 7px; border: none; background: #2A2F3A; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Alle · 18</button>
<button type="button" aria-pressed="false" style="min-height: 36px; padding: 0 14px; border-radius: 7px; border: none; background: transparent; color: #A0A7B4; font: inherit; font-weight: 500; cursor: pointer;">Öffentlich · 11</button>
<button type="button" aria-pressed="false" style="min-height: 36px; padding: 0 14px; border-radius: 7px; border: none; background: transparent; color: #A0A7B4; font: inherit; font-weight: 500; cursor: pointer;">mTLS · 7</button>
</div>
<label style="flex: 1 1 240px; display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 12px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #A0A7B4;">
<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M20 20l-4-4"></path></svg>
<span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Hosts durchsuchen</span>
<input type="search" placeholder="Domain oder Ziel suchen" style="flex: 1; min-width: 0; border: none; outline: none; background: transparent; color: #E7E9EE; font: inherit;">
</label>
<label style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px;">Node
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;">
<option>Alle Nodes</option><option>edge-fra</option><option>home-nas</option><option>pi-eltern</option><option>vps-hel</option>
</select>
</label>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<section aria-label="Host-Liste" style="flex: 999 1 560px; min-width: 0; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<table style="width: 100%; min-width: 640px; border-collapse: collapse; font-size: 14px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">
<th scope="col" style="padding: 12px 16px; font-weight: 600;">Domain</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Ziel</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Node</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Zugriff</th>
<th scope="col" style="padding: 12px; font-weight: 600;">Schutz</th>
<th scope="col" style="padding: 12px 16px 12px 12px; font-weight: 600;">TLS</th>
</tr>
</thead>
<tbody>
{#each dcv.hosts as h}
<tr style={h.rowStyle}>
<td style="padding: 11px 16px;">
<div style="display: flex; align-items: center; gap: 10px;">
<span style={h.dotStyle}></span>
<a href="#/host-security" style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 500; color: #E7E9EE; text-decoration: none;">{h.domain}</a>
</div>
</td>
<td style="padding: 11px 12px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px; color: #A0A7B4;">{h.target}</td>
<td style="padding: 11px 12px; color: #A0A7B4;">{h.node}</td>
<td style="padding: 11px 12px;">
<span style={h.modeStyle}>
<svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d={h.modeIcon}></path></svg>
{h.mode}
</span>
</td>
<td style="padding: 11px 12px; font-size: 12px; color: #C9CED8; white-space: nowrap;">{h.prot}</td>
<td style="padding: 11px 16px 11px 12px; font-size: 13px;"><span style={h.tlsStyle}>{h.tls}</span></td>
</tr>
{/each}
</tbody>
</table>
</section>

<section aria-labelledby="edit-title" style="flex: 1 1 360px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 20px; border-radius: 12px; background: #161920; border: 1px solid #3A3460;">
<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 10px;">
<div style="display: flex; flex-direction: column; gap: 2px;">
<span style="font-size: 12px; font-weight: 600; color: #A0A7B4; text-transform: uppercase; letter-spacing: 0.06em;">Host bearbeiten</span>
<h2 id="edit-title" style="margin: 0; font-size: 17px; font-weight: 600; font-family: 'JetBrains Mono', ui-monospace, monospace;">fotos.beispiel.de</h2>
</div>
<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #7FD9AC; background: rgba(76,195,138,.12);">aktiv</span>
</div>

<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px;">
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Node
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>home-nas</option><option>edge-fra</option><option>pi-eltern</option><option>vps-hel</option>
</select>
</label>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Ziel (Upstream)
<input type="text" value="10.0.1.20:2342" style="min-height: 44px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 14px;">
</label>
</div>

<div role="radiogroup" aria-label="Zugriff" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; padding: 4px; border-radius: 10px; background: #0E1014; border: 1px solid #232833;">
<label style="display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 40px; border-radius: 7px; color: #A0A7B4; cursor: pointer;"><input type="radio" name="mode" style="accent-color: #8B7CF6; margin: 0;">Öffentlich</label>
<label style="display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 40px; border-radius: 7px; background: rgba(139,124,246,.18); color: #EEEBFF; font-weight: 600; cursor: pointer;"><input type="radio" name="mode" checked style="accent-color: #8B7CF6; margin: 0;">Nur mit Zertifikat</label>
</div>

<div style="display: flex; flex-direction: column; gap: 8px;">
<span style="font-size: 13px; color: #A0A7B4;">Freigegeben für</span>
<div style="display: flex; flex-wrap: wrap; gap: 8px;">
<span style="display: inline-flex; align-items: center; gap: 6px; padding: 0 4px 0 12px; min-height: 34px; border-radius: 999px; background: rgba(139,124,246,.16); color: #D6D0FF; font-size: 13px; font-weight: 500;">Gruppe Familie
<button type="button" aria-label="Gruppe Familie entfernen" style="width: 28px; height: 28px; border-radius: 50%; border: none; background: transparent; color: inherit; cursor: pointer; display: flex; align-items: center; justify-content: center;"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg></button>
</span>
<span style="display: inline-flex; align-items: center; gap: 6px; padding: 0 4px 0 12px; min-height: 34px; border-radius: 999px; background: #232833; color: #E7E9EE; font-size: 13px; font-weight: 500;">Ben
<button type="button" aria-label="Ben entfernen" style="width: 28px; height: 28px; border-radius: 50%; border: none; background: transparent; color: inherit; cursor: pointer; display: flex; align-items: center; justify-content: center;"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg></button>
</span>
<button type="button" style="min-height: 34px; padding: 0 12px; border-radius: 999px; border: 1px dashed #3A4150; background: transparent; color: #A0A7B4; font: inherit; font-size: 13px; cursor: pointer;">+ Hinzufügen</button>
</div>
<div style="display: flex; gap: 16px; padding: 10px 12px; border-radius: 8px; background: #0E1014; font-size: 13px;">
<span><strong style="font-weight: 600;">4</strong> <span style="color: #A0A7B4;">Personen</span></span>
<span><strong style="font-weight: 600;">6</strong> <span style="color: #A0A7B4;">Geräte mit gültigem Zertifikat</span></span>
</div>
</div>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Ohne passendes Zertifikat
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>Verbindung ablehnen (TLS-Handshake schlägt fehl)</option>
<option>Hinweisseite „Kein Zugang“ anzeigen</option>
</select>
</label>

<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<button type="button" style="flex: 1 1 auto; min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Speichern &amp; übertragen</button>
<a href="#/host-history" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Verlauf</a>
<a href="#/host-security" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Sicherheit</a>
</div>
</section>

</div>
</main>
</div>
