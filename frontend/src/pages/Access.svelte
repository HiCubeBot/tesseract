<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import { api, type AccessMatrix } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  type Kind = 'group' | 'person';

  let matrix = $state<AccessMatrix | null>(null);
  let cells = $state<Set<string>>(new Set());
  let original = $state<Set<string>>(new Set());
  let error = $state('');
  let saving = $state(false);

  const key = (hostId: number, kind: Kind, id: number) => `${hostId}:${kind}:${id}`;

  async function load() {
    try {
      matrix = await api.get<AccessMatrix>('/access');
      original = new Set(matrix.grants.map((g) => key(g.host_id, g.kind, g.id)));
      cells = new Set(original);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  function toggle(hostId: number, kind: Kind, id: number) {
    const k = key(hostId, kind, id);
    const next = new Set(cells);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    cells = next;
  }

  const dirty = $derived(cells.size !== original.size || [...cells].some((k) => !original.has(k)));

  function viaGroup(hostId: number, groupIds: number[]): boolean {
    return groupIds.some((g) => cells.has(key(hostId, 'group', g)));
  }

  async function save() {
    if (!matrix) return;
    saving = true;
    try {
      const grants = [...cells].map((k) => {
        const [h, kind, id] = k.split(':');
        return { host_id: Number(h), kind, id: Number(id) };
      });
      const r = await api.put<{ changed: string[]; ok: boolean; error: string | null }>('/access', { grants });
      if (r.ok) toasts.show('ok', `Übertragen: ${r.changed.join(', ') || 'keine Änderung'}.`);
      else toasts.show('warn', `Gespeichert, aber nicht übertragen: ${r.error}`, 12000);
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      saving = false;
    }
  }
</script>

<AppShell active="access">
  <PageHeader
    title="Zugriffsmatrix"
    subtitle="Rechte vergibst du an Gruppen oder Personen – sie gelten automatisch für alle Geräte dieser Person."
  />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if matrix && matrix.hosts.length === 0}
    <EmptyState
      icon="hosts"
      title="Noch keine geschützten Hosts"
      text="Stelle einen Host auf „Nur mit Zertifikat“ oder schütze einzelne Pfade – dann erscheint er hier."
      actionLabel="Zu den Hosts"
      actionHref="#/hosts"
    />
  {:else if matrix}
    <div class="legend muted">
      <span><span class="box on"><Icon name="check" size={12} strokeWidth={3} /></span> direkt erlaubt</span>
      <span><span class="box via"><Icon name="check" size={12} strokeWidth={3} /></span> über Gruppe</span>
      <span><span class="box"></span> kein Zugriff</span>
    </div>

    <div class="table-wrap">
      <table class="table matrix">
        <thead>
          <tr>
            <th scope="col">Gruppe / Person</th>
            {#each matrix.hosts as h (h.id)}
              <th scope="col" class="host">
                <span class="mono">{h.domain}</span>
                {#if h.paths.length}<span class="tiny">{h.access === 'mtls' ? 'mit öffentl. Pfaden' : 'nur ' + h.paths.join(', ')}</span>{/if}
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each matrix.groups as g (g.id)}
            <tr>
              <th scope="row"><Icon name="users" size={14} /> Gruppe {g.name} <span class="muted tiny">{g.members.length}</span></th>
              {#each matrix.hosts as h (h.id)}
                {@const on = cells.has(key(h.id, 'group', g.id))}
                <td class="cell">
                  <button
                    type="button"
                    class="box"
                    class:on
                    aria-pressed={on}
                    aria-label={`Gruppe ${g.name} auf ${h.domain} ${on ? 'entziehen' : 'erlauben'}`}
                    onclick={() => toggle(h.id, 'group', g.id)}
                  >
                    {#if on}<Icon name="check" size={12} strokeWidth={3} />{/if}
                  </button>
                </td>
              {/each}
            </tr>
          {/each}
          {#each matrix.persons as p (p.id)}
            <tr class:disabled={p.disabled}>
              <th scope="row"><Icon name="person" size={14} /> {p.name}{#if p.disabled} <span class="muted tiny">gesperrt</span>{/if}</th>
              {#each matrix.hosts as h (h.id)}
                {@const on = cells.has(key(h.id, 'person', p.id))}
                {@const via = !on && viaGroup(h.id, p.group_ids)}
                <td class="cell">
                  <button
                    type="button"
                    class="box"
                    class:on
                    class:via
                    aria-pressed={on}
                    aria-label={`${p.name} auf ${h.domain} ${on ? 'entziehen' : 'direkt erlauben'}${via ? ' (bereits über Gruppe)' : ''}`}
                    onclick={() => toggle(h.id, 'person', p.id)}
                  >
                    {#if on || via}<Icon name="check" size={12} strokeWidth={3} />{/if}
                  </button>
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="row">
      <Button label={saving ? 'Überträgt …' : 'Übertragen'} disabled={!dirty || saving} onClick={save} />
      <Button variant="secondary" label="Verwerfen" disabled={!dirty || saving} onClick={() => (cells = new Set(original))} />
      {#if dirty}<span class="muted small">Ungespeicherte Änderungen</span>{/if}
    </div>
  {/if}
</AppShell>

<style>
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 13px;
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .matrix th[scope='row'] {
    white-space: nowrap;
    font-weight: 500;
    text-align: left;
    padding: 10px 12px 10px 16px;
    border-top: 1px solid var(--border);
    text-transform: none;
    letter-spacing: 0;
    font-size: 14px;
    color: var(--text);
  }
  .host {
    text-transform: none;
    letter-spacing: 0;
    font-size: 12px;
    color: var(--text);
    vertical-align: bottom;
    min-width: 120px;
  }
  .host .tiny {
    display: block;
    color: var(--text-muted);
    font-weight: 400;
  }
  .tiny {
    font-size: 11px;
  }
  .small {
    font-size: 13px;
  }
  .cell {
    text-align: center;
  }
  .box {
    width: 26px;
    height: 26px;
    border-radius: 7px;
    border: 1px solid var(--border-dashed);
    background: transparent;
    color: var(--bg);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    vertical-align: middle;
  }
  .legend .box {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    cursor: default;
  }
  .box.on {
    background: var(--accent);
    border-color: var(--accent);
  }
  .box.via {
    background: var(--accent-soft);
    border-color: transparent;
    color: #c9c1ff;
  }
  tr.disabled th,
  tr.disabled .box {
    opacity: 0.5;
  }
</style>
