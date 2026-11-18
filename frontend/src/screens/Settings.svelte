<!--
  Einstellungen · Allgemein
  Aus dem Design-Canvas „Caddy Control“ übernommen (Settings.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const tabs = [
        ['Allgemein', '#/settings'], ['Integrationen', '#/settings-integrations'], ['Zertifizierungsstelle', '#/settings-ca'],
        ['Benachrichtigungen', '#/settings-notify'], ['Metriken', '#/settings-metrics'], ['Backup', '#/settings-backup']
      ].map(([label, href], i) => ({
        label, href, current: i === 0 ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 42px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (i === 0 ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const box = 'min-height: 36px; min-width: 190px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; flex-shrink: 0; ';
      const mono = box + "font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;";
      const plain = box + 'font-family: inherit; font-size: 13px;';
      const sw = (label, hint, on) => ({ label, hint, isSwitch: true, on: !!on, isSelect: false, isText: false });
      const sel = (label, hint, value, m) => ({ label, hint, value, isSelect: true, isSwitch: false, isText: false, valueStyle: m ? mono : plain });
      const txt = (label, hint, value, color) => ({ label, hint, value, isText: true, isSwitch: false, isSelect: false, valueStyle: 'font-size: 13px; font-weight: 500; white-space: nowrap; color: ' + (color || '#E7E9EE') + ';' });
      const cards = [
        { title: "Let's Encrypt", icon: 'M12 3l8 3v6c0 4.5-3.4 8.2-8 9c-4.6-.8-8-4.5-8-9V6z', rows: [
          sel('Kontakt-E-Mail', 'für Ablaufwarnungen von Let’s Encrypt', '[DEINE E-MAIL]', true),
          sel('Standard-Prüfung', 'HTTP-01 braucht Port 80, DNS-01 nicht', 'HTTP-01'),
          txt('DNS-API-Token', 'für DNS-01 und Wildcards', 'gesetzt · ändern', '#B9AFFF'),
          sw('Testumgebung (Staging)', 'für Experimente, Zertifikate sind nicht vertrauenswürdig', false)
        ] },
        { title: 'Geräte-Zertifikate (Standard)', icon: 'M7 3h10v18H7zM11 18h2', rows: [
          sel('Laufzeit', 'pro Person änderbar', 'Unbegrenzt (99 Jahre)'),
          sel('Schlüsseltyp', 'ECDSA ist kleiner und schneller', 'ECDSA P-256', true),
          sel('Geräte pro Person', 'selbst registrierbar über den Einladungslink', '3'),
          sw('Neue Geräte manuell freigeben', 'sonst sofort aktiv nach korrektem Code', true)
        ] },
        { title: 'Admin-Zugang', icon: 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4', rows: [
          sw('Nur mit Admin-Gerätezertifikat', 'die Oberfläche ist sonst nicht erreichbar', true),
          txt('Passkeys', 'ThinkPad, iPhone', '2 registriert · verwalten', '#B9AFFF'),
          sel('Sitzung läuft ab nach', 'Inaktivität', '8 Stunden'),
          sel('Sperre nach Fehlversuchen', 'pro IP-Adresse, 15 Minuten', '5 Versuche')
        ] },
        { title: 'Controller', icon: 'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01', rows: [
          sel('Adresse', 'hier erreichen Nodes und Admins den Controller', 'tesseract.beispiel.de', true),
          sel('Zeitzone', 'für Zeitpläne und das Audit-Log', 'Europe/Berlin'),
          sel('Audit-Log aufbewahren', 'ältere Einträge werden gelöscht', '365 Tage'),
          sw('Nach Updates suchen', 'für Controller und Agenten', true)
        ] }
      ];
      return { tabs, cards };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="settings" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 16px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Einstellungen</h1>
<p style="margin: 0; color: #A0A7B4;">Gilt für den Controller und als Standard für alle Nodes.</p>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: #161920; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Verwerfen</button>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Speichern</button>
</div>
</header>

<nav aria-label="Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px;">
{#each dcv.cards as c}
<section style="display: flex; flex-direction: column; padding: 14px 18px 6px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
<span style="width: 30px; height: 30px; border-radius: 8px; background: #232833; display: inline-flex; align-items: center; justify-content: center; color: #C9CED8;"><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d={c.icon}></path></svg></span>
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">{c.title}</h2>
</div>
{#each c.rows as r}
<div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 50px; border-top: 1px solid #1E222B;">
<div style="display: flex; flex-direction: column; gap: 1px; min-width: 0;">
<span style="font-weight: 500;">{r.label}</span>
<span style="font-size: 12px; color: #A0A7B4;">{r.hint}</span>
</div>
{#if r.isSwitch}
<input type="checkbox" role="switch" aria-label={r.label} checked={r.on} style="width: 20px; height: 20px; margin: 0; accent-color: #8B7CF6; flex-shrink: 0;">
{/if}
{#if r.isSelect}
<select aria-label={r.label} style={r.valueStyle}><option>{r.value}</option></select>
{/if}
{#if r.isText}
<span style={r.valueStyle}>{r.value}</span>
{/if}
</div>
{/each}
</section>
{/each}
</div>

</main>
</div>
