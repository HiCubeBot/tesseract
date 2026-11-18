<!--
  Einstellungen · Metriken (Prometheus)
  Aus dem Design-Canvas „Caddy Control“ übernommen (SettingsMetrics.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Metriken';
      const tabs = [
        ['Allgemein', '#/settings'], ['Integrationen', '#/settings-integrations'], ['Zertifizierungsstelle', '#/settings-ca'],
        ['Benachrichtigungen', '#/settings-notify'], ['Metriken', '#/settings-metrics'], ['Backup', '#/settings-backup']
      ].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 42px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (label === active ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const pill = (fg, bg) => 'padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const T = { gauge: pill('#A9C7F5', 'rgba(110,160,240,.14)'), counter: pill('#C9C1FF', 'rgba(139,124,246,.16)') };
      const metrics = [
        ['tesseract_node_up', 'node', 'gauge', '1, wenn der Agent verbunden ist'],
        ['tesseract_node_config_drift', 'node', 'gauge', '1 bei lokaler Abweichung von der Config'],
        ['tesseract_cert_expiry_timestamp_seconds', 'kind, name', 'gauge', 'Ablauf von Host- und Geräte-Zertifikaten'],
        ['tesseract_devices', 'status', 'gauge', 'Geräte nach Status (aktiv, gesperrt, wartend)'],
        ['tesseract_tls_rejected_total', 'host, node', 'counter', 'abgewiesene Verbindungen ohne gültiges Zertifikat'],
        ['tesseract_waf_blocked_total', 'host, node', 'counter', 'von Coraza blockierte Anfragen'],
        ['tesseract_ip_blocked_total', 'host, list', 'counter', 'vom IP-Filter abgewiesene Anfragen'],
        ['caddy_http_requests_total', 'node, server, handler', 'counter', 'von Caddy, über den Agenten eingesammelt']
      ].map(([name, labels, type, desc]) => ({ name, labels: '{' + labels + '}', type, desc, typeStyle: T[type] }));
      return { tabs, metrics };
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
<p style="margin: 0; color: #A0A7B4;">Prometheus-Metriken für Controller und alle Nodes – an einer Stelle abrufbar.</p>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<a href="#" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Grafana-Dashboard (JSON)</a>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Speichern</button>
</div>
</header>

<nav aria-label="Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>

<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">

<div style="flex: 1 1 400px; min-width: 0; display: flex; flex-direction: column; gap: 14px;">
<section aria-labelledby="ep-title" style="display: flex; flex-direction: column; padding: 14px 18px 6px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 6px;">
<h2 id="ep-title" style="margin: 0; font-size: 15px; font-weight: 600;">Endpunkt</h2>
<span style="display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #7FD9AC; background: rgba(76,195,138,.12);"><span style="width: 7px; height: 7px; border-radius: 50%; background: #4CC38A;"></span>abgefragt vor 12 s</span>
</div>
<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="font-weight: 500;">Adresse</span>
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">tesseract.beispiel.de/metrics</span>
</div>
<label style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Schutz</span><span style="font-size: 12px; color: #A0A7B4;">wer die Metriken abrufen darf</span></span>
<select style="min-height: 36px; min-width: 200px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 13px;"><option>Bearer-Token</option><option>Geräte-Zertifikat (mTLS)</option><option>Nur IP-Liste „Heimnetz“</option></select>
</label>
<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="font-weight: 500;">Token</span>
<span style="font-size: 13px;">gesetzt · <a href="#" style="font-weight: 500;">neu erzeugen</a></span>
</div>
<label style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 52px; border-top: 1px solid #1E222B; cursor: pointer;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Caddy-Metriken der Nodes einsammeln</span><span style="font-size: 12px; color: #A0A7B4;">der Agent liest sie lokal und reicht sie mit Label <code style="font-family: 'JetBrains Mono', ui-monospace, monospace;">node</code> weiter</span></span>
<input type="checkbox" role="switch" checked style="width: 20px; height: 20px; margin: 0; accent-color: #8B7CF6; flex-shrink: 0;">
</label>
</section>

<section aria-labelledby="scrape-title" style="display: flex; flex-direction: column; gap: 8px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="scrape-title" style="margin: 0; font-size: 15px; font-weight: 600;">Für prometheus.yml</h2>
<button type="button" style="min-height: 32px; padding: 0 12px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">Kopieren</button>
</div>
<pre style="margin: 0; padding: 12px 14px; border-radius: 8px; background: #0B0D10; border: 1px solid #232833; overflow-x: auto; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.6; color: #C9CED8;">scrape_configs:
  - job_name: tesseract
    scheme: https
    authorization:
      credentials_file: /etc/prometheus/tesseract.token
    static_configs:
      - targets: ['tesseract.beispiel.de']</pre>
</section>
</div>

<section aria-labelledby="list-title" style="flex: 999 1 520px; min-width: 0; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<h2 id="list-title" style="margin: 0; padding: 14px 18px 4px; font-size: 15px; font-weight: 600;">Verfügbare Metriken</h2>
<table style="width: 100%; min-width: 560px; border-collapse: collapse;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px;">
<th scope="col" style="padding: 10px 18px; font-weight: 600;">Name</th>
<th scope="col" style="padding: 10px 12px; font-weight: 600;">Typ</th>
<th scope="col" style="padding: 10px 18px 10px 12px; font-weight: 600;">Bedeutung</th>
</tr>
</thead>
<tbody>
{#each dcv.metrics as m}
<tr style="border-top: 1px solid #1E222B;">
<td style="padding: 9px 18px;">
<div style="display: flex; flex-direction: column; gap: 2px;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #E7E9EE;">{m.name}</span>
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; color: #A0A7B4;">{m.labels}</span>
</div>
</td>
<td style="padding: 9px 12px;"><span style={m.typeStyle}>{m.type}</span></td>
<td style="padding: 9px 18px 9px 12px; font-size: 13px; color: #C9CED8;">{m.desc}</td>
</tr>
{/each}
</tbody>
</table>
</section>

</div>
</main>
</div>
