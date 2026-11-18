<!--
  Einladung 4 · Handy
  Aus dem Design-Canvas „Caddy Control“ übernommen (Invite4m.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const steps = [
        { n: '1', title: 'Profil laden', text: 'Button unten antippen und „Erlauben“ wählen.', now: true },
        { n: '2', title: 'Einstellungen öffnen', text: '„Profil geladen“ → Installieren.' },
        { n: '3', title: 'Mit iPhone-Code bestätigen', text: 'Kein extra Passwort nötig.' },
        { n: '4', title: 'Fertig', text: 'Der Link ist danach verbraucht.' }
      ].map((s) => ({
        ...s,
        style: 'display: flex; gap: 12px; padding: 12px 14px; border-radius: 12px; ' + (s.now ? 'background: rgba(139,124,246,.10); border: 1px solid #8B7CF6;' : 'background: #161920; border: 1px solid #232833;'),
        numStyle: 'width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; ' + (s.now ? 'background: #E7E9EE; color: #0E1014;' : 'background: #232833; color: #E7E9EE;')
      }));
      const tests = ['filme.beispiel.de', 'rezepte.beispiel.de', 'fotos.beispiel.de'];
      return { steps, tests };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="width: 390px; height: 844px; box-sizing: border-box; display: flex; flex-direction: column; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 15px; overflow: hidden;">

<header style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 20px; border-bottom: 1px solid #1C2029;">
<div style="display: flex; align-items: center; gap: 8px;">
<div style="width: 28px; height: 28px; border-radius: 7px; background: #E7E9EE; display: flex; align-items: center; justify-content: center;">
<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0E1014" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
</div>
<span style="font-weight: 700;">Tesseract</span>
</div>
<span style="font-size: 13px; color: #A0A7B4;">Schritt 2 von 2</span>
</header>

<div style="flex: 1; display: flex; flex-direction: column; gap: 16px; padding: 18px 20px;">
<div style="display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 10px; background: rgba(76,195,138,.10); border: 1px solid #2F5C46; font-size: 14px;">
<span style="width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(76,195,138,.22); color: #7FD9AC;"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l9-10"></path></svg></span>
<span><strong style="font-weight: 600;">Freigegeben.</strong> <span style="color: #A0A7B4;">1 Jahr gültig.</span></span>
</div>

<h1 style="margin: 0; font-size: 24px; line-height: 1.2; font-weight: 700; letter-spacing: -0.02em;">Zertifikat installieren</h1>

<ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px;">
{#each dcv.steps as s}
<li style={s.style}>
<span style={s.numStyle}>{s.n}</span>
<span style="flex: 1; display: flex; flex-direction: column; gap: 2px;">
<span style="font-weight: 600; font-size: 15px;">{s.title}</span>
<span style="font-size: 13px; color: #A0A7B4; line-height: 1.45;">{s.text}</span>
</span>
</li>
{/each}
</ol>

<div style="display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="font-weight: 600; font-size: 14px;">Danach testen</span>
{#each dcv.tests as r}
<a href="#" style="display: flex; align-items: center; gap: 10px; min-height: 40px; text-decoration: none; color: #E7E9EE; border-top: 1px solid #232833;">
<span style="width: 18px; height: 18px; border-radius: 50%; flex-shrink: 0; border: 2px solid #3A4150;"></span>
<span style="flex: 1; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">{r}</span>
<span style="font-size: 13px; color: #B9AFFF;">öffnen</span>
</a>
{/each}
</div>
</div>

<div style="display: flex; flex-direction: column; gap: 10px; padding: 14px 20px 28px; border-top: 1px solid #1C2029;">
<button type="button" style="min-height: 52px; border-radius: 12px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; font-size: 16px; cursor: pointer;">Profil laden</button>
<a href="#" style="text-align: center; font-size: 13px; font-weight: 500;">Anleitung für Android, Windows oder macOS</a>
</div>

</div>
