<!--
  Einladung 3 · Gast: Gerät registrieren
  Aus dem Design-Canvas „Caddy Control“ übernommen (Invite3.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      return {};
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
<span style="font-size: 13px; color: #A0A7B4;">Schritt 1 von 2 · Gerät registrieren</span>
</header>

<div style="flex: 1; display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 64px; padding: 40px 48px; max-width: 1200px; width: 100%; box-sizing: border-box; margin: 0 auto;">

<section style="flex: 1 1 380px; min-width: 0; display: flex; flex-direction: column; gap: 20px;">
<h1 style="margin: 0; font-size: 40px; line-height: 1.1; font-weight: 700; letter-spacing: -0.02em;">Hallo Dana,<br>du wurdest eingeladen.</h1>
<p style="margin: 0; color: #A0A7B4; line-height: 1.6; max-width: 460px;">Diese Dienste sind privat und nur von freigeschalteten Geräten aus erreichbar. Dafür bekommt dein Gerät gleich ein eigenes Zertifikat – wie ein Schlüssel, den nur es selbst hat.</p>
<div style="display: flex; flex-direction: column; gap: 8px;">
<span style="font-size: 13px; color: #A0A7B4;">Danach kommst du auf:</span>
<div style="display: flex; flex-wrap: wrap; gap: 8px;">
<span style="padding: 6px 12px; border-radius: 8px; background: #161920; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">filme.beispiel.de</span>
<span style="padding: 6px 12px; border-radius: 8px; background: #161920; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">rezepte.beispiel.de</span>
<span style="padding: 6px 12px; border-radius: 8px; background: #161920; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">fotos.beispiel.de</span>
</div>
</div>
</section>

<form style="flex: 1 1 420px; max-width: 460px; min-width: 0; display: flex; flex-direction: column; gap: 18px; padding: 28px; border-radius: 16px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 10px; background: #0E1014; border: 1px solid #232833;">
<span style="width: 38px; height: 38px; border-radius: 9px; background: #232833; display: inline-flex; align-items: center; justify-content: center; color: #C9CED8;"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h10v18H7zM11 18h2"></path></svg></span>
<span style="flex: 1; display: flex; flex-direction: column;">
<span style="font-weight: 600;">iPhone · iOS 18</span>
<span style="font-size: 13px; color: #A0A7B4;">automatisch erkannt</span>
</span>
<span style="font-size: 13px; color: #A0A7B4;">Gerät 1 von 2</span>
</div>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: #A0A7B4;">Wie soll dieses Gerät heißen?
<input type="text" value="Danas iPhone" style="min-height: 48px; padding: 0 14px; border-radius: 10px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 16px;">
</label>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: #A0A7B4;">Bestätigungscode
<input type="text" inputmode="numeric" value="481 207" style="min-height: 48px; padding: 0 14px; border-radius: 10px; background: #0E1014; border: 1px solid #8B7CF6; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 20px; letter-spacing: 0.12em;">
<span style="font-size: 13px;">Den Code hast du separat bekommen (z. B. am Telefon).</span>
</label>

<a href="#/invite-4" style="display: flex; align-items: center; justify-content: center; min-height: 50px; border-radius: 10px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Gerät registrieren</a>
<span style="font-size: 13px; color: #A0A7B4; line-height: 1.5;">Der Schlüssel wird nur für dieses Gerät erzeugt. Geht es verloren, kann es einzeln gesperrt werden.</span>
</form>

</div>
</div>
