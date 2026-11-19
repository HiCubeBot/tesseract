<script lang="ts">
  import Icon from './Icon.svelte';
  import StatusPill from './StatusPill.svelte';

  interface Props {
    nodeName?: string;
    location?: string;
    caddy?: string;
    hosts?: string | number;
    seen?: string;
    status?: 'online' | 'drift' | 'offline';
    href?: string;
  }

  let {
    nodeName = '',
    location = '',
    caddy = '',
    hosts = '',
    seen = '',
    status = 'online',
    href = '#/nodes'
  }: Props = $props();

  const S = {
    online: { tone: 'ok', label: 'online' },
    drift: { tone: 'warn', label: 'lokal geändert' },
    offline: { tone: 'bad', label: 'offline' }
  } as const;
  const s = $derived(S[status]);
</script>

<article class="card {status}">
  <div class="top">
    <div class="who">
      <div class="icon"><Icon name="server" /></div>
      <div class="names">
        <span class="name">{nodeName}</span>
        <span class="loc">{location}</span>
      </div>
    </div>
    <StatusPill tone={s.tone} label={s.label} />
  </div>
  <dl>
    <div><dt>Caddy</dt><dd>{caddy}</dd></div>
    <div><dt>Hosts</dt><dd>{hosts}</dd></div>
    <div><dt>Kontakt</dt><dd class="seen">{seen}</dd></div>
  </dl>
  <a {href} class="link">Node öffnen</a>
</article>

<style>
  .card {
    width: 100%;
    min-height: 168px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px 18px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    color: var(--text);
    font-family: var(--font-sans);
    border: 1px solid var(--border);
  }
  .card.drift { border-color: rgba(229, 164, 67, 0.4); }
  .card.offline { border-color: rgba(240, 113, 103, 0.45); }
  .top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }
  .who {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .icon {
    width: 34px;
    height: 34px;
    border-radius: var(--radius);
    background: var(--surface-raised);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .names {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .name {
    font-family: var(--font-mono);
    font-weight: 500;
    font-size: 15px;
  }
  .loc {
    font-size: 13px;
    color: var(--text-muted);
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }
  dl div {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  dt {
    font-size: 12px;
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    font-size: 14px;
    font-variant-numeric: tabular-nums;
  }
  .offline .seen { color: var(--bad-text); }
  .link {
    font-size: 13px;
    font-weight: 500;
  }
  .icon {
    color: var(--text-soft);
  }
</style>
