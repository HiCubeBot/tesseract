<!--
  Host anlegen 1 · Domain & Ziel
  Aus dem Design-Canvas „Caddy Control“ übernommen (HostNew1.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const step = 1;
      const steps = ['Domain & Ziel', 'Zugriff', 'Prüfen & übertragen'].map((label, i) => {
        const n = i + 1, on = n === step, done = n < step;
        return {
          n: done ? '✓' : String(n), label, current: on ? 'step' : 'false',
          style: 'display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 14px 0 6px; border-radius: 999px; font-size: 13px; font-weight: 500; ' + (on ? 'background: #232833; color: #E7E9EE;' : 'color: #A0A7B4;'),
          numStyle: 'width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; ' + (on ? 'background: #E7E9EE; color: #0E1014;' : done ? 'background: rgba(76,195,138,.18); color: #7FD9AC;' : 'background: transparent; border: 1px solid #3A4150; color: #A0A7B4;')
        };
      });
      const nodes = [
        { name: 'edge-fra', where: 'VPS · Frankfurt', status: 'online', t: 'ok' },
        { name: 'home-nas', where: 'Zuhause', status: 'online', t: 'ok', checked: true },
        { name: 'pi-eltern', where: 'Elternhaus', status: 'online', t: 'ok' },
        { name: 'vps-hel', where: 'VPS · Helsinki', status: 'offline', t: 'bad', disabled: true }
      ].map((n) => ({
        ...n, checked: !!n.checked, disabled: !!n.disabled,
        style: 'display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border-radius: 10px; cursor: pointer; ' + (n.checked ? 'background: rgba(139,124,246,.10); border: 1px solid #8B7CF6;' : 'background: #0E1014; border: 1px solid #2E3440;') + (n.disabled ? ' opacity: 0.55; cursor: not-allowed;' : ''),
        statusStyle: 'font-size: 12px; font-weight: 600; color: ' + (n.t === 'ok' ? '#7FD9AC' : '#F59A90') + ';'
      }));
      const ok = 'M5 12l5 5l9-10';
      const icon = (bg, fg) => 'width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: ' + bg + '; color: ' + fg + ';';
      const checks = [
        { title: 'DNS zeigt auf home-nas', detail: 'musik.beispiel.de → öffentliche IP von Zuhause', d: ok, iconStyle: icon('rgba(76,195,138,.18)', '#7FD9AC') },
        { title: 'Ziel erreichbar', detail: 'home-nas erreicht 10.0.1.20:4533 · Antwort in 3 ms', d: ok, iconStyle: icon('rgba(76,195,138,.18)', '#7FD9AC') },
        { title: 'Domain noch frei', detail: 'Kein anderer Host nutzt diese Domain', d: ok, iconStyle: icon('rgba(76,195,138,.18)', '#7FD9AC') },
        { title: 'Port 80 von außen offen?', detail: 'Wird für die Let’s-Encrypt-Prüfung (HTTP-01) gebraucht – im letzten Schritt getestet', d: 'M12 8v5M12 16h.01', iconStyle: icon('#232833', '#A0A7B4') }
      ];
      return { steps, nodes, checks };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="hosts" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 20px;">

<header style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<a href="#/hosts" style="font-size: 13px; font-weight: 500; text-decoration: none;">← Proxy-Hosts</a>
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Host anlegen</h1>
</div>
<ol aria-label="Schritte" style="margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px;">
{#each dcv.steps as st}
<li aria-current={st.current} style={st.style}><span style={st.numStyle}>{st.n}</span>{st.label}</li>
{/each}
</ol>
</header>

<div style="display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start;">

<section aria-label="Domain und Ziel" style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 18px; padding: 22px 24px; border-radius: 12px; background: #161920; border: 1px solid #232833;">

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Domain
<input type="text" value="musik.beispiel.de" style="min-height: 46px; padding: 0 14px; border-radius: 8px; background: #0E1014; border: 1px solid #8B7CF6; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 15px;">
</label>

<fieldset style="margin: 0; padding: 0; border: none; display: flex; flex-direction: column; gap: 8px;">
<legend style="padding: 0; margin-bottom: 8px; font-size: 13px; color: #A0A7B4;">Auf welchem Node läuft der Dienst?</legend>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px;">
{#each dcv.nodes as n}
<label style={n.style}>
<span style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 600; font-size: 13px;">{n.name}</span>
<input type="radio" name="node" checked={n.checked} disabled={n.disabled} style="margin: 0; accent-color: #8B7CF6;">
</span>
<span style="font-size: 12px; color: #A0A7B4;">{n.where}</span>
<span style={n.statusStyle}>{n.status}</span>
</label>
{/each}
</div>
</fieldset>

<div style="display: grid; grid-template-columns: 120px minmax(0, 1fr) 120px; gap: 12px;">
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Protokoll
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;"><option>http</option><option>https</option></select>
</label>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Ziel-Adresse (vom Node aus)
<input type="text" value="10.0.1.20" style="min-height: 44px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 14px;">
</label>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Port
<input type="text" value="4533" style="min-height: 44px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 14px;">
</label>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 20px;">
<label style="display: flex; align-items: center; gap: 10px; min-height: 44px; cursor: pointer;"><input type="checkbox" checked style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">WebSockets erlauben</label>
<label style="display: flex; align-items: center; gap: 10px; min-height: 44px; cursor: pointer;"><input type="checkbox" checked style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">HTTP → HTTPS umleiten</label>
<label style="display: flex; align-items: center; gap: 10px; min-height: 44px; cursor: pointer;"><input type="checkbox" style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">Kompression (gzip/zstd)</label>
</div>
</section>

<aside aria-label="Automatische Prüfungen" style="flex: 1 1 320px; min-width: 0; display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Vorab geprüft</h2>
{#each dcv.checks as c}
<div style="display: flex; gap: 12px; padding: 10px 0; border-top: 1px solid #232833;">
<span style={c.iconStyle}><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d={c.d}></path></svg></span>
<div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
<span style="font-weight: 500;">{c.title}</span>
<span style="font-size: 13px; color: #A0A7B4;">{c.detail}</span>
</div>
</div>
{/each}
</aside>

</div>

<footer style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: auto;">
<a href="#/hosts" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Abbrechen</a>
<a href="#/host-new-2" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Weiter: Zugriff</a>
</footer>

</main>
</div>
