<!--
  Nutzer
  Aus dem Design-Canvas „Caddy Control“ übernommen (Users.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import Sidebar from '../lib/components/Sidebar.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      const pill = (fg, bg) => 'display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: ' + fg + '; background: ' + bg + ';';
      const T = {
        ok: pill('#7FD9AC', 'rgba(76,195,138,.12)'),
        warn: pill('#F0BE6E', 'rgba(229,164,67,.14)'),
        bad: pill('#F59A90', 'rgba(240,113,103,.14)'),
        muted: pill('#A0A7B4', '#232833'),
        none: 'display: none;'
      };
      const users = [
        ['Anna', 'AN', 'Familie', '2 Geräte', '1 läuft ab', 'warn', true],
        ['Ben', 'BE', 'Freunde', '2 Geräte', '', 'none'],
        ['Clara', 'CL', 'Familie', '1 Gerät', '', 'none'],
        ['Opa', 'OP', 'Familie', '1 Gerät', '1 läuft ab', 'warn'],
        ['Dana', 'DA', 'Freunde', 'noch kein Gerät', 'Einladung offen', 'muted'],
        ['Erik', 'ER', 'Freunde', '1 Gerät', 'gesperrt', 'bad']
      ].map(([name, initials, group, devices, badge, t, sel]) => ({
        name, initials, group, devices, badge,
        current: sel ? 'page' : 'false',
        badgeStyle: T[t],
        rowStyle: 'display: flex; align-items: center; gap: 12px; min-height: 60px; padding: 8px 16px; text-decoration: none; border-top: 1px solid #232833;' + (sel ? ' background: rgba(139,124,246,.10); box-shadow: inset 3px 0 0 #8B7CF6;' : ''),
        avatarStyle: 'width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; ' + (t === 'bad' ? 'background: #2A2F3A; color: #A0A7B4;' : 'background: rgba(139,124,246,.22); color: #D6D0FF;')
      }));
      const laptop = 'M4 5h16v11H4zM2 19h20';
      const phone = 'M7 3h10v18H7zM11 18h2';
      const devices = [
        { name: 'MacBook Air', os: 'macOS', seen: 'heute 09:12', icon: laptop, fp: '3F:9A:21 … 0B:C1', until: '02.03.2027', status: 'aktiv', t: 'ok' },
        { name: 'iPhone 15', os: 'iOS', seen: 'gestern', icon: phone, fp: 'A4:10:E8 … 77:2E', until: '29.11.2026', status: 'läuft ab', t: 'warn' }
      ].map((d) => ({ ...d, statusStyle: T[d.t], cardStyle: 'display: flex; flex-direction: column; gap: 12px; padding: 14px; border-radius: 10px; background: #0E1014; border: 1px solid ' + (d.t === 'warn' ? '#5A4520' : '#232833') + ';' }));
      const via = pill('#C9C1FF', 'rgba(139,124,246,.16)');
      const direct = pill('#E7E9EE', '#2A2F3A');
      const services = [
        { domain: 'fotos', via: 'Familie', style: via },
        { domain: 'filme', via: 'Familie', style: via },
        { domain: 'kalender', via: 'Familie', style: via },
        { domain: 'dateien', via: 'direkt', style: direct },
        { domain: 'home', via: 'direkt', style: direct }
      ];
      return { users, devices, services };
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

<header style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px;">
<div style="display: flex; flex-direction: column; gap: 4px;">
<h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em;">Nutzer</h1>
<p style="margin: 0; color: #A0A7B4;">Rechte gehören zur Person. Jedes ihrer Geräte hat ein eigenes Zertifikat.</p>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<button type="button" style="min-height: 44px; padding: 0 16px; border-radius: 8px; border: 1px solid #2E3440; background: #161920; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Gruppen verwalten</button>
<a href="#/invite-1" style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 8px; background: #E7E9EE; color: #0E1014; font-weight: 600; text-decoration: none;">Person einladen</a>
</div>
</header>

<div style="display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start;">

<section aria-label="Personen" style="flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; border-radius: 12px; background: #161920; border: 1px solid #232833; overflow: hidden;">
{#each dcv.users as u}
<a href="#" aria-current={u.current} style={u.rowStyle}>
<div style={u.avatarStyle}>{u.initials}</div>
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px;">
<span style="font-weight: 600; color: #E7E9EE;">{u.name}</span>
<span style="font-size: 13px; color: #A0A7B4;">{u.group} · {u.devices}</span>
</div>
<span style={u.badgeStyle}>{u.badge}</span>
</a>
{/each}
</section>

<section aria-labelledby="user-title" style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 18px; padding: 22px 24px; border-radius: 12px; background: #161920; border: 1px solid #232833;">

<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 14px;">
<div style="width: 52px; height: 52px; border-radius: 50%; background: rgba(139,124,246,.22); color: #D6D0FF; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700;">AN</div>
<div style="flex: 1; min-width: 200px; display: flex; flex-direction: column; gap: 3px;">
<div style="display: flex; align-items: center; gap: 10px;">
<h2 id="user-title" style="margin: 0; font-size: 21px; font-weight: 700;">Anna</h2>
<span style="padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #D6D0FF; background: rgba(139,124,246,.16);">Person</span>
</div>
<span style="color: #A0A7B4;">Gruppe Familie · seit 02.03.2026 · darf bis zu 3 Geräte registrieren</span>
</div>
<button type="button" style="min-height: 44px; padding: 0 14px; border-radius: 8px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-weight: 500; cursor: pointer;">Bearbeiten</button>
<button type="button" style="min-height: 44px; padding: 0 14px; border-radius: 8px; border: 1px solid #4A2F33; background: transparent; color: #F59A90; font: inherit; font-weight: 500; cursor: pointer;">Person sperren</button>
</div>

<div style="display: flex; flex-direction: column; gap: 10px;">
<div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;">
<h3 style="margin: 0; font-size: 15px; font-weight: 600;">Geräte <span style="color: #A0A7B4; font-weight: 400;">· 2 von 3</span></h3>
<a href="#/invite-2" style="font-size: 13px; font-weight: 500;">+ Gerät hinzufügen (Link erzeugen)</a>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px;">
{#each dcv.devices as d}
<article style={d.cardStyle}>
<div style="display: flex; align-items: center; gap: 12px;">
<div style="width: 40px; height: 40px; border-radius: 10px; background: #232833; display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: #C9CED8;">
<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d={d.icon}></path></svg>
</div>
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px;">
<span style="font-weight: 600;">{d.name}</span>
<span style="font-size: 12px; color: #A0A7B4;">{d.os} · zuletzt {d.seen}</span>
</div>
<span style={d.statusStyle}>{d.status}</span>
</div>
<div style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; font-size: 12px; color: #A0A7B4;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace;">{d.fp}</span>
<span>gültig bis {d.until}</span>
</div>
<div style="display: flex; gap: 8px;">
<button type="button" style="flex: 1; min-height: 36px; border-radius: 7px; border: 1px solid #2E3440; background: transparent; color: #E7E9EE; font: inherit; font-size: 13px; cursor: pointer;">Verlängern</button>
<button type="button" style="flex: 1; min-height: 36px; border-radius: 7px; border: 1px solid #4A2F33; background: transparent; color: #F59A90; font: inherit; font-size: 13px; cursor: pointer;">Gerät sperren</button>
</div>
</article>
{/each}
<a href="#/invite-2" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; min-height: 150px; border-radius: 10px; border: 1px dashed #3A4150; color: #A0A7B4; text-decoration: none; text-align: center; padding: 12px;">
<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"></path></svg>
<span style="font-weight: 500; color: #E7E9EE;">Drittes Gerät</span>
<span style="font-size: 12px;">Anna bekommt einen Link und registriert es selbst</span>
</a>
</div>
</div>

<div style="display: flex; flex-direction: column; gap: 8px;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
<h3 style="margin: 0; font-size: 15px; font-weight: 600;">Zugriff auf Dienste <span style="color: #A0A7B4; font-weight: 400;">· gilt für alle Geräte der Person</span></h3>
<a href="#/access" style="font-size: 13px; font-weight: 500;">Matrix öffnen</a>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 8px;">
{#each dcv.services as s}
<span style="display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 12px; border-radius: 8px; background: #0E1014; border: 1px solid #232833;">
<span style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px;">{s.domain}</span>
<span style={s.style}>{s.via}</span>
</span>
{/each}
</div>
</div>

</section>

</div>
</main>
</div>
