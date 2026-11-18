<!--
  Einladung 1 · Admin: Person anlegen
  Aus dem Design-Canvas „Caddy Control“ übernommen (Invite1.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const step = 1;
      const steps = ['Person anlegen', 'Link teilen'].map((label, i) => {
        const n = i + 1, on = n === step, done = n < step;
        return {
          n: done ? '✓' : String(n), label, current: on ? 'step' : 'false',
          style: 'display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 14px 0 6px; border-radius: 999px; font-size: 13px; font-weight: 500; ' + (on ? 'background: #232833; color: #E7E9EE;' : 'color: #A0A7B4;'),
          numStyle: 'width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; ' + (on ? 'background: #E7E9EE; color: #0E1014;' : done ? 'background: rgba(76,195,138,.18); color: #7FD9AC;' : 'background: transparent; border: 1px solid #3A4150; color: #A0A7B4;')
        };
      });
      const services = [
        { id: 'filme', note: 'über Gruppe Freunde', checked: true, fixed: true },
        { id: 'rezepte', note: 'über Gruppe Freunde', checked: true, fixed: true },
        { id: 'fotos', note: 'zusätzlich', checked: true },
        { id: 'kalender', note: '' },
        { id: 'dateien', note: '' },
        { id: 'home', note: '' }
      ].map((s) => ({
        ...s, checked: !!s.checked, fixed: !!s.fixed,
        style: 'display: flex; align-items: center; gap: 10px; min-height: 52px; padding: 6px 12px; border-radius: 8px; cursor: pointer; ' + (s.checked ? 'background: rgba(139,124,246,.08); border: 1px solid #3A3460;' : 'background: #0E1014; border: 1px solid #2E3440;')
      }));
      const how = [
        { n: '1', title: 'Du teilst einen Link', text: 'Per Messenger oder als QR-Code. Den Bestätigungscode sagst du Dana separat.' },
        { n: '2', title: 'Dana registriert ihr Gerät', text: 'Sie gibt dem Gerät einen Namen. Das Zertifikat wird für genau dieses Gerät ausgestellt.' },
        { n: '3', title: 'Du bestätigst', text: 'Neue Geräte erscheinen unter Geräte als „wartet auf Freigabe“.' },
        { n: '4', title: 'Weitere Geräte', text: 'Über denselben Link kann Dana bis zu 2 Geräte hinzufügen.' }
      ];
      return { steps, services, how };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="users" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 18px;">

<header style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<a href="#/users" style="font-size: 13px; font-weight: 500; text-decoration: none;">← Nutzer</a>
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Person einladen</h1>
</div>
<ol aria-label="Schritte" style="margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px;">
{#each dcv.steps as st}
<li aria-current={st.current} style={st.style}><span style={st.numStyle}>{st.n}</span>{st.label}</li>
{/each}
</ol>
</header>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<section aria-label="Angaben zur Person" style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 18px; padding: 20px 22px; border-radius: 12px; background: #161920; border: 1px solid #232833;">

<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px;">
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Name
<input type="text" value="Dana" style="min-height: 44px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #8B7CF6; color: #E7E9EE; font: inherit; font-size: 15px;">
</label>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Gruppe
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>Freunde</option><option>Familie</option><option>Keine Gruppe</option>
</select>
</label>
</div>

<fieldset style="margin: 0; padding: 0; border: none; display: flex; flex-direction: column; gap: 8px;">
<legend style="padding: 0; margin-bottom: 8px; font-size: 13px; color: #A0A7B4;">Zugriff auf Dienste</legend>
<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px;">
{#each dcv.services as s}
<label style={s.style}>
<input type="checkbox" checked={s.checked} disabled={s.fixed} style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">
<span style="display: flex; flex-direction: column;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">{s.id}</span>
<span style="font-size: 12px; color: #A0A7B4;">{s.note}</span>
</span>
</label>
{/each}
</div>
</fieldset>

<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px;">
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Geräte, die Dana selbst registrieren darf
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>1</option><option selected>2</option><option>3</option><option>5</option>
</select>
</label>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Laufzeit je Geräte-Zertifikat
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>6 Monate</option><option selected>1 Jahr</option><option>2 Jahre</option><option>5 Jahre</option><option>Unbegrenzt (99 Jahre)</option>
</select>
<span style="font-size: 12px;">Auch „unbegrenzt“ lässt sich jederzeit sperren.</span>
</label>
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Einladung gültig
<select style="min-height: 44px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 14px;">
<option>24 Stunden</option><option selected>7 Tage</option><option>30 Tage</option>
</select>
</label>
</div>

<label style="display: flex; align-items: center; gap: 10px; min-height: 44px; cursor: pointer;"><input type="checkbox" checked style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">Neue Geräte erst nach meiner Bestätigung freischalten</label>
</section>

<aside aria-label="So funktioniert es" style="flex: 1 1 320px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 20px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Was danach passiert</h2>
<ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 14px;">
{#each dcv.how as h}
<li style="display: flex; gap: 12px;">
<span style="width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: #232833; font-size: 12px; font-weight: 700;">{h.n}</span>
<span style="display: flex; flex-direction: column; gap: 2px;">
<span style="font-weight: 500;">{h.title}</span>
<span style="font-size: 13px; color: #A0A7B4; line-height: 1.45;">{h.text}</span>
</span>
</li>
{/each}
</ol>
</aside>

</div>

<footer style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: auto;">
<a href="#/users" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Abbrechen</a>
<a href="#/invite-2" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Einladung erstellen</a>
</footer>

</main>
</div>
