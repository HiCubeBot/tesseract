<script lang="ts">
  import Icon from './Icon.svelte';
  import type { Check } from '../api';

  interface Props {
    checks: Check[];
    busy?: boolean;
  }

  let { checks, busy = false }: Props = $props();

  const icon = { ok: 'check', warn: 'warn', bad: 'close', info: 'info' } as const;
</script>

<ul class="checks" aria-busy={busy}>
  {#each checks as c (c.key)}
    <li>
      <span class="icon {c.status}"><Icon name={icon[c.status]} size={12} strokeWidth={3} /></span>
      <div class="body">
        <span class="title">{c.title}</span>
        <span class="detail">{c.detail}</span>
      </div>
    </li>
  {:else}
    <li class="empty">{busy ? 'Prüfe …' : 'Domain und Ziel eingeben – die Prüfungen laufen automatisch.'}</li>
  {/each}
</ul>

<style>
  .checks {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
  }
  li {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-top: 1px solid var(--border);
  }
  .empty {
    color: var(--text-muted);
    font-size: 13px;
  }
  .icon {
    width: 22px;
    height: 22px;
    flex-shrink: 0;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .ok {
    background: rgba(76, 195, 138, 0.18);
    color: var(--ok-text);
  }
  .warn {
    background: var(--warn-soft);
    color: var(--warn-text);
  }
  .bad {
    background: var(--bad-soft);
    color: var(--bad-text);
  }
  .info {
    background: var(--surface-raised);
    color: var(--text-muted);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .title {
    font-weight: 500;
  }
  .detail {
    font-size: 13px;
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }
</style>
