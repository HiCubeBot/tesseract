<!--
  Übersicht
  Aus dem Design-Canvas „Caddy Control“ übernommen (Main.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const C = { ok: '#7FD9AC', okDot: '#4CC38A', warn: '#F0BE6E', warnDot: '#E5A443', bad: '#F59A90', badDot: '#F07167', mtls: '#B9AFFF', mtlsDot: '#8B7CF6', muted: '#A0A7B4' };
      const dot = (c) => 'display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: ' + c + ';';
      const pill = (fg, bg) => 'display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const tone = { ok: [C.ok, C.okDot], warn: [C.warn, C.warnDot], bad: [C.bad, C.badDot] };
      const nodes = [
        { name: 'edge-fra', where: 'VPS · Frankfurt', caddy: '2.10.2', sync: 'synchron', syncTone: 'ok', hosts: 9, status: 'online', tone: 'ok' },
        { name: 'home-nas', where: 'Zuhause', caddy: '2.10.2', sync: 'synchron', syncTone: 'ok', hosts: 6, status: 'online', tone: 'ok' },
        { name: 'pi-eltern', where: 'Elternhaus', caddy: '2.9.1', sync: 'lokal geändert', syncTone: 'warn', hosts: 2, status: 'online', tone: 'ok' },
        { name: 'vps-hel', where: 'VPS · Helsinki', caddy: '2.10.2', sync: 'unbekannt', syncTone: 'bad', hosts: 1, status: 'offline · 14 Min.', tone: 'bad' }
      ].map((n) => ({
        ...n,
        dotStyle: dot(tone[n.tone][1]),
        statusStyle: 'color: ' + tone[n.tone][0] + ';',
        syncStyle: pill(tone[n.syncTone][0], n.syncTone === 'ok' ? 'rgba(76,195,138,.12)' : n.syncTone === 'warn' ? 'rgba(229,164,67,.14)' : 'rgba(240,113,103,.14)')
      }));
      const stats = [
        { label: 'Nodes online', value: '3 / 4', sub: 'vps-hel antwortet seit 14 Min. nicht', d: C.okDot, s: C.bad },
        { label: 'Hosts', value: '11 + 7', sub: 'öffentlich + nur mit Zertifikat (mTLS)', d: C.mtlsDot, s: C.muted },
        { label: 'Personen', value: '6', sub: '1 Einladung offen', d: C.mtlsDot, s: C.muted },
        { label: 'Geräte', value: '6 aktiv', sub: '1 gesperrt · 2 Zertifikate laufen bald ab', d: C.warnDot, s: C.warn }
      ].map((s) => ({ ...s, dotStyle: dot(s.d), subStyle: 'font-size: 13px; color: ' + s.s + ';' }));
      const expiring = [
        { title: 'iPhone von Anna', kind: 'Gerät', when: 'in 12 Tagen', t: 'warn' },
        { title: 'iPad von Opa', kind: 'Gerät', when: 'in 21 Tagen', t: 'warn' },
        { title: 'wiki.beispiel.de · Erneuerung fehlgeschlagen', kind: 'Host', when: 'in 9 Tagen', t: 'bad' }
      ].map((e) => ({ ...e, badgeStyle: pill(tone[e.t][0], e.t === 'warn' ? 'rgba(229,164,67,.14)' : 'rgba(240,113,103,.14)') }));
      const events = [
        { time: '10:42', title: 'Zugriff verweigert', detail: 'Unbekanntes Gerät an fotos.beispiel.de (home-nas)', t: 'bad' },
        { time: '10:20', title: 'Einladung geöffnet', detail: 'Dana hat den Einladungslink aufgerufen', t: 'mtls' },
        { time: '10:15', title: 'Konfiguration übertragen', detail: 'home-nas · 3 Änderungen', t: 'ok' },
        { time: '09:58', title: 'Gerät registriert', detail: 'Pixel 8 von Ben · gültig bis 17.11.2027', t: 'mtls' },
        { time: '09:31', title: 'Node offline', detail: 'vps-hel · letzter Kontakt 10:28', t: 'bad' },
        { time: 'gestern', title: 'Abweichung erkannt', detail: 'pi-eltern wurde lokal geändert', t: 'warn' }
      ].map((e) => ({ ...e, titleStyle: 'font-weight: 500; color: ' + ({ ok: '#E7E9EE', bad: C.bad, warn: C.warn, mtls: C.mtls })[e.t] + ';' }));
      return { nodes, stats, expiring, events };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="main" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 18px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Übersicht</h1>
<p style="margin: 0; color: #A0A7B4;">4 Nodes · 18 Hosts · 6 Personen mit 7 Geräten</p>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<a href="#/invite-1" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: #161920; color: #E7E9EE; font-weight: 500; text-decoration: none;">Person einladen</a>
<a href="#/host-new-1" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Host anlegen</a>
</div>
</header>

<section aria-label="Kennzahlen" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px;">
{#each dcv.stats as s}
<div style="display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; gap: 8px; color: #A0A7B4; font-size: 13px; font-weight: 500;">
<span style={s.dotStyle}></span>
<span>{s.label}</span>
</div>
<span style="font-size: 28px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums;">{s.value}</span>
<span style={s.subStyle}>{s.sub}</span>
</div>
{/each}
</section>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<div style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 18px;">
<section style="display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Nodes</h2>
<a href="#/nodes" style="font-size: 13px; font-weight: 500;">Alle Nodes</a>
</div>
<div style="overflow-x: auto;">
<table style="width: 100%; min-width: 600px; border-collapse: collapse; font-size: 14px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">
<th scope="col" style="padding: 8px 12px 8px 0; font-weight: 600;">Node</th>
<th scope="col" style="padding: 8px 12px; font-weight: 600;">Standort</th>
<th scope="col" style="padding: 8px 12px; font-weight: 600;">Caddy</th>
<th scope="col" style="padding: 8px 12px; font-weight: 600;">Konfiguration</th>
<th scope="col" style="padding: 8px 12px; font-weight: 600; text-align: right;">Hosts</th>
<th scope="col" style="padding: 8px 0 8px 12px; font-weight: 600;">Status</th>
</tr>
</thead>
<tbody>
{#each dcv.nodes as n}
<tr style="border-top: 1px solid #232833;">
<td style="padding: 11px 12px 11px 0; font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 500;">{n.name}</td>
<td style="padding: 11px 12px; color: #A0A7B4;">{n.where}</td>
<td style="padding: 11px 12px; color: #A0A7B4; font-variant-numeric: tabular-nums;">{n.caddy}</td>
<td style="padding: 11px 12px;"><span style={n.syncStyle}>{n.sync}</span></td>
<td style="padding: 11px 12px; text-align: right; font-variant-numeric: tabular-nums;">{n.hosts}</td>
<td style="padding: 11px 0 11px 12px;">
<span style="display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;"><span style={n.dotStyle}></span><span style={n.statusStyle}>{n.status}</span></span>
</td>
</tr>
{/each}
</tbody>
</table>
</div>
</section>

<section style="display: flex; flex-direction: column; gap: 4px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 style="margin: 0 0 4px; font-size: 15px; font-weight: 600;">Bald ablaufende Zertifikate</h2>
{#each dcv.expiring as e}
<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid #232833;">
<div style="display: flex; align-items: center; gap: 10px; min-width: 0;">
<span style="font-size: 12px; color: #A0A7B4; width: 64px; flex-shrink: 0;">{e.kind}</span>
<span style="font-weight: 500;">{e.title}</span>
</div>
<span style={e.badgeStyle}>{e.when}</span>
</div>
{/each}
</section>
</div>

<section style="flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 2px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">Letzte Ereignisse</h2>
{#each dcv.events as ev}
<div style="display: flex; gap: 12px; padding: 9px 0; border-top: 1px solid #232833;">
<span style="width: 52px; flex-shrink: 0; font-size: 12px; color: #A0A7B4; font-variant-numeric: tabular-nums; padding-top: 2px;">{ev.time}</span>
<div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
<span style={ev.titleStyle}>{ev.title}</span>
<span style="font-size: 13px; color: #A0A7B4;">{ev.detail}</span>
</div>
</div>
{/each}
</section>

</div>
</main>
</div>
