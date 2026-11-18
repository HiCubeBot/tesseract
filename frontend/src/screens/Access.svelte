<!--
  Zugriffsmatrix
  Aus dem Design-Canvas „Caddy Control“ übernommen (Access.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    init() {
      return {
        g: { familie: ['fotos', 'filme', 'kalender'], freunde: ['filme', 'rezepte'] },
        d: { anna: ['dateien', 'home'], ben: ['fotos'], clara: ['rezepte'], opa: ['home'], dana: [], erik: ['filme'] }
      };
    }
    renderVals() {
      const base = this.state && this.state.base ? this.state.base : this.init();
      const cur = this.state && this.state.cur ? this.state.cur : this.init();
      const svcs = [
        { id: 'fotos', node: 'home-nas' }, { id: 'filme', node: 'home-nas' }, { id: 'rezepte', node: 'home-nas' },
        { id: 'kalender', node: 'edge-fra' }, { id: 'dateien', node: 'home-nas' }, { id: 'home', node: 'pi-eltern' }
      ];
      const groups = [{ id: 'familie', name: 'Familie' }, { id: 'freunde', name: 'Freunde' }];
      const users = [
        { id: 'anna', name: 'Anna', g: 'familie' }, { id: 'ben', name: 'Ben', g: 'freunde' },
        { id: 'clara', name: 'Clara', g: 'familie' }, { id: 'opa', name: 'Opa', g: 'familie' },
        { id: 'dana', name: 'Dana', g: 'freunde', note: 'noch kein Zertifikat' }, { id: 'erik', name: 'Erik', g: 'freunde', blocked: true }
      ];
      const gName = { familie: 'Familie', freunde: 'Freunde' };
      const devs = { anna: 2, ben: 2, clara: 1, opa: 1, dana: 0, erik: 1 };
      const devLabel = (k) => devs[k] ? devs[k] + (devs[k] === 1 ? ' Gerät' : ' Geräte') : 'noch kein Gerät';
      const has = (obj, k, s) => (obj[k] || []).indexOf(s) >= 0;
      const flip = (kind, key, s) => {
        const next = { g: { ...cur.g }, d: { ...cur.d } };
        const list = (next[kind][key] || []).slice();
        const i = list.indexOf(s);
        if (i >= 0) list.splice(i, 1); else list.push(s);
        next[kind] = { ...next[kind], [key]: list };
        this.setState({ base, cur: next });
      };
      const btn = 'min-width: 92px; min-height: 36px; padding: 0 10px; border-radius: 8px; font: inherit; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer;';
      const S = {
        on: btn + ' background: rgba(139,124,246,.30); border: 1px solid #8B7CF6; color: #EEEBFF;',
        via: btn + ' background: transparent; border: 1px dashed #8B7CF6; color: #C9C1FF;',
        off: btn + ' background: transparent; border: 1px solid #2E3440; color: #A0A7B4;',
        dis: btn + ' background: transparent; border: 1px solid #232833; color: #6E7582; cursor: not-allowed;'
      };
      const cols = svcs.map((s) => {
        const allowed = users.filter((u) => !u.blocked && (has(cur.d, u.id, s.id) || has(cur.g, u.g, s.id)));
        const m = allowed.reduce((a, u) => a + devs[u.id], 0);
        return { label: s.id, node: s.node, count: allowed.length + ' Pers. · ' + m + ' Ger.' };
      });
      const avatar = (bg, fg) => 'width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; background: ' + bg + '; color: ' + fg + ';';
      const rows = [];
      groups.forEach((g, gi) => {
        const members = users.filter((u) => u.g === g.id).length;
        rows.push({
          name: 'Gruppe ' + g.name, initials: g.name.slice(0, 2).toUpperCase(), sub: members + ' Mitglieder',
          subStyle: 'font-size: 12px; color: #A0A7B4;',
          avatarStyle: avatar('#2A2F3A', '#E7E9EE').replace('50%', '8px'),
          trStyle: 'border-top: 1px solid #232833; background: #12151B;' + (gi === groups.length - 1 ? ' border-bottom: 2px solid #2A2F3A;' : ''),
          cells: svcs.map((s) => {
            const on = has(cur.g, g.id, s.id);
            return { check: on, label: on ? 'Gruppe' : '—', pressed: on ? 'true' : 'false', disabled: false,
              aria: 'Gruppe ' + g.name + ' für ' + s.id + (on ? ' entziehen' : ' freigeben'),
              style: on ? S.on : S.off, toggle: () => flip('g', g.id, s.id) };
          })
        });
      });
      users.forEach((u) => {
        rows.push({
          name: u.name, initials: u.name.slice(0, 2).toUpperCase(),
          sub: u.blocked ? 'gesperrt · ' + devLabel(u.id) : gName[u.g] + ' · ' + devLabel(u.id),
          subStyle: 'font-size: 12px; color: ' + (u.blocked ? '#F59A90' : '#A0A7B4') + ';',
          avatarStyle: u.blocked ? avatar('#2A2F3A', '#A0A7B4') : avatar('rgba(139,124,246,.22)', '#D6D0FF'),
          trStyle: 'border-top: 1px solid #232833;' + (u.blocked ? ' opacity: 0.6;' : ''),
          cells: svcs.map((s) => {
            const direct = has(cur.d, u.id, s.id);
            const via = has(cur.g, u.g, s.id);
            if (u.blocked) return { check: false, label: 'gesperrt', pressed: 'false', disabled: true, aria: u.name + ' ist gesperrt', style: S.dis, toggle: null };
            return {
              check: direct, label: direct ? 'Direkt' : (via ? gName[u.g] : '—'),
              pressed: direct ? 'true' : 'false', disabled: false,
              aria: u.name + ' für ' + s.id + (direct ? ' direkt entziehen' : ' direkt freigeben'),
              style: direct ? S.on : (via ? S.via : S.off), toggle: () => flip('d', u.id, s.id)
            };
          })
        });
      });
      let changes = 0; const changedSvcs = {};
      ['g', 'd'].forEach((k) => {
        Object.keys(base[k]).forEach((key) => {
          svcs.forEach((s) => { if (has(base[k], key, s.id) !== has(cur[k], key, s.id)) { changes++; changedSvcs[s.id] = true; } });
        });
      });
      const nodes = Array.from(new Set(svcs.filter((s) => changedSvcs[s.id]).map((s) => s.node)));
      const dirty = changes > 0;
      const applied = this.state && this.state.applied;
      return {
        cols, rows, dirty,
        barTitle: dirty ? (changes === 1 ? '1 ungespeicherte Änderung' : changes + ' ungespeicherte Änderungen') : (applied ? 'Änderungen übertragen' : 'Alles übertragen'),
        barDetail: dirty ? 'Wird übertragen an: ' + nodes.join(', ') + ' – die erlaubten Zertifikatslisten werden neu erzeugt.' : 'Alle Nodes haben den aktuellen Stand der Zugriffsrechte.',
        barStyle: 'display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 20px; border-radius: 12px; ' + (dirty ? 'background: rgba(139,124,246,.10); border: 1px solid #8B7CF6;' : 'background: #161920; border: 1px solid #232833;'),
        reset: () => this.setState({ base, cur: base, applied: false }),
        apply: () => this.setState({ base: cur, cur, applied: true })
      };
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<div style="min-height: 100vh; display: flex; flex-wrap: wrap; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px;">
<div style="flex: 1 1 240px; background: #12151B; border-right: 1px solid #232833;">
<Sidebar active="access" />
</div>
<main style="flex: 999 1 560px; min-width: 0; box-sizing: border-box; padding: 24px 32px; display: flex; flex-direction: column; gap: 18px;">

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 6px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Zugriff</h1>
<p style="margin: 0; color: #A0A7B4;">Rechte vergibst du an Gruppen oder Personen – sie gelten automatisch für alle Geräte dieser Person.</p>
</div>
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 16px; font-size: 13px; color: #A0A7B4;">
<span style="display: inline-flex; align-items: center; gap: 8px;"><span style="width: 18px; height: 18px; border-radius: 5px; background: rgba(139,124,246,.30); border: 1px solid #8B7CF6;"></span>direkt erlaubt</span>
<span style="display: inline-flex; align-items: center; gap: 8px;"><span style="width: 18px; height: 18px; border-radius: 5px; border: 1px dashed #8B7CF6;"></span>über Gruppe</span>
<span style="display: inline-flex; align-items: center; gap: 8px;"><span style="width: 18px; height: 18px; border-radius: 5px; border: 1px solid #2E3440;"></span>kein Zugriff</span>
</div>
</header>

<section aria-label="Zugriffsmatrix" style="border-radius: 12px; background: #161920; border: 1px solid #232833; overflow-x: auto;">
<table style="width: 100%; min-width: 860px; border-collapse: collapse;">
<thead>
<tr>
<th scope="col" style="padding: 16px; text-align: left; font-size: 12px; font-weight: 600; color: #A0A7B4; text-transform: uppercase; letter-spacing: 0.05em; min-width: 180px;">Gruppe / Person</th>
{#each dcv.cols as col}
<th scope="col" style="padding: 16px 8px; text-align: center; font-weight: 500;">
<div style="display: flex; flex-direction: column; align-items: center; gap: 2px;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px; color: #E7E9EE;">{col.label}</span>
<span style="font-size: 12px; color: #A0A7B4;">{col.node} · {col.count}</span>
</div>
</th>
{/each}
</tr>
</thead>
<tbody>
{#each dcv.rows as row}
<tr style={row.trStyle}>
<th scope="row" style="padding: 7px 16px; text-align: left; font-weight: 400;">
<div style="display: flex; align-items: center; gap: 10px;">
<span style={row.avatarStyle}>{row.initials}</span>
<div style="display: flex; flex-direction: column; gap: 1px;">
<span style="font-weight: 600; color: #E7E9EE;">{row.name}</span>
<span style={row.subStyle}>{row.sub}</span>
</div>
</div>
</th>
{#each row.cells as cell}
<td style="padding: 8px; text-align: center;">
<button type="button" aria-pressed={cell.pressed} aria-label={cell.aria} disabled={cell.disabled} onclick={cell.toggle} style={cell.style}>
{#if cell.check}
<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l9-10"></path></svg>
{/if}
<span>{cell.label}</span>
</button>
</td>
{/each}
</tr>
{/each}
</tbody>
</table>
</section>

<div style={dcv.barStyle}>
<div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
<span style="font-weight: 600;">{dcv.barTitle}</span>
<span style="font-size: 13px; color: #A0A7B4;">{dcv.barDetail}</span>
</div>
{#if dcv.dirty}
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<button type="button" onclick={dcv.reset} style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Verwerfen</button>
<button type="button" onclick={dcv.apply} style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: none; background: #E7E9EE; color: #0E1014; font: inherit; font-weight: 600; cursor: pointer;">Übertragen</button>
</div>
{/if}
</div>

</main>
</div>
