<!--
  Einladung 3 · Handy
  Aus dem Design-Canvas „Caddy Control“ übernommen (Invite3m.dc.html).
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

<div style="width: 390px; height: 844px; box-sizing: border-box; display: flex; flex-direction: column; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 15px; overflow: hidden;">

<header style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 20px; border-bottom: 1px solid #1C2029;">
<div style="display: flex; align-items: center; gap: 8px;">
<div style="width: 28px; height: 28px; border-radius: 7px; background: #E7E9EE; display: flex; align-items: center; justify-content: center;">
<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0E1014" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
</div>
<span style="font-weight: 700;">Tesseract</span>
</div>
<span style="font-size: 13px; color: #A0A7B4;">Schritt 1 von 2</span>
</header>

<div style="flex: 1; display: flex; flex-direction: column; gap: 20px; padding: 24px 20px;">
<div style="display: flex; flex-direction: column; gap: 10px;">
<h1 style="margin: 0; font-size: 28px; line-height: 1.15; font-weight: 700; letter-spacing: -0.02em;">Hallo Dana,<br>du wurdest eingeladen.</h1>
<p style="margin: 0; color: #A0A7B4; line-height: 1.55; font-size: 15px;">Dein Handy bekommt gleich ein eigenes Zertifikat – wie ein Schlüssel, den nur es selbst hat.</p>
</div>

<div style="display: flex; flex-wrap: wrap; gap: 6px;">
<span style="padding: 5px 10px; border-radius: 7px; background: #161920; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">filme</span>
<span style="padding: 5px 10px; border-radius: 7px; background: #161920; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">rezepte</span>
<span style="padding: 5px 10px; border-radius: 7px; background: #161920; border: 1px solid #232833; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">fotos</span>
<span style="padding: 5px 4px; font-size: 12px; color: #A0A7B4;">.beispiel.de</span>
</div>

<form style="display: flex; flex-direction: column; gap: 16px;">
<div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="width: 36px; height: 36px; border-radius: 9px; background: #232833; display: inline-flex; align-items: center; justify-content: center; color: #C9CED8;"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h10v18H7zM11 18h2"></path></svg></span>
<span style="flex: 1; display: flex; flex-direction: column;">
<span style="font-weight: 600;">iPhone · iOS 18</span>
<span style="font-size: 13px; color: #A0A7B4;">erkannt · Gerät 1 von 2</span>
</span>
</div>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: #A0A7B4;">Name dieses Geräts
<input type="text" value="Danas iPhone" style="min-height: 50px; padding: 0 14px; border-radius: 12px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 17px;">
</label>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: #A0A7B4;">Bestätigungscode
<input type="text" inputmode="numeric" value="481 207" style="min-height: 54px; padding: 0 14px; border-radius: 12px; background: #161920; border: 1px solid #8B7CF6; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 22px; letter-spacing: 0.14em; text-align: center;">
<span style="font-size: 13px;">Den Code hast du separat bekommen.</span>
</label>
</form>
</div>

<div style="display: flex; flex-direction: column; gap: 10px; padding: 16px 20px 28px; border-top: 1px solid #1C2029;">
<a href="#/invite-4m" style="display: flex; align-items: center; justify-content: center; min-height: 52px; border-radius: 12px; background: #E7E9EE; color: #0E1014; font-weight: 600; font-size: 16px; text-decoration: none;">Gerät registrieren</a>
<span style="font-size: 12px; color: #A0A7B4; text-align: center; line-height: 1.45;">Geht das Handy verloren, wird nur dieses Gerät gesperrt.</span>
</div>

</div>
