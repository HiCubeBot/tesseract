<!--
  Host anlegen 2 · Zugriff
  Aus dem Design-Canvas „Caddy Control“ übernommen (HostNew2.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const step = 2;
      const steps = ['Domain & Ziel', 'Zugriff', 'Prüfen & übertragen'].map((label, i) => {
        const n = i + 1, on = n === step, done = n < step;
        return {
          n: done ? '✓' : String(n), label, current: on ? 'step' : 'false',
          style: 'display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 14px 0 6px; border-radius: 999px; font-size: 13px; font-weight: 500; ' + (on ? 'background: #232833; color: #E7E9EE;' : 'color: #A0A7B4;'),
          numStyle: 'width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; ' + (on ? 'background: #E7E9EE; color: #0E1014;' : done ? 'background: rgba(76,195,138,.18); color: #7FD9AC;' : 'background: transparent; border: 1px solid #3A4150; color: #A0A7B4;')
        };
      });
      const av = (group, dim) => 'width: 30px; height: 30px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; border-radius: ' + (group ? '8px' : '50%') + '; ' + (dim ? 'background: #2A2F3A; color: #A0A7B4;' : group ? 'background: #2A2F3A; color: #E7E9EE;' : 'background: rgba(139,124,246,.22); color: #D6D0FF;');
      const picks = [
        { name: 'Gruppe Familie', initials: 'FA', sub: 'Anna, Clara, Opa', devices: '4 Geräte', checked: true, group: true },
        { name: 'Gruppe Freunde', initials: 'FR', sub: 'Ben, Dana, Erik', devices: '3 Geräte', group: true },
        { name: 'Ben', initials: 'BE', sub: 'Freunde', devices: 'ThinkPad, Pixel 8', checked: true },
        { name: 'Dana', initials: 'DA', sub: 'Freunde · Einladung offen', devices: 'noch kein Gerät' },
        { name: 'Erik', initials: 'ER', sub: 'gesperrt', devices: '–', disabled: true }
      ].map((p) => ({
        ...p, checked: !!p.checked, disabled: !!p.disabled,
        avatarStyle: av(p.group, p.disabled),
        rowStyle: 'display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 4px 10px; border-radius: 8px; cursor: pointer; border-top: 1px solid #232833;' + (p.checked ? ' background: rgba(139,124,246,.08);' : '') + (p.disabled ? ' opacity: 0.55; cursor: not-allowed;' : '')
      }));
      const devices = ['Anna · MacBook Air', 'Anna · iPhone 15', 'Clara · MacBook Pro', 'Opa · iPad', 'Ben · ThinkPad', 'Ben · Pixel 8'];
      return { steps, picks, devices };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="hosts" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 18px;">

<header style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<span style="font-size: 13px; color: #A0A7B4; font-family: 'JetBrains Mono', ui-monospace, monospace;">musik.beispiel.de → home-nas · 10.0.1.20:4533</span>
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Wer darf zugreifen?</h1>
</div>
<ol aria-label="Schritte" style="margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px;">
{#each dcv.steps as st}
<li aria-current={st.current} style={st.style}><span style={st.numStyle}>{st.n}</span>{st.label}</li>
{/each}
</ol>
</header>

<div role="radiogroup" aria-label="Zugriffsart" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
<label style="display: flex; gap: 14px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #2E3440; cursor: pointer;">
<input type="radio" name="mode" style="margin: 3px 0 0; accent-color: #8B7CF6;">
<span style="display: flex; flex-direction: column; gap: 3px;">
<span style="font-weight: 600; font-size: 15px;">Öffentlich</span>
<span style="font-size: 13px; color: #A0A7B4;">Jeder mit der Adresse. Server-Zertifikat von Let's Encrypt, sonst keine Hürde.</span>
</span>
</label>
<label style="display: flex; gap: 14px; padding: 16px 18px; border-radius: 12px; background: rgba(139,124,246,.10); border: 1px solid #8B7CF6; cursor: pointer;">
<input type="radio" name="mode" checked style="margin: 3px 0 0; accent-color: #8B7CF6;">
<span style="display: flex; flex-direction: column; gap: 3px;">
<span style="font-weight: 600; font-size: 15px;">Nur freigegebene Geräte (mTLS)</span>
<span style="font-size: 13px; color: #A0A7B4;">Ohne gültiges Geräte-Zertifikat kommt keine Verbindung zustande – auch keine Login-Seite.</span>
</span>
</label>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<section aria-labelledby="pick-title" style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 4px; padding: 18px 20px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px;">
<h2 id="pick-title" style="margin: 0; font-size: 15px; font-weight: 600;">Gruppen &amp; Personen freigeben</h2>
<span style="font-size: 12px; color: #A0A7B4;">Freigabe gilt für alle Geräte der Person</span>
</div>
{#each dcv.picks as p}
<label style={p.rowStyle}>
<input type="checkbox" checked={p.checked} disabled={p.disabled} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">
<span style={p.avatarStyle}>{p.initials}</span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column;">
<span style="font-weight: 500;">{p.name}</span>
<span style="font-size: 12px; color: #A0A7B4;">{p.sub}</span>
</span>
<span style="font-size: 12px; color: #A0A7B4; white-space: nowrap;">{p.devices}</span>
</label>
{/each}
</section>

<aside aria-label="Ergebnis" style="flex: 1 1 320px; min-width: 0; display: flex; flex-direction: column; gap: 12px; padding: 18px 20px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Ergebnis</h2>
<div style="display: flex; gap: 20px;">
<div style="display: flex; flex-direction: column;"><span style="font-size: 26px; font-weight: 700;">4</span><span style="font-size: 12px; color: #A0A7B4;">Personen</span></div>
<div style="display: flex; flex-direction: column;"><span style="font-size: 26px; font-weight: 700;">6</span><span style="font-size: 12px; color: #A0A7B4;">Geräte</span></div>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 6px;">
{#each dcv.devices as d}
<span style="padding: 4px 10px; border-radius: 6px; background: #0E1014; border: 1px solid #232833; font-size: 12px;">{d}</span>
{/each}
</div>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4; margin-top: 4px;">Ohne passendes Zertifikat
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>Verbindung ablehnen</option>
<option>Hinweisseite „Kein Zugang“</option>
</select>
</label>
</aside>

</div>

<footer style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: auto;">
<a href="#/host-new-1" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Zurück</a>
<a href="#/host-new-3" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Weiter: Prüfen</a>
</footer>

</main>
</div>
