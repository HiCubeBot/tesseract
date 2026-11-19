<script lang="ts">
  import Button from './Button.svelte';
  import { api, formatAgo, formatDate, type Ban } from '../api';
  import { toasts } from '../toast.svelte';

  interface Props {
    /** kompakte Liste ohne Formular (z. B. in der Übersicht) */
    compact?: boolean;
  }

  let { compact = false }: Props = $props();

  let bans = $state<Ban[]>([]);
  let ip = $state('');
  // 0 = dauerhaft (bis zum Entsperren von Hand)
  let hours = $state(24);
  let reason = $state('');
  let busy = $state(false);

  async function load() {
    try {
      bans = await api.get<Ban[]>('/bans');
    } catch {
      bans = [];
    }
  }
  load();

  async function lift(b: Ban) {
    try {
      await api.del(`/bans/${b.id}`);
      toasts.show('ok', `${b.ip} entsperrt.`);
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }

  async function add(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    try {
      await api.post('/bans', { ip, hours: Number(hours) || null, reason });
      toasts.show('ok', `${ip} gesperrt.`);
      ip = '';
      reason = '';
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="bans-title">
  <div class="row">
    <h2 id="bans-title" class="card-title">Gesperrte IPs</h2>
    <span class="muted small">{bans.length} aktiv</span>
  </div>
  {#if bans.length}
    <ul>
      {#each bans as b (b.id)}
        <li>
          <span class="stack">
            <span class="mono strong">{b.ip}</span>
            <span class="muted small">
              {b.reason}{b.host ? ` · ${b.host}` : ''} · {b.created_by === 'system' ? 'automatisch' : b.created_by}
              {formatAgo(b.created_at)} · {b.expires_at ? `bis ${formatDate(b.expires_at)}` : 'dauerhaft'}
            </span>
          </span>
          <span class="spacer"></span>
          <Button variant="ghost" size="sm" label="Entsperren" onClick={() => lift(b)} />
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted small">Keine IP gesperrt.</p>
  {/if}

  {#if !compact}
    <form class="row" onsubmit={add}>
      <input class="input mono ip" placeholder="IP oder Netz" required bind:value={ip} aria-label="IP oder Netz sperren" />
      <select class="input hours" bind:value={hours} aria-label="Dauer">
        <option value={1}>1 Stunde</option>
        <option value={24}>24 Stunden</option>
        <option value={168}>7 Tage</option>
        <option value={720}>30 Tage</option>
        <option value={2160}>90 Tage</option>
        <option value={8760}>1 Jahr</option>
        <option value={0}>Für immer</option>
      </select>
      <input class="input grow" placeholder="Grund (optional)" maxlength="255" bind:value={reason} aria-label="Grund" />
      <Button type="submit" variant="secondary" label={busy ? 'Sperrt …' : 'Sperren'} disabled={busy} />
    </form>
  {/if}
</section>

<style>
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    padding: 10px 0;
    border-top: 1px solid var(--border);
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .strong {
    font-weight: 600;
  }
  .small {
    font-size: 12px;
    margin: 0;
  }
  .ip {
    flex: 1 1 170px;
  }
  .hours {
    width: auto;
  }
  .grow {
    flex: 2 1 200px;
  }
</style>
