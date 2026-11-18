<!--
  Login
  Aus dem Design-Canvas „Caddy Control“ übernommen (Login.dc.html).
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

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 15px;">

<section style="flex: 1 1 480px; min-width: 0; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; gap: 40px; padding: 48px 56px; background: #12151B; border-right: 1px solid #232833;">
<div style="display: flex; align-items: center; gap: 12px;">
<div style="width: 40px; height: 40px; border-radius: 10px; background: #E7E9EE; display: flex; align-items: center; justify-content: center;">
<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0E1014" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
</div>
<div style="display: flex; flex-direction: column;">
<span style="font-weight: 700; font-size: 18px;">Tesseract</span>
<span style="font-size: 13px; color: #A0A7B4;">Caddy-Verwaltung</span>
</div>
</div>

<div style="display: flex; flex-direction: column; gap: 16px; max-width: 480px;">
<h1 style="margin: 0; font-size: 40px; line-height: 1.1; font-weight: 700; letter-spacing: -0.02em;">Ein Webinterface für alle deine Caddy-Nodes.</h1>
<p style="margin: 0; color: #A0A7B4; line-height: 1.6;">Öffentliche Hosts mit Let's Encrypt, private Dienste nur für freigegebene Geräte – zentral verwaltet.</p>
</div>

<div style="display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px; border-radius: 12px; background: #161920; border: 1px solid #232833; max-width: 480px;">
<span style="width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(139,124,246,.18); color: #C9C1FF;"><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4"></path></svg></span>
<span style="font-size: 14px; color: #A0A7B4; line-height: 1.5;"><strong style="color: #E7E9EE; font-weight: 600;">Doppelt geschützt.</strong> Diese Seite ist selbst nur mit einem Admin-Gerätezertifikat erreichbar – das Passwort ist die zweite Hürde.</span>
</div>
</section>

<main style="flex: 1 1 480px; min-width: 0; box-sizing: border-box; display: flex; align-items: center; justify-content: center; padding: 48px 32px;">
<form style="width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 18px;">
<div style="display: flex; flex-direction: column; gap: 6px;">
<h2 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.02em;">Anmelden</h2>
<span style="display: inline-flex; align-items: center; gap: 8px; align-self: flex-start; padding: 5px 12px; border-radius: 999px; background: rgba(76,195,138,.12); color: #7FD9AC; font-size: 13px; font-weight: 600;"><span style="width: 7px; height: 7px; border-radius: 50%; background: #4CC38A;"></span>Admin-Gerät erkannt · ThinkPad</span>
</div>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: #A0A7B4;">Benutzername
<input type="text" autocomplete="username" value="admin" style="min-height: 48px; padding: 0 14px; border-radius: 10px; background: #161920; border: 1px solid #2E3440; color: #E7E9EE; font: inherit;">
</label>

<label style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: #A0A7B4;">Passwort
<input type="password" autocomplete="current-password" value="••••••••••••" style="min-height: 48px; padding: 0 14px; border-radius: 10px; background: #161920; border: 1px solid #8B7CF6; color: #E7E9EE; font: inherit;">
</label>

<label style="display: flex; align-items: center; gap: 10px; min-height: 44px; cursor: pointer; font-size: 14px;"><input type="checkbox" style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;">Auf diesem Gerät 30 Tage angemeldet bleiben</label>

<a href="#/" style="display: flex; align-items: center; justify-content: center; min-height: 50px; border-radius: 10px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Anmelden</a>

<div style="display: flex; align-items: center; gap: 12px; color: #A0A7B4; font-size: 13px;">
<span style="flex: 1; height: 1px; background: #232833;"></span>oder<span style="flex: 1; height: 1px; background: #232833;"></span>
</div>

<a href="#/" style="display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 50px; border-radius: 10px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">
<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11a4 4 0 1 0 0-8a4 4 0 0 0 0 8M3 21v-1a5 5 0 0 1 5-5h2M17 12a3 3 0 1 0 0 6a3 3 0 0 0 0-6M19.5 17.5L22 20M21 19l-1 1"></path></svg>
Mit Passkey anmelden
</a>

<p style="margin: 0; font-size: 13px; color: #A0A7B4; line-height: 1.5;">Passwort vergessen? Zurücksetzen geht nur auf dem Controller selbst: <code style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: #C9CED8;">tesseract admin reset</code></p>
</form>
</main>

</div>
