<!--
  Host · Verlauf & Zurücksetzen
  Aus dem Design-Canvas „Caddy Control“ übernommen (HostHistory.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    base() {
      const L = (t, text) => ({ t, text });
      return [
        { n: 12, title: 'IP 203.0.113.17 gesperrt', when: 'heute 10:31', who: 'admin',
          changes: [{ field: 'IP-Filter · Sperren', before: '1 Eintrag + Liste', after: '+ 203.0.113.17' }],
          code: [L(' ', 'git.beispiel.de {'), L('-', '  @blocked client_ip 198.51.100.0/24'), L('+', '  @blocked client_ip 198.51.100.0/24 203.0.113.17'), L(' ', '  respond @blocked 403'), L(' ', '  …')] },
        { n: 11, title: 'Login über Authelia aktiviert', when: 'heute 09:12', who: 'admin',
          changes: [{ field: 'Authelia', before: 'aus', after: 'an' }, { field: 'Ohne Login erreichbar', before: '–', after: '/api/*, /.well-known/*' }],
          code: [L(' ', 'git.beispiel.de {'), L('+', '  @auth not path /api/* /.well-known/*'), L('+', '  forward_auth @auth 10.0.1.30:9091 {'), L('+', '    uri /api/authz/forward-auth'), L('+', '    copy_headers Remote-User Remote-Groups Remote-Email Remote-Name'), L('+', '  }'), L(' ', '  reverse_proxy 127.0.0.1:3000'), L(' ', '}')] },
        { n: 10, title: 'Auto-Sperre 198.51.100.0/24', when: 'gestern 22:40', who: 'System',
          changes: [{ field: 'IP-Filter · Sperren', before: '–', after: '+ 198.51.100.0/24 (24 h)' }],
          code: [L(' ', 'git.beispiel.de {'), L('+', '  @blocked client_ip 198.51.100.0/24'), L('+', '  respond @blocked 403'), L(' ', '  …')] },
        { n: 9, title: 'WAF blockiert jetzt', when: '12.11.', who: 'admin',
          changes: [{ field: 'Coraza · Modus', before: 'Nur protokollieren', after: 'Blockieren' }],
          code: [L(' ', 'coraza_waf {'), L('-', '  directives `SecRuleEngine DetectionOnly`'), L('+', '  directives `SecRuleEngine On`'), L(' ', '}')] },
        { n: 8, title: 'Ziel-Port geändert', when: '03.11.', who: 'admin',
          changes: [{ field: 'Ziel', before: '127.0.0.1:3001', after: '127.0.0.1:3000' }],
          code: [L('-', '  reverse_proxy 127.0.0.1:3001'), L('+', '  reverse_proxy 127.0.0.1:3000')] },
        { n: 7, title: 'Zurückgesetzt auf Version 5', when: '28.10.', who: 'admin', revert: true,
          changes: [{ field: 'Ziel', before: '10.0.1.40:3000', after: '127.0.0.1:3001' }],
          code: [L('-', '  reverse_proxy 10.0.1.40:3000'), L('+', '  reverse_proxy 127.0.0.1:3001')] },
        { n: 1, title: 'Host angelegt', when: '14.09.', who: 'admin',
          changes: [{ field: 'Host', before: '–', after: 'git.beispiel.de → 127.0.0.1:3001' }],
          code: [L('+', 'git.beispiel.de {'), L('+', '  reverse_proxy 127.0.0.1:3001'), L('+', '}')] }
      ];
    }
    renderVals() {
      const list = (this.state && this.state.list) || this.base();
      const selN = (this.state && this.state.sel) || list[0].n;
      const current = list[0].n;
      const sel = list.find((v) => v.n === selN) || list[0];
      const pill = (fg, bg) => 'padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const versions = list.map((v) => {
        const on = v.n === sel.n;
        return {
          ...v,
          pressed: on ? 'true' : 'false',
          pick: () => this.setState({ list, sel: v.n }),
          badge: v.n === current ? 'läuft' : (v.revert ? 'Revert' : (v.who === 'System' ? 'automatisch' : '')),
          badgeStyle: v.n === current ? pill('#7FD9AC', 'rgba(76,195,138,.12)') : (v.revert ? pill('#F0BE6E', 'rgba(229,164,67,.14)') : (v.who === 'System' ? pill('#A0A7B4', '#232833') : 'display: none;')),
          numStyle: 'width: 40px; flex-shrink: 0; font-family: \'JetBrains Mono\', ui-monospace, monospace; font-size: 12px; font-weight: 500; color: ' + (on ? '#E7E9EE' : '#A0A7B4') + ';',
          rowStyle: 'display: flex; align-items: center; gap: 10px; width: 100%; min-height: 54px; padding: 6px 16px; border: none; border-top: 1px solid #232833; font: inherit; cursor: pointer; ' + (on ? 'background: rgba(139,124,246,.10); box-shadow: inset 3px 0 0 #8B7CF6;' : 'background: transparent;')
        };
      });
      const lineStyle = { '+': 'padding: 0 14px; white-space: pre; color: #7FD9AC; background: rgba(76,195,138,.10);', '-': 'padding: 0 14px; white-space: pre; color: #F59A90; background: rgba(240,113,103,.10);', ' ': 'padding: 0 14px; white-space: pre; color: #C9CED8;' };
      const notice = !!(this.state && this.state.notice);
      return {
        tabs: [
          { id: 'general', label: 'Allgemein', href: '#/hosts' },
          { id: 'access', label: 'Zugriff', href: '#/hosts' },
          { id: 'security', label: 'Sicherheit', href: '#/host-security' },
          { id: 'history', label: 'Verlauf · ' + list.length, href: '#/host-history' }
        ].map((t) => ({ ...t, current: t.id === 'history' ? 'page' : 'false', style: 'display: inline-flex; align-items: center; min-height: 40px; padding: 0 14px; margin-bottom: -1px; text-decoration: none; font-weight: 500; border-bottom: 2px solid ' + (t.id === 'history' ? '#8B7CF6; color: #E7E9EE;' : 'transparent; color: #A0A7B4;') })),
        versions,
        sel: {
          ...sel,
          meta: sel.when + ' · ' + sel.who + ' · an edge-fra übertragen',
          isCurrent: sel.n === current,
          canRevert: sel.n !== current,
          code: sel.code.map((l) => ({ text: (l.t === ' ' ? '  ' : l.t + ' ') + l.text, style: lineStyle[l.t] }))
        },
        notice,
        noticeText: notice ? this.state.notice : '',
        revert: () => {
          const n = current + 1;
          const cur = list[0];
          const entry = {
            n, title: 'Zurückgesetzt auf Version ' + sel.n, when: 'gerade eben', who: 'admin', revert: true,
            changes: sel.changes.map((c) => ({ field: c.field, before: 'Stand v' + cur.n, after: 'wie v' + sel.n })),
            code: sel.code
          };
          this.setState({ list: [entry].concat(list), sel: n, notice: 'Version ' + n + ' erstellt (Stand von v' + sel.n + ') und an edge-fra übertragen. v' + cur.n + ' bleibt im Verlauf.' });
        }
      };
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
<span style="font-size: 13px; color: #A0A7B4;">Jede gespeicherte Änderung wird eine Version. Nichts wird überschrieben.</span>
</div>
<nav aria-label="Host-Bereiche" style="display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #232833;">
{#each dcv.tabs as t}
<a href={t.href} aria-current={t.current} style={t.style}>{t.label}</a>
{/each}
</nav>
</header>

{#if dcv.notice}
<div role="status" style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 10px; background: rgba(76,195,138,.10); border: 1px solid #2F5C46; font-size: 13px;">
<span style="width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; background: rgba(76,195,138,.22); color: #7FD9AC;"><svg aria-hidden="true" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l9-10"></path></svg></span>
<span>{dcv.noticeText}</span>
</div>
{/if}

<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">

<section aria-label="Versionen" style="flex: 1 1 360px; min-width: 0; display: flex; flex-direction: column; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow: hidden;">
{#each dcv.versions as v}
<button type="button" aria-pressed={v.pressed} onclick={v.pick} style={v.rowStyle}>
<span style={v.numStyle}>v{v.n}</span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; text-align: left;">
<span style="font-weight: 500; color: #E7E9EE;">{v.title}</span>
<span style="font-size: 12px; color: #A0A7B4;">{v.when} · {v.who}</span>
</span>
<span style={v.badgeStyle}>{v.badge}</span>
</button>
{/each}
</section>

<section aria-labelledby="diff-title" style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 18px 20px; border-radius: 12px; background: #161920; border: 1px solid #3A3460;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<span style="font-size: 12px; color: #A0A7B4;">{dcv.sel.meta}</span>
<h2 id="diff-title" style="margin: 0; font-size: 18px; font-weight: 600;">Version {dcv.sel.n} · {dcv.sel.title}</h2>
</div>

<div style="border: 1px solid #232833; border-radius: 10px; overflow: hidden;">
<table style="width: 100%; border-collapse: collapse; font-size: 13px;">
<thead>
<tr style="text-align: left; color: #A0A7B4; font-size: 12px; background: #12151B;">
<th scope="col" style="padding: 9px 12px; font-weight: 600;">Einstellung</th>
<th scope="col" style="padding: 9px 12px; font-weight: 600;">vorher</th>
<th scope="col" style="padding: 9px 12px; font-weight: 600;">nachher</th>
</tr>
</thead>
<tbody>
{#each dcv.sel.changes as c}
<tr style="border-top: 1px solid #232833;">
<td style="padding: 9px 12px; font-weight: 500;">{c.field}</td>
<td style="padding: 9px 12px; color: #F59A90;">{c.before}</td>
<td style="padding: 9px 12px; color: #7FD9AC;">{c.after}</td>
</tr>
{/each}
</tbody>
</table>
</div>

<div style="display: flex; flex-direction: column; gap: 6px;">
<span style="font-size: 12px; color: #A0A7B4;">Caddy-Config (Ausschnitt)</span>
<div style="border-radius: 8px; background: #0B0D10; border: 1px solid #232833; padding: 8px 0; overflow-x: auto; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.7;">
{#each dcv.sel.code as l}
<div style={l.style}>{l.text}</div>
{/each}
</div>
</div>

<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 2px;">
{#if dcv.sel.canRevert}
<button type="button" onclick={dcv.revert} style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Auf Version {dcv.sel.n} zurücksetzen</button>
<span style="font-size: 12px; color: #A0A7B4;">Erzeugt eine neue Version und überträgt sie an edge-fra.</span>
{/if}
{#if dcv.sel.isCurrent}
<span style="font-size: 13px; color: #A0A7B4;">Das ist die laufende Version.</span>
{/if}
</div>
</section>

</div>
</main>
</div>
