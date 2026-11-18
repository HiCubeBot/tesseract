<!--
  Host · Sicherheit (IP-Filter, Coraza, Authelia)
  Aus dem Design-Canvas „Caddy Control“ übernommen (HostSecurity.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const active = 'security';
      const tabs = [
        { id: 'general', label: 'Allgemein', href: '#/hosts' },
        { id: 'access', label: 'Zugriff', href: '#/hosts' },
        { id: 'security', label: 'Sicherheit', href: '#/host-security' },
        { id: 'history', label: 'Verlauf · 12', href: '#/host-history' }
      ].map((t) => ({
        ...t, current: t.id === active ? 'page' : 'false',
        style: 'display: inline-flex; align-items: center; min-height: 40px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (t.id === active ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;')
      }));
      const on = 'padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 600; background: rgba(139,124,246,.14); border: 1px solid #5B4FB0; color: #E7E9EE;';
      const off = 'padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 500; background: transparent; border: 1px dashed #3A4150; color: #A0A7B4;';
      const end = 'padding: 6px 12px; border-radius: 8px; font-size: 13px; font-family: \'JetBrains Mono\', ui-monospace, monospace; background: #0E1014; border: 1px solid #2E3440; color: #C9CED8;';
      const pipe = [
        { label: 'Client', style: end, arrow: true },
        { label: "TLS · Let's Encrypt", style: on, arrow: true },
        { label: 'IP-Filter', style: on, arrow: true },
        { label: 'Coraza WAF', style: on, arrow: true },
        { label: 'Authelia', style: on, arrow: true },
        { label: '127.0.0.1:3000', style: end, arrow: false }
      ];
      const mono = "font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px; font-weight: 500;";
      const ips = [
        { value: 'Liste „Scanner“', note: '14 Einträge · global gepflegt', valueStyle: 'font-size: 13px; font-weight: 600; color: #C9C1FF;' },
        { value: '203.0.113.17', note: 'Brute-Force · manuell · heute 10:31', valueStyle: mono },
        { value: '198.51.100.0/24', note: 'Auto-Sperre · endet in 18 h', valueStyle: mono }
      ].map((ip) => ({ ...ip, removeLabel: ip.value + ' entfernen' }));
      return { tabs, pipe, ips };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="hosts" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 22px 32px; display: flex; flex-direction: column; gap: 14px;">

<header style="display: flex; flex-direction: column; gap: 10px;">
<div style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<a href="#/hosts" style="font-size: 13px; font-weight: 500; text-decoration: none;">← Proxy-Hosts</a>
<div style="display: flex; align-items: center; gap: 12px;">
<h1 style="margin: 0; font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', ui-monospace, monospace;">git.beispiel.de</h1>
<span style="padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #7FD9AC; background: rgba(76,195,138,.12);">Öffentlich · edge-fra</span>
</div>
</div>
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Speichern &amp; übertragen</button>
</div>
<nav aria-label="Host-Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>
</header>

<section aria-label="Weg einer Anfrage" style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 12px 14px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<span style="font-size: 12px; color: #A0A7B4; margin-right: 6px;">Weg einer Anfrage</span>
{#each dcv.pipe as p}
<span style="display: inline-flex; align-items: center; gap: 6px;">
<span style={p.style}>{p.label}</span>
{#if p.arrow}
<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#5E6573" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6l-6 6"></path></svg>
{/if}
</span>
{/each}
</section>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; align-items: start;">

<section aria-labelledby="ip-title" style="display: flex; flex-direction: column; gap: 12px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="ip-title" style="margin: 0; font-size: 15px; font-weight: 600;">IP-Filter</h2>
<span style="font-size: 12px; color: #A0A7B4;">3 Regeln</span>
</div>
<div role="radiogroup" aria-label="IP-Filter-Modus" style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; padding: 4px; border-radius: 9px; background: #0E1014; border: 1px solid #232833;">
<label style="display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; border-radius: 6px; color: #A0A7B4; font-size: 13px; cursor: pointer;"><input type="radio" name="ipmode" style="margin: 0; accent-color: #8B7CF6;">Aus</label>
<label style="display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; border-radius: 6px; color: #A0A7B4; font-size: 13px; cursor: pointer;"><input type="radio" name="ipmode" style="margin: 0; accent-color: #8B7CF6;">Nur erlauben</label>
<label style="display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; border-radius: 6px; background: #2A2F3A; color: #E7E9EE; font-size: 13px; font-weight: 600; cursor: pointer;"><input type="radio" name="ipmode" checked style="margin: 0; accent-color: #8B7CF6;">Sperren</label>
</div>
<div style="display: flex; flex-direction: column;">
{#each dcv.ips as ip}
<div style="display: flex; align-items: center; gap: 10px; min-height: 48px; border-top: 1px solid #1E222B;">
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px;">
<span style={ip.valueStyle}>{ip.value}</span>
<span style="font-size: 12px; color: #A0A7B4;">{ip.note}</span>
</div>
<button type="button" aria-label={ip.removeLabel} style="width: 32px; height: 32px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #A0A7B4; cursor: pointer; display: inline-flex; align-items: center; justify-content: center;"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg></button>
</div>
{/each}
</div>
<div style="display: flex; gap: 8px;">
<label style="flex: 1; min-width: 0; display: flex;">
<span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">IP, Netz oder Liste hinzufügen</span>
<input type="text" placeholder="IP, CIDR oder Liste" style="flex: 1; min-width: 0; min-height: 40px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">
</label>
<button type="button" style="min-height: 40px; padding: 0 14px; border-radius: 8px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Hinzufügen</button>
</div>
<label style="display: flex; align-items: flex-start; gap: 10px; padding-top: 10px; border-top: 1px solid #1E222B; cursor: pointer;">
<input type="checkbox" role="switch" checked style="width: 18px; height: 18px; margin: 1px 0 0; accent-color: #8B7CF6;">
<span style="display: flex; flex-direction: column; gap: 1px;"><span style="font-weight: 500;">Auto-Sperre</span><span style="font-size: 12px; color: #A0A7B4;">IP für 24 h sperren nach 20 WAF-Treffern in 10 Min.</span></span>
</label>
</section>

<section aria-labelledby="waf-title" style="display: flex; flex-direction: column; gap: 12px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="waf-title" style="margin: 0; font-size: 15px; font-weight: 600;">Coraza WAF</h2>
<label style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: #A0A7B4; cursor: pointer;">Aktiv<input type="checkbox" role="switch" checked style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;"></label>
</div>
<div role="radiogroup" aria-label="WAF-Modus" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; padding: 4px; border-radius: 9px; background: #0E1014; border: 1px solid #232833;">
<label style="display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; border-radius: 6px; color: #A0A7B4; font-size: 13px; cursor: pointer;"><input type="radio" name="wafmode" style="margin: 0; accent-color: #8B7CF6;">Nur protokollieren</label>
<label style="display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; border-radius: 6px; background: #2A2F3A; color: #E7E9EE; font-size: 13px; font-weight: 600; cursor: pointer;"><input type="radio" name="wafmode" checked style="margin: 0; accent-color: #8B7CF6;">Blockieren</label>
</div>
<div style="display: flex; flex-direction: column;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Regelsatz</span><span style="font-size: 12px; color: #A0A7B4;">OWASP Core Rule Set</span></span>
<span style="font-size: 13px; color: #C9CED8;">mitgeliefert</span>
</div>
<label style="display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Paranoia-Level</span><span style="font-size: 12px; color: #A0A7B4;">höher = strenger, mehr Fehlalarme</span></span>
<select style="min-height: 36px; padding: 0 10px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font: inherit; font-size: 13px;"><option>1 · Standard</option><option>2</option><option>3</option><option>4</option></select>
</label>
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Regel-Ausnahmen</span><span style="font-size: 12px; color: #A0A7B4;">für Fehlalarme dieses Dienstes</span></span>
<a href="#" style="font-size: 13px; font-weight: 500;">2 · bearbeiten</a>
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px;">
<div style="display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border-radius: 8px; background: #0E1014;"><span style="font-size: 20px; font-weight: 700; color: #F59A90;">37</span><span style="font-size: 12px; color: #A0A7B4;">blockiert · 24 h</span></div>
<div style="display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border-radius: 8px; background: #0E1014;"><span style="font-size: 20px; font-weight: 700;">2</span><span style="font-size: 12px; color: #A0A7B4;">IPs auto-gesperrt</span></div>
</div>
<a href="#/logs" style="font-size: 13px; font-weight: 500;">Treffer in den Logs ansehen</a>
</section>

<section aria-labelledby="auth-title" style="display: flex; flex-direction: column; gap: 12px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
<h2 id="auth-title" style="margin: 0; font-size: 15px; font-weight: 600;">Login über Authelia</h2>
<label style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: #A0A7B4; cursor: pointer;">Aktiv<input type="checkbox" role="switch" checked style="width: 18px; height: 18px; margin: 0; accent-color: #8B7CF6;"></label>
</div>
<p style="margin: 0; font-size: 13px; color: #A0A7B4; line-height: 1.5;">Vor dem Dienst erscheint das Authelia-Login. Nutzer und Regeln pflegst du in Authelia selbst.</p>
<div style="display: flex; flex-direction: column;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Instanz</span><span style="font-size: 12px; color: #A0A7B4;">aus Einstellungen › Integrationen</span></span>
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">auth.beispiel.de</span>
</div>
<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Erwartete Regel</span><span style="font-size: 12px; color: #A0A7B4;">nur Hinweis – Authelia entscheidet</span></span>
<span style="padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #C9C1FF; background: rgba(139,124,246,.16);">Zwei-Faktor</span>
</div>
</div>
<div style="display: flex; flex-direction: column; gap: 8px; padding-top: 10px; border-top: 1px solid #1E222B;">
<span style="display: flex; flex-direction: column;"><span style="font-weight: 500;">Ohne Login erreichbar</span><span style="font-size: 12px; color: #A0A7B4;">z. B. für API-Clients und Webhooks</span></span>
<div style="display: flex; flex-wrap: wrap; gap: 6px;">
<span style="padding: 5px 10px; border-radius: 7px; background: #0E1014; border: 1px solid #2E3440; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">/api/*</span>
<span style="padding: 5px 10px; border-radius: 7px; background: #0E1014; border: 1px solid #2E3440; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;">/.well-known/*</span>
<button type="button" style="min-height: 30px; padding: 0 10px; border-radius: 7px; border: 1px dashed #3A4150; background: transparent; color: #A0A7B4; font: inherit; font-size: 12px; cursor: pointer;">+ Pfad</button>
</div>
</div>
</section>

</div>
</main>
</div>
