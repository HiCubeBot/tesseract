<!--
  Einladung 2 · Admin: Link teilen
  Aus dem Design-Canvas „Caddy Control“ übernommen (Invite2.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const step = 2;
      const steps = ['Person anlegen', 'Link teilen'].map((label, i) => {
        const n = i + 1, on = n === step, done = n < step;
        return {
          n: done ? '✓' : String(n), label, current: on ? 'step' : 'false',
          style: 'display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 14px 0 6px; border-radius: 999px; font-size: 13px; font-weight: 500; ' + (on ? 'background: #232833; color: #E7E9EE;' : 'color: #A0A7B4;'),
          numStyle: 'width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; ' + (on ? 'background: #E7E9EE; color: #0E1014;' : done ? 'background: rgba(76,195,138,.18); color: #7FD9AC;' : 'background: transparent; border: 1px solid #3A4150; color: #A0A7B4;')
        };
      });
      const c = { done: '#4CC38A', now: '#E5A443', todo: '#3A4150' };
      const timeline = [
        { title: 'Einladung erstellt', detail: 'heute 10:05', s: 'done' },
        { title: 'Link geöffnet', detail: 'heute 10:20', s: 'done' },
        { title: 'Gerät registriert – wartet auf dich', detail: 'heute 10:24', s: 'now' },
        { title: 'Zertifikat installiert', detail: 'noch offen', s: 'todo' }
      ].map((t) => ({
        ...t,
        dotStyle: 'width: 12px; height: 12px; margin-top: 4px; border-radius: 50%; flex-shrink: 0; ' + (t.s === 'todo' ? 'border: 2px solid ' + c.todo + ';' : 'background: ' + c[t.s] + ';'),
        titleStyle: 'font-weight: 500; color: ' + (t.s === 'todo' ? '#A0A7B4' : '#E7E9EE') + ';'
      }));
      return { steps, timeline };
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
<span style="font-size: 13px; color: #A0A7B4;">Dana · Freunde · bis zu 2 Geräte</span>
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Einladung ist bereit</h1>
</div>
<ol aria-label="Schritte" style="margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px;">
{#each dcv.steps as st}
<li aria-current={st.current} style={st.style}><span style={st.numStyle}>{st.n}</span>{st.label}</li>
{/each}
</ol>
</header>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<section aria-label="Link teilen" style="flex: 999 1 540px; min-width: 0; display: flex; flex-wrap: wrap; gap: 22px; padding: 22px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<div style="flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 8px;">
<div role="img" aria-label="QR-Code für den Einladungslink" style="width: 188px; height: 188px; box-sizing: border-box; padding: 14px; border-radius: 12px; background: #F4F5F7;">
<svg aria-hidden="true" width="160" height="160" viewBox="0 0 21 21" shape-rendering="crispEdges"><path fill="#0E1014" d="M0 0h7v7H0zM14 0h7v7h-7zM0 14h7v7H0z"></path><path fill="#F4F5F7" d="M1 1h5v5H1zM15 1h5v5h-5zM1 15h5v5H1z"></path><path fill="#0E1014" d="M2 2h3v3H2zM16 2h3v3h-3zM2 16h3v3H2zM8 0h1v2H8zM10 1h2v1h-2zM9 3h2v2H9zM12 4h1v3h-1zM8 6h2v1H8zM8 8h3v1H8zM0 8h2v1H0zM3 9h3v1H3zM12 8h2v2h-2zM15 8h1v3h-1zM17 9h3v1h-3zM9 10h1v3H9zM11 11h3v1h-3zM1 11h2v2H1zM5 11h2v1H5zM19 11h2v2h-2zM16 12h2v1h-2zM8 14h2v1H8zM11 13h1v3h-1zM13 14h3v1h-3zM17 14h1v2h-1zM19 15h2v1h-2zM9 16h1v2H9zM12 17h3v1h-3zM16 17h1v3h-1zM18 18h3v1h-3zM8 19h3v2H8zM13 19h2v2h-2zM19 20h2v1h-2z"></path></svg>
</div>
<span style="font-size: 12px; color: #A0A7B4;">Mit dem Handy scannen</span>
</div>
<div style="flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; gap: 16px;">
<label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #A0A7B4;">Einladungslink · gültig bis 24.11.2026
<span style="display: flex; gap: 8px;">
<input type="text" readonly value="https://tesseract.beispiel.de/e/7KQ2-XM9P" style="flex: 1; min-width: 0; min-height: 44px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #2E3440; color: #E7E9EE; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Kopieren</button>
</span>
</label>
<div style="display: flex; flex-direction: column; gap: 6px; padding: 14px 16px; border-radius: 10px; background: rgba(139,124,246,.08); border: 1px solid #3A3460;">
<span style="font-size: 13px; color: #C9C1FF; font-weight: 600;">Bestätigungscode – separat mitteilen</span>
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 28px; font-weight: 500; letter-spacing: 0.12em;">481 207</span>
<span style="font-size: 13px; color: #A0A7B4; line-height: 1.45;">Am besten mündlich oder per Anruf. Wer nur den Link abfängt, kann damit kein Gerät registrieren.</span>
</div>
<span style="font-size: 13px; color: #A0A7B4;">Die öffentliche Einladungsseite ist der einzige Teil von Tesseract, der ohne Zertifikat erreichbar ist.</span>
</div>
</section>

<aside aria-label="Status der Einladung" style="flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #161920; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Status</h2>
<ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column;">
{#each dcv.timeline as t}
<li style="display: flex; gap: 12px; padding: 8px 0;">
<span style={t.dotStyle}></span>
<span style="flex: 1; display: flex; flex-direction: column; gap: 1px;">
<span style={t.titleStyle}>{t.title}</span>
<span style="font-size: 12px; color: #A0A7B4;">{t.detail}</span>
</span>
</li>
{/each}
</ol>
<div style="display: flex; flex-direction: column; gap: 12px; padding: 14px; border-radius: 10px; background: #0E1014; border: 1px solid #5A4520;">
<div style="display: flex; align-items: center; gap: 12px;">
<span style="width: 36px; height: 36px; border-radius: 9px; background: #232833; display: inline-flex; align-items: center; justify-content: center; color: #C9CED8;"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h10v18H7zM11 18h2"></path></svg></span>
<span style="flex: 1; display: flex; flex-direction: column;">
<span style="font-weight: 600;">„Danas iPhone“</span>
<span style="font-size: 12px; color: #A0A7B4;">iOS 18 · Code korrekt · 10:24</span>
</span>
<span style="padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #F0BE6E; background: rgba(229,164,67,.14);">wartet</span>
</div>
<div style="display: flex; gap: 8px;">
<button type="button" style="flex: 1; min-height: 40px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Gerät freigeben</button>
<button type="button" style="min-height: 40px; padding: 0 14px; border-radius: 8px; border: 1px solid #4A2F33; background: transparent; color: #F59A90; font: inherit; font-weight: 500; cursor: pointer;">Ablehnen</button>
</div>
</div>
</aside>

</div>

<footer style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: auto;">
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #4A2F33; background: transparent; color: #F59A90; font: inherit; font-weight: 500; cursor: pointer;">Einladung widerrufen</button>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<a href="#/invite-3" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; color: #E7E9EE; font-weight: 500; text-decoration: none;">Ansicht für Dana</a>
<a href="#/users" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Fertig</a>
</div>
</footer>

</main>
</div>
