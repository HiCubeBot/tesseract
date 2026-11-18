<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import { api, formatDate, ACTION_LABELS, type AuditEntry } from '../lib/api';

  const PAGE = 100;

  let entries = $state<AuditEntry[]>([]);
  let query = $state('');
  let more = $state(false);
  let error = $state('');
  let open = $state<number | null>(null);

  async function load(append = false) {
    const params = new URLSearchParams({ limit: String(PAGE) });
    if (query.trim()) params.set('q', query.trim());
    if (append && entries.length) params.set('before_id', String(entries[entries.length - 1].id));
    try {
      const page = await api.get<AuditEntry[]>(`/audit?${params}`);
      entries = append ? [...entries, ...page] : page;
      more = page.length === PAGE;
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    void query;
    clearTimeout(timer);
    timer = setTimeout(() => load(), 250);
  });

  const detailText = (e: AuditEntry) => (Object.keys(e.details).length ? JSON.stringify(e.details, null, 2) : '');
</script>

<AppShell active="audit">
  <PageHeader title="Audit-Log" subtitle="Jede Änderung und jede Anmeldung – wer, wann, was." />

  <label class="search">
    <Icon name="search" size={16} strokeWidth={2} />
    <span class="visually-hidden">Log durchsuchen</span>
    <input type="search" placeholder="Wer, Aktion oder Ziel …" bind:value={query} />
  </label>

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th scope="col">Zeit</th>
          <th scope="col">Wer</th>
          <th scope="col">Aktion</th>
          <th scope="col">Betrifft</th>
          <th scope="col">Von</th>
        </tr>
      </thead>
      <tbody>
        {#each entries as e (e.id)}
          {@const details = detailText(e)}
          <tr>
            <td class="nowrap muted">{formatDate(e.created_at)}</td>
            <td>{e.actor}</td>
            <td>
              {#if details}
                <button type="button" class="link" aria-expanded={open === e.id} onclick={() => (open = open === e.id ? null : e.id)}>
                  {ACTION_LABELS[e.action] ?? e.action}
                </button>
              {:else}
                {ACTION_LABELS[e.action] ?? e.action}
              {/if}
            </td>
            <td class="mono small">{e.target || '–'}</td>
            <td class="mono small muted">{e.ip ?? '–'}</td>
          </tr>
          {#if open === e.id && details}
            <tr class="details"><td colspan="5"><pre class="code">{details}</pre></td></tr>
          {/if}
        {:else}
          <tr><td colspan="5" class="muted">Keine Einträge.</td></tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if more}<div><Button variant="secondary" label="Ältere laden" onClick={() => load(true)} /></div>{/if}

  <p class="muted small">Unveränderliche, verkettete Einträge und CSV-Export folgen mit Phase 5.</p>
</AppShell>

<style>
  .search {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 12px;
    max-width: 480px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border-input);
    color: var(--text-muted);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text);
    font: inherit;
  }
  .nowrap {
    white-space: nowrap;
  }
  .small {
    font-size: 13px;
  }
  .link {
    padding: 0;
    border: none;
    background: none;
    color: var(--accent-text);
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .details td {
    border-top: none;
    padding-top: 0;
  }
  p.small {
    margin: 0;
  }
</style>
