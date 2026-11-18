<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import EventItem from '../lib/components/EventItem.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Button from '../lib/components/Button.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import BansCard from '../lib/components/BansCard.svelte';
  import {
    api,
    formatAgo,
    ACTION_LABELS,
    type AuditEntry,
    type Host,
    type CertificateOverview,
    type Invite,
    type NodeInfo
  } from '../lib/api';
  import { formatDay } from '../lib/api';
  import { applyNode } from '../lib/nodes';

  let hosts = $state<Host[]>([]);
  let nodes = $state<NodeInfo[]>([]);
  let events = $state<AuditEntry[]>([]);
  let invites = $state<Invite[]>([]);
  let certs = $state<CertificateOverview | null>(null);
  // Zertifikate separat laden – das Auslesen kann ein paar Sekunden dauern
  api.get<CertificateOverview>('/certificates').then(
    (c) => (certs = c),
    () => (certs = null)
  );
  const expiring = $derived(
    (certs?.certificates ?? []).filter((c) => c.source !== 'lokal' && c.days_left < 30).slice(0, 5)
  );
  let error = $state('');
  let applying = $state<number | null>(null);

  async function load() {
    try {
      [hosts, nodes, events, invites] = await Promise.all([
        api.get<Host[]>('/hosts'),
        api.get<NodeInfo[]>('/nodes'),
        api.get<AuditEntry[]>('/audit?limit=8'),
        api.get<Invite[]>('/invites')
      ]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function apply(node: NodeInfo) {
    applying = node.id;
    try {
      await applyNode(node);
    } finally {
      applying = null;
      await load();
    }
  }

  const live = $derived(hosts.filter((h) => h.enabled && !h.draft));
  const drafts = $derived(hosts.filter((h) => h.draft).length);
  const outOfSync = $derived(nodes.filter((n) => !n.in_sync));
  const pending = $derived(
    invites.flatMap((i) =>
      i.enrollments.filter((e) => e.status === 'pending').map((e) => ({ ...e, person: i.person_name, personId: i.person_id }))
    )
  );

  const tone = (action: string) =>
    action.endsWith('failed') ? 'bad' : action.startsWith('host_') ? 'mtls' : 'neutral';
</script>

<AppShell active="main">
  <PageHeader
    title="Übersicht"
    subtitle={`${nodes.length} Node${nodes.length === 1 ? '' : 's'} · ${hosts.length} Hosts`}
    primaryLabel="Host anlegen"
    primaryHref="#/hosts/new"
  />

  {#if error}<Alert tone="bad" title="Daten konnten nicht geladen werden" text={error} />{/if}

  {#each pending as e (e.id)}
    <Alert
      tone="info"
      title={`${e.person} möchte „${e.device_name}“ registrieren`}
      text="Bestätigungscode war korrekt. Gib das Gerät frei oder lehne ab."
      actionLabel="Ansehen"
      actionHref={`#/users/${e.personId}`}
    />
  {/each}

  {#each outOfSync as node (node.id)}
    <Alert
      tone="warn"
      title={`${node.name} ist nicht auf dem Stand des Controllers`}
      text={node.last_apply_error ?? 'Die Config wurde noch nicht übertragen.'}
    />
  {/each}

  <div class="stats">
    <StatCard label="Aktive Hosts" value={String(live.length)} sub={drafts ? `${drafts} Entwurf/Entwürfe` : 'alle übertragen'} tone="ok" />
    <StatCard
      label="Nodes synchron"
      value={`${nodes.length - outOfSync.length}/${nodes.length}`}
      sub={outOfSync.length ? 'Abweichung – erneut übertragen' : 'alles übertragen'}
      tone={outOfSync.length ? 'warn' : 'ok'}
      subTone={outOfSync.length ? 'warn' : 'muted'}
    />
    <StatCard label="Freigegebene Geräte" value="–" sub="ab Phase 2 (mTLS)" tone="mtls" />
  </div>

  <div class="cols">
    <section class="card" aria-labelledby="nodes-title">
      <h2 id="nodes-title">Nodes</h2>
      {#each nodes as node (node.id)}
        <div class="node">
          <div class="node-head">
            <span class="mono strong">{node.name}</span>
            <StatusPill tone={node.in_sync ? 'ok' : 'warn'} label={node.in_sync ? 'synchron' : 'nicht synchron'} />
          </div>
          <span class="muted small">
            {node.location} · {node.hosts} Hosts · zuletzt übertragen {formatAgo(node.last_applied_at)}
          </span>
          <div>
            <Button
              variant="secondary"
              size="sm"
              icon="refresh"
              label={applying === node.id ? 'Überträgt …' : 'Config erneut übertragen'}
              disabled={applying !== null}
              onClick={() => apply(node)}
            />
          </div>
        </div>
      {/each}
    </section>

    <section class="card" aria-labelledby="certs-title">
      <div class="row">
        <h2 id="certs-title" class="card-title">Bald ablaufende Zertifikate</h2>
        <span class="spacer"></span>
        <a href="#/certificates" class="small">Alle Zertifikate</a>
      </div>
      {#if !certs}
        <p class="muted small">Prüfe …</p>
      {:else if expiring.length}
        <ul class="plain">
          {#each expiring as c (c.fingerprint)}
            <li>
              <span class="mono">{c.names[0]}</span>
              <span class="spacer"></span>
              <StatusPill tone={c.status === 'ok' ? 'warn' : 'bad'} label={`${c.days_left} Tage · ${formatDay(c.not_after)}`} />
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted small">Keine öffentlichen Zertifikate, die in den nächsten 30 Tagen ablaufen.</p>
      {/if}
    </section>

    <BansCard compact />

    <section class="card" aria-labelledby="events-title">
      <div class="row">
        <h2 id="events-title" class="card-title">Letzte Ereignisse</h2>
        <span class="spacer"></span>
        <a href="#/audit" class="small">Audit-Log</a>
      </div>
      {#each events as e (e.id)}
        <EventItem
          time={formatAgo(e.created_at)}
          title={`${ACTION_LABELS[e.action] ?? e.action}${e.target ? ' · ' + e.target : ''}`}
          detail={e.actor + (e.ip ? ' · ' + e.ip : '')}
          tone={tone(e.action)}
        />
      {:else}
        <p class="muted">Noch keine Ereignisse.</p>
      {/each}
    </section>
  </div>
</AppShell>

<style>
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
    align-items: start;
  }
  .node {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }
  .node-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .strong {
    font-weight: 600;
  }
  .small {
    font-size: 13px;
  }
  .plain {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .plain li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-top: 1px solid var(--border);
  }
</style>
