<!--
  Nodes
  Aus dem Design-Canvas „Caddy Control“ übernommen (Nodes.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const tone = {
        ok: { fg: '#7FD9AC', dot: '#4CC38A', bg: 'rgba(76,195,138,.12)', border: '#232833' },
        warn: { fg: '#F0BE6E', dot: '#E5A443', bg: 'rgba(229,164,67,.14)', border: '#5A4520' },
        bad: { fg: '#F59A90', dot: '#F07167', bg: 'rgba(240,113,103,.14)', border: '#5A2F30' }
      };
      const nodes = [
        { name: 'edge-fra', where: 'VPS · Frankfurt', status: 'online', t: 'ok', caddy: '2.10.2', hosts: '9 (5 öffentlich)', seen: 'gerade eben', sync: 'synchron', st: 'ok', modules: 'dns.providers.cloudflare', action: 'Neu synchronisieren' },
        { name: 'home-nas', where: 'Zuhause', status: 'online', t: 'ok', caddy: '2.10.2', hosts: '6 (alle mTLS)', seen: 'gerade eben', sync: 'synchron', st: 'ok', modules: 'dns.providers.cloudflare', action: 'Neu synchronisieren' },
        { name: 'pi-eltern', where: 'Elternhaus · hinter NAT', status: 'online', t: 'ok', caddy: '2.9.1 · Update verfügbar', hosts: '2 (1 mTLS)', seen: 'vor 8 Sek.', sync: 'lokal geändert', st: 'warn', modules: '–', action: 'Caddy aktualisieren' },
        { name: 'vps-hel', where: 'VPS · Helsinki', status: 'offline', t: 'bad', caddy: '2.10.2', hosts: '1 (öffentlich)', seen: 'heute, 10:28', sync: 'unbekannt', st: 'bad', modules: '–', action: 'Verbindung prüfen' }
      ].map((n) => ({
        ...n,
        cardStyle: 'display: flex; flex-direction: column; gap: 14px; padding: 16px; border-radius: 12px; background: #161920; border: 1px solid ' + tone[n.st === 'ok' ? n.t : n.st].border + ';',
        statusStyle: 'display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + tone[n.t].fg + '; background: ' + tone[n.t].bg + ';',
        dotStyle: 'width: 7px; height: 7px; border-radius: 50%; background: ' + tone[n.t].dot + ';',
        syncStyle: 'margin: 0; color: ' + (n.st === 'ok' ? '#E7E9EE' : tone[n.st].fg) + ';'
      }));
      return { nodes };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="nodes" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 18px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 6px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Nodes</h1>
<p style="margin: 0; color: #A0A7B4;">Jeder Node meldet sich per Agent beim Controller – kein offener Admin-Port, auch hinter NAT.</p>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Node hinzufügen</button>
</header>

<section aria-label="Alle Nodes" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px;">
{#each dcv.nodes as n}
<article style={n.cardStyle}>
<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;">
<div style="display: flex; flex-direction: column; gap: 4px; min-width: 0;">
<h2 style="margin: 0; font-size: 17px; font-weight: 600; font-family: 'JetBrains Mono', ui-monospace, monospace;">{n.name}</h2>
<span style="font-size: 13px; color: #A0A7B4;">{n.where}</span>
</div>
<span style={n.statusStyle}><span style={n.dotStyle}></span>{n.status}</span>
</div>
<dl style="margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px;">
<div style="display: flex; flex-direction: column; gap: 2px;"><dt style="font-size: 12px; color: #A0A7B4;">Caddy</dt><dd style="margin: 0; font-variant-numeric: tabular-nums;">{n.caddy}</dd></div>
<div style="display: flex; flex-direction: column; gap: 2px;"><dt style="font-size: 12px; color: #A0A7B4;">Hosts</dt><dd style="margin: 0;">{n.hosts}</dd></div>
<div style="display: flex; flex-direction: column; gap: 2px;"><dt style="font-size: 12px; color: #A0A7B4;">Letzter Kontakt</dt><dd style="margin: 0;">{n.seen}</dd></div>
<div style="display: flex; flex-direction: column; gap: 2px;"><dt style="font-size: 12px; color: #A0A7B4;">Konfiguration</dt><dd style={n.syncStyle}>{n.sync}</dd></div>
</dl>
<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: auto;">
<button type="button" style="min-height: 40px; padding: 0 12px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">Config ansehen</button>
<button type="button" style="min-height: 40px; padding: 0 12px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">{n.action}</button>
</div>
</article>
{/each}
</section>

<div style="display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start;">

<section aria-labelledby="drift-title" style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 24px; border-radius: 12px; background: #161920; border: 1px solid #5A4520;">
<div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h2 id="drift-title" style="margin: 0; font-size: 16px; font-weight: 600;">Abweichung auf pi-eltern</h2>
<span style="font-size: 13px; color: #A0A7B4;">Die laufende Config unterscheidet sich vom Stand im Controller (gestern, 21:04).</span>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 8px;">
<button type="button" style="min-height: 44px; padding: 0 14px; border-radius: 8px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Änderung übernehmen</button>
<button type="button" style="min-height: 44px; padding: 0 14px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Mit Controller überschreiben</button>
</div>
</div>
<div style="overflow-x: auto; border-radius: 8px; background: #0B0D10; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.7;">
<div style="padding: 10px 14px 0; color: #A0A7B4;">home.beispiel.de</div>
<div style="padding: 0 14px; color: #C9CED8; white-space: pre;">  reverse_proxy &#123;</div>
<div style="padding: 0 14px; color: #F59A90; background: rgba(240,113,103,.10); white-space: pre;">-   to 192.168.178.5:8123</div>
<div style="padding: 0 14px; color: #7FD9AC; background: rgba(76,195,138,.10); white-space: pre;">+   to 192.168.178.7:8123</div>
<div style="padding: 0 14px 12px; color: #C9CED8; white-space: pre;">  &#125;</div>
</div>
</section>

<section aria-labelledby="join-title" style="flex: 1 1 380px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 24px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="join-title" style="margin: 0; font-size: 16px; font-weight: 600;">Neuen Node verbinden</h2>
<ol style="margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 10px; color: #C9CED8; line-height: 1.5;">
<li>Caddy auf dem Server installieren (mit benötigten DNS-Modulen).</li>
<li>Agent mit Beitritts-Token starten – er erzeugt eigene Schlüssel und baut eine mTLS-Verbindung zum Controller auf.</li>
<li>Node hier bestätigen. Danach überträgt der Controller die Config.</li>
</ol>
<pre style="margin: 0; padding: 12px 14px; border-radius: 8px; background: #0B0D10; border: 1px solid #232833; overflow-x: auto; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.6; color: #C9CED8;">tesseract-agent join \
  --controller https://tesseract.beispiel.de \
  --token [BEITRITTS-TOKEN]</pre>
<span style="font-size: 12px; color: #A0A7B4;">Token ist 30 Minuten gültig und nur einmal verwendbar.</span>
</section>

</div>
</main>
</div>
