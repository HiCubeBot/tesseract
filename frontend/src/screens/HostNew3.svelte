<!--
  Host anlegen 3 · Prüfen & übertragen
  Aus dem Design-Canvas „Caddy Control“ übernommen (HostNew3.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const step = 3;
      const steps = ['Domain & Ziel', 'Zugriff', 'Prüfen & übertragen'].map((label, i) => {
        const n = i + 1, on = n === step, done = n < step;
        return {
          n: done ? '✓' : String(n), label, current: on ? 'step' : 'false',
          style: 'display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 14px 0 6px; border-radius: 999px; font-size: 13px; font-weight: 500; ' + (on ? 'background: #232833; color: #E7E9EE;' : 'color: #A0A7B4;'),
          numStyle: 'width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; ' + (on ? 'background: #E7E9EE; color: #0E1014;' : done ? 'background: rgba(76,195,138,.18); color: #7FD9AC;' : 'background: transparent; border: 1px solid #3A4150; color: #A0A7B4;')
        };
      });
      const mono = "font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 14px; font-weight: 500;";
      const txt = 'font-size: 14px; font-weight: 500;';
      const summary = [
        { k: 'Domain', v: 'musik.beispiel.de', style: mono },
        { k: 'Node', v: 'home-nas (Zuhause)', style: txt },
        { k: 'Ziel', v: 'http://10.0.1.20:4533', style: mono },
        { k: 'Optionen', v: 'WebSockets, HTTPS-Umleitung', style: txt },
        { k: 'Zugriff', v: 'Nur freigegebene Geräte (mTLS)', style: txt + ' color: #C9C1FF;' },
        { k: 'Freigegeben für', v: 'Familie + Ben · 4 Personen, 6 Geräte', style: txt },
        { k: 'Server-Zertifikat', v: "Let's Encrypt · HTTP-01", style: txt },
        { k: 'Ohne Zertifikat', v: 'Verbindung ablehnen', style: txt }
      ];
      const checks = [
        { title: 'DNS-Eintrag', detail: 'zeigt auf home-nas' },
        { title: 'Port 80 & 443 von außen', detail: 'erreichbar' },
        { title: 'Ziel vom Node erreichbar', detail: '200 OK · 3 ms' },
        { title: 'Config-Validierung (caddy adapt)', detail: 'gültig' }
      ];
      return { steps, summary, checks };
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
<span style="font-size: 13px; color: #A0A7B4;">Letzter Schritt</span>
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Prüfen &amp; übertragen</h1>
</div>
<ol aria-label="Schritte" style="margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px;">
{#each dcv.steps as st}
<li aria-current={st.current} style={st.style}><span style={st.numStyle}>{st.n}</span>{st.label}</li>
{/each}
</ol>
</header>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<div style="flex: 999 1 480px; min-width: 0; display: flex; flex-direction: column; gap: 18px;">

<section aria-label="Zusammenfassung" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; border-radius: 12px; overflow: hidden; background: #232833; border: 1px solid #232833;">
{#each dcv.summary as s}
<div style="display: flex; flex-direction: column; gap: 4px; padding: 14px 18px; background: #161920;">
<span style="font-size: 12px; color: #A0A7B4;">{s.k}</span>
<span style={s.style}>{s.v}</span>
</div>
{/each}
</section>

<section aria-labelledby="checks-title" style="display: flex; flex-direction: column; gap: 2px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 id="checks-title" style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">Prüfungen</h2>
{#each dcv.checks as c}
<div style="display: flex; align-items: center; gap: 12px; padding: 9px 0; border-top: 1px solid #232833;">
<span style="width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(76,195,138,.18); color: #7FD9AC;"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l9-10"></path></svg></span>
<span style="flex: 1; font-weight: 500;">{c.title}</span>
<span style="font-size: 13px; color: #A0A7B4;">{c.detail}</span>
</div>
{/each}
</section>

</div>

<section aria-labelledby="cfg-title" style="flex: 1 1 400px; min-width: 0; display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
<h2 id="cfg-title" style="margin: 0; font-size: 15px; font-weight: 600;">Wird an home-nas übertragen</h2>
<a href="#" style="font-size: 13px; font-weight: 500;">Als JSON</a>
</div>
<pre style="margin: 0; padding: 14px; border-radius: 8px; background: #0B0D10; border: 1px solid #232833; overflow-x: auto; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.65; color: #C9CED8;">musik.beispiel.de &#123;
  tls &#123;
    client_auth &#123;
      mode require_and_verify
      trust_pool file /etc/caddy/tesseract/ca.pem
      verifier leaf &#123;
        # 6 Geräte von 4 Personen
        file /etc/caddy/tesseract/musik.allowed.pem
      &#125;
    &#125;
  &#125;
  reverse_proxy 10.0.1.20:4533
&#125;</pre>
<span style="font-size: 12px; color: #A0A7B4;">Neues Gerät für Anna? Die Liste wird automatisch ergänzt und neu übertragen.</span>
</section>

</div>

<footer style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: auto;">
<a href="#/host-new-2" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Zurück</a>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<a href="#/hosts" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Als Entwurf speichern</a>
<a href="#/hosts" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Anlegen &amp; übertragen</a>
</div>
</footer>

</main>
</div>
