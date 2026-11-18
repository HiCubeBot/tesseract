<!--
  Einladung 4 · Gast: Zertifikat installieren
  Aus dem Design-Canvas „Caddy Control“ übernommen (Invite4.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const tabs = ['iPhone / iPad', 'Android', 'Windows', 'macOS'].map((label, i) => ({
        label, pressed: i === 0 ? 'true' : 'false',
        style: 'min-height: 38px; padding: 0 14px; border-radius: 7px; border: none; font: inherit; font-size: 14px; font-weight: 500; cursor: pointer; ' + (i === 0 ? 'background: #2A2F3A; color: #E7E9EE;' : 'background: transparent; color: #A0A7B4;')
      }));
      const steps = [
        { n: '1', title: 'Profil laden', text: 'Lädt ein Konfigurationsprofil mit deinem Geräte-Zertifikat herunter.', hasButton: true, button: 'Profil laden' },
        { n: '2', title: 'In den Einstellungen öffnen', text: 'Einstellungen → „Profil geladen“ antippen → Installieren.', hasButton: false },
        { n: '3', title: 'Mit deinem iPhone-Code bestätigen', text: 'Ein extra Passwort brauchst du nicht – es steckt bereits im Profil.', hasButton: false },
        { n: '4', title: 'Fertig', text: 'Der Download-Link ist jetzt verbraucht. Das Zertifikat bleibt nur auf diesem iPhone.', hasButton: false }
      ];
      const tests = ['filme.beispiel.de', 'rezepte.beispiel.de', 'fotos.beispiel.de'];
      return { tabs, steps, tests };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; box-sizing: border-box; display: flex; flex-direction: column; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 15px;">

<header style="display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 48px; border-bottom: 1px solid #1C2029;">
<div style="display: flex; align-items: center; gap: 10px;">
<div style="width: 32px; height: 32px; border-radius: 8px; background: #E7E9EE; display: flex; align-items: center; justify-content: center;">
<svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#0E1014" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
</div>
<span style="font-weight: 700;">Tesseract</span>
</div>
<span style="font-size: 13px; color: #A0A7B4;">Schritt 2 von 2 · Zertifikat installieren</span>
</header>

<div style="flex: 1; display: flex; flex-wrap: wrap; align-items: flex-start; gap: 28px; padding: 28px 48px; max-width: 1280px; width: 100%; box-sizing: border-box; margin: 0 auto;">

<section aria-labelledby="install-title" style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 18px;">
<div style="display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 10px; background: rgba(76,195,138,.10); border: 1px solid #2F5C46;">
<span style="width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(76,195,138,.22); color: #7FD9AC;"><svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l9-10"></path></svg></span>
<span><strong style="font-weight: 600;">„Danas iPhone“ wurde freigegeben.</strong> <span style="color: #A0A7B4;">Das Zertifikat ist 1 Jahr gültig.</span></span>
</div>

<h1 id="install-title" style="margin: 0; font-size: 30px; font-weight: 700; letter-spacing: -0.02em;">Zertifikat auf dem iPhone installieren</h1>

<div role="group" aria-label="Anleitung für" style="display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 10px; background: #161920; border: 1px solid #232833; align-self: flex-start;">
{#each dcv.tabs as t}
<button type="button" aria-pressed={t.pressed} style={t.style}>{t.label}</button>
{/each}
</div>

<ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px;">
{#each dcv.steps as s}
<li style="display: flex; gap: 14px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: #232833; font-size: 13px; font-weight: 700;">{s.n}</span>
<span style="flex: 1; display: flex; flex-direction: column; gap: 3px;">
<span style="font-weight: 600;">{s.title}</span>
<span style="font-size: 14px; color: #A0A7B4; line-height: 1.5;">{s.text}</span>
</span>
{#if s.hasButton}
<button type="button" style="align-self: center; min-height: 44px; padding: 0 18px; border-radius: 9px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">{s.button}</button>
{/if}
</li>
{/each}
</ol>
</section>

<aside aria-labelledby="test-title" style="flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 22px; border-radius: 16px; background: #161920; border: 1px solid #232833;">
<h2 id="test-title" style="margin: 0; font-size: 17px; font-weight: 600;">Hat es geklappt?</h2>
<p style="margin: 0; font-size: 14px; color: #A0A7B4; line-height: 1.5;">Nach der Installation hier testen. Safari fragt einmal, welches Zertifikat es verwenden soll – „Danas iPhone“ wählen.</p>
<button type="button" style="min-height: 48px; border-radius: 10px; border: 1px solid #2E3440; background: #0E1014; color: #E7E9EE; font: inherit; font-weight: 600; cursor: pointer;">Verbindung testen</button>
<div style="display: flex; flex-direction: column;">
{#each dcv.tests as r}
<a href="#" style="display: flex; align-items: center; gap: 10px; min-height: 44px; border-top: 1px solid #232833; text-decoration: none; color: #E7E9EE;">
<span style="width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(76,195,138,.18); color: #7FD9AC;"><svg aria-hidden="true" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l9-10"></path></svg></span>
<span style="flex: 1; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">{r}</span>
<span style="font-size: 13px; color: #B9AFFF;">öffnen</span>
</a>
{/each}
</div>
<div style="display: flex; flex-direction: column; gap: 6px; padding-top: 12px; border-top: 1px solid #232833;">
<span style="font-weight: 600; font-size: 14px;">Noch ein Gerät?</span>
<span style="font-size: 13px; color: #A0A7B4; line-height: 1.5;">Öffne denselben Einladungslink auf deinem Laptop – 1 von 2 Plätzen ist noch frei.</span>
</div>
</aside>

</div>
</div>
