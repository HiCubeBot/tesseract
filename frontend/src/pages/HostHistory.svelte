<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import HostHeader from '../lib/components/HostHeader.svelte';
  import {
    api,
    formatDate,
    formatValue,
    FIELD_LABELS,
    type Host,
    type HostSaved,
    type Version,
    type VersionDetail
  } from '../lib/api';
  import { reportApply } from '../lib/nodes';

  let { params = {} }: { params?: Record<string, string> } = $props();
  const hostId = $derived(Number(params.id));

  let host = $state<Host | null>(null);
  let versions = $state<Version[]>([]);
  let selected = $state<number | null>(null);
  let detail = $state<VersionDetail | null>(null);
  let error = $state('');
  let restoring = $state(false);

  async function load() {
    try {
      [host, versions] = await Promise.all([
        api.get<Host>(`/hosts/${hostId}`),
        api.get<Version[]>(`/hosts/${hostId}/versions`)
      ]);
      error = '';
      if (selected === null || !versions.some((v) => v.version === selected)) {
        selected = versions[0]?.version ?? null;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  $effect(() => {
    if (selected === null) return;
    const v = selected;
    api.get<VersionDetail>(`/hosts/${hostId}/versions/${v}`).then((d) => {
      if (selected === v) detail = d;
    });
  });

  async function restore() {
    if (!detail) return;
    restoring = true;
    try {
      const r = await api.post<HostSaved>(`/hosts/${hostId}/versions/${detail.version}/restore`);
      reportApply(r.apply, `Version ${detail.version} von ${r.host.domain}`);
      selected = null;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      restoring = false;
    }
  }

  const summary = (v: Version) =>
    v.changes.length
      ? v.changes.map((c) => FIELD_LABELS[c.field] ?? c.field).join(', ') + ' geändert'
      : v.version === 1
        ? 'Angelegt'
        : 'keine Änderung';
</script>

<AppShell active="hosts">
  <HostHeader {hostId} {host} tab="history" onChange={() => load()} />
  <p class="muted intro">Jede gespeicherte Änderung wird eine Version. Nichts wird überschrieben.</p>

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  <div class="layout">
    <section class="card list" aria-label="Versionen">
      <ol>
        {#each versions as v (v.version)}
          <li>
            <button type="button" class:on={v.version === selected} onclick={() => (selected = v.version)}>
              <span class="row">
                <strong>Version {v.version}</strong>
                {#if v.current}<StatusPill tone="ok" label="läuft" />{/if}
              </span>
              <span class="muted small">{formatDate(v.created_at)} · {v.actor}</span>
              <span class="small">{v.comment || summary(v)}</span>
            </button>
          </li>
        {/each}
      </ol>
    </section>

    {#if detail}
      <section class="card detail" aria-labelledby="v-title">
        <div class="row">
          <h2 id="v-title">Version {detail.version}</h2>
          <span class="spacer"></span>
          {#if detail.current}
            <span class="muted small">Das ist die laufende Version.</span>
          {:else}
            <Button
              variant="secondary"
              icon="refresh"
              label={restoring ? 'Überträgt …' : 'Diese Version wiederherstellen'}
              disabled={restoring}
              onClick={restore}
            />
          {/if}
        </div>
        {#if !detail.current}
          <p class="muted small">Erzeugt eine neue Version mit diesem Stand und überträgt sie an {host?.node.name}.</p>
        {/if}

        {#if detail.changes.length}
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr><th scope="col">Einstellung</th><th scope="col">vorher</th><th scope="col">nachher</th></tr>
              </thead>
              <tbody>
                {#each detail.changes as c (c.field)}
                  <tr>
                    <td>{FIELD_LABELS[c.field] ?? c.field}</td>
                    <td class="mono before">{formatValue(c.before)}</td>
                    <td class="mono after">{formatValue(c.after)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="muted">{detail.version === 1 ? 'Erste Version des Hosts.' : 'Keine Änderungen gegenüber der vorherigen Version.'}</p>
        {/if}

        <div class="routes">
          {#if detail.previous_route}
            <div class="field">
              <span>Caddy-Route vorher</span>
              <pre class="code">{JSON.stringify(detail.previous_route, null, 2)}</pre>
            </div>
          {/if}
          <div class="field">
            <span>Caddy-Route {detail.previous_route ? 'nachher' : ''}</span>
            <pre class="code">{JSON.stringify(detail.route, null, 2)}</pre>
          </div>
        </div>
      </section>
    {/if}
  </div>
</AppShell>

<style>
  .intro {
    margin: 0;
  }
  h2 {
    margin: 0;
    font-size: 17px;
  }
  .layout {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    align-items: flex-start;
  }
  .list {
    flex: 1 1 280px;
    padding: 8px;
  }
  .detail {
    flex: 999 1 520px;
  }
  ol {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  ol button {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    border: none;
    border-radius: var(--radius);
    background: transparent;
    color: var(--text);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  ol button:hover {
    background: var(--surface-hover);
  }
  ol button.on {
    background: var(--surface-raised);
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
  .before {
    color: var(--bad-text);
  }
  .after {
    color: var(--ok-text);
  }
  .routes {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px;
  }
</style>
