<!--
  Einstellungen · Integrationen
  Aus dem Design-Canvas „Caddy Control“ übernommen (SettingsIntegrations.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'Integrationen';
      const tabs = [
        ['Allgemein', '#/settings'], ['Integrationen', '#/settings-integrations'], ['Zertifizierungsstelle', '#/settings-ca'],
        ['Benachrichtigungen', '#/settings-notify'], ['Metriken', '#/settings-metrics'], ['Backup', '#/settings-backup']
      ].map(([label, href]) => ({
        label, href, current: label === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 42px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (label === active ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const headers = ['Remote-User', 'Remote-Groups', 'Remote-Email', 'Remote-Name'];
      const waf = [
        { label: 'Modus', hint: 'erst beobachten, dann scharf schalten', value: 'Nur protokollieren' },
        { label: 'Paranoia-Level', hint: 'OWASP Core Rule Set', value: '1 · Standard' },
        { label: 'Auto-Sperre', hint: 'IP sperren nach WAF-Treffern', value: '20 in 10 Min. → 24 h' },
        { label: 'Treffer aufbewahren', hint: 'im Audit-Log', value: '30 Tage' }
      ];
      const pill = (fg, bg) => 'padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const lists = [
        { name: 'Heimnetz', detail: '192.168.178.0/24, 10.0.1.0/24', use: '3 Hosts · erlauben', useStyle: pill('#7FD9AC', 'rgba(76,195,138,.12)') },
        { name: 'Scanner', detail: '14 Einträge · zuletzt geändert heute', use: '4 Hosts · sperren', useStyle: pill('#F59A90', 'rgba(240,113,103,.14)') },
        { name: 'Cloudflare', detail: 'wird täglich automatisch aktualisiert', use: 'nicht verwendet', useStyle: pill('#A0A7B4', '#232833') }
      ];
      const yes = pill('#7FD9AC', 'rgba(76,195,138,.12)');
      const no = pill('#F59A90', 'rgba(240,113,103,.14)');
      const unk = pill('#A0A7B4', '#232833');
      const link = 'font-size: 13px; font-weight: 500; color: #B9AFFF;';
      const none = 'display: none;';
      const mods = [
        { node: 'edge-fra', waf: 'vorhanden', wafStyle: yes, dns: 'vorhanden', dnsStyle: yes, action: '', actionStyle: none },
        { node: 'home-nas', waf: 'vorhanden', wafStyle: yes, dns: 'vorhanden', dnsStyle: yes, action: '', actionStyle: none },
        { node: 'pi-eltern', waf: 'fehlt', wafStyle: no, dns: 'fehlt', dnsStyle: no, action: 'Neu bauen', actionStyle: link },
        { node: 'vps-hel', waf: 'unbekannt', wafStyle: unk, dns: 'unbekannt', dnsStyle: unk, action: 'offline', actionStyle: 'font-size: 12px; color: #A0A7B4;' }
      ];
      return { tabs, headers, waf, lists, mods };
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
<p style="margin: 0; color: #A0A7B4;">Externe Dienste und Caddy-Module, die Hosts nutzen können.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Speichern</button>
</header>

<nav aria-label="Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 14px; align-items: start;">

<section aria-labelledby="authelia-title" style="display: flex; flex-direction: column; gap: 10px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="authelia-title" style="margin: 0; font-size: 15px; font-weight: 600;">Authelia</h2>
<span style="display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #7FD9AC; background: rgba(76,195,138,.12);"><span style="width: 7px; height: 7px; border-radius: 50%; background: #4CC38A;"></span>erreichbar · 4 ms</span>
</div>
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px;">
<label style="display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #A0A7B4;">Login-Portal (für Nutzer)
<input type="text" value="https://auth.beispiel.de" style="min-height: 38px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">
</label>
<label style="display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #A0A7B4;">Prüf-Adresse (von den Nodes aus)
<input type="text" value="10.0.1.30:9091" style="min-height: 38px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">
</label>
</div>
<div style="display: flex; flex-direction: column; gap: 6px;">
<span style="font-size: 12px; color: #A0A7B4;">An den Dienst weitergereichte Header</span>
<div style="display: flex; flex-wrap: wrap; gap: 6px;">
{#each dcv.headers as h}
<span style="padding: 4px 9px; border-radius: 6px; background: #0E1014; border: 1px solid #2E3440; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">{h}</span>
{/each}
</div>
</div>
<span style="font-size: 12px; color: #A0A7B4;">Nutzer, Gruppen und Regeln (ein/zwei Faktoren) pflegst du in Authelia. Tesseract richtet nur die Weiterleitung ein.</span>
</section>

<section aria-labelledby="coraza-title" style="display: flex; flex-direction: column; padding: 14px 18px 6px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="coraza-title" style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">Coraza WAF · Standards für neue Hosts</h2>
{#each dcv.waf as w}
<label style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 48px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column; gap: 1px;"><span style="font-weight: 500;">{w.label}</span><span style="font-size: 12px; color: #A0A7B4;">{w.hint}</span></span>
<select style="min-height: 36px; min-width: 190px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 13px;"><option>{w.value}</option></select>
</label>
{/each}
</section>

<section aria-labelledby="lists-title" style="display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="lists-title" style="margin: 0; font-size: 15px; font-weight: 600;">IP-Listen</h2>
<button type="button" style="min-height: 34px; padding: 0 12px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">+ Liste</button>
</div>
{#each dcv.lists as l}
<div style="display: flex; align-items: center; gap: 12px; min-height: 48px; border-top: 1px solid #1E222B;">
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px;">
<span style="font-weight: 500;">{l.name}</span>
<span style="font-size: 12px; color: #A0A7B4;">{l.detail}</span>
</div>
<span style={l.useStyle}>{l.use}</span>
</div>
{/each}
<label style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 48px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column; gap: 1px;"><span style="font-weight: 500;">Vertrauenswürdige Proxys</span><span style="font-size: 12px; color: #A0A7B4;">nur dann zählt die IP aus X-Forwarded-For</span></span>
<select style="min-height: 36px; min-width: 190px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 13px;"><option>Keine (direkte Verbindung)</option><option>Liste „Cloudflare“</option></select>
</label>
</section>

<section aria-labelledby="mods-title" style="display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="mods-title" style="margin: 0; font-size: 15px; font-weight: 600;">Caddy-Module pro Node</h2>
<div style="overflow-x: auto;">
<table style="width: 100%; min-width: 380px; border-collapse: collapse; font-size: 13px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px;">
<th scope="col" style="padding: 8px 8px 8px 0; font-weight: 600;">Node</th>
<th scope="col" style="padding: 8px; font-weight: 600;">coraza</th>
<th scope="col" style="padding: 8px; font-weight: 600;">dns.cloudflare</th>
<th scope="col" style="padding: 8px 0 8px 8px; font-weight: 600;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">Aktion</span></th>
</tr>
</thead>
<tbody>
{#each dcv.mods as m}
<tr style="border-top: 1px solid #1E222B;">
<td style="padding: 9px 8px 9px 0; font-family: 'JetBrains Mono', ui-monospace, monospace;">{m.node}</td>
<td style="padding: 9px 8px;"><span style={m.wafStyle}>{m.waf}</span></td>
<td style="padding: 9px 8px;"><span style={m.dnsStyle}>{m.dns}</span></td>
<td style="padding: 9px 0 9px 8px; text-align: right;"><span style={m.actionStyle}>{m.action}</span></td>
</tr>
{/each}
</tbody>
</table>
</div>
<span style="font-size: 12px; color: #A0A7B4;">Fehlt ein Modul, lassen sich WAF bzw. DNS-01 auf diesem Node nicht einschalten.</span>
</section>

</div>
</main>
</div>
