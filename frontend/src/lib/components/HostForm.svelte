<script lang="ts">
  import type { HostInput, NodeInfo } from '../api';

  interface Props {
    value: HostInput;
    nodes: NodeInfo[];
    /** kompakte Darstellung im Bearbeiten-Panel */
    compact?: boolean;
    /** Cloudflare-Token hinterlegt → DNS-01 möglich */
    dnsAvailable?: boolean;
  }

  let { value = $bindable(), nodes, compact = false, dnsAvailable = false }: Props = $props();
  const wildcard = $derived(value.domain.trim().startsWith('*.'));
  // Wildcard geht nur per DNS-01
  $effect(() => {
    if (wildcard && dnsAvailable && value.tls_challenge !== 'dns') value.tls_challenge = 'dns';
  });
  const id = $props.id();
</script>

<div class="form" class:compact>
  <label class="field" for="{id}-domain">
    Domain
    <input
      id="{id}-domain"
      class="input mono"
      type="text"
      inputmode="url"
      autocomplete="off"
      spellcheck="false"
      placeholder="musik.beispiel.de"
      required
      bind:value={value.domain}
    />
  </label>

  <label class="field" for="{id}-challenge">
    Zertifikat von Let's Encrypt prüfen über
    <select id="{id}-challenge" class="input" bind:value={value.tls_challenge}>
      <option value="http" disabled={wildcard}>HTTP-01 – Port 80 muss von außen erreichbar sein</option>
      <option value="dns" disabled={!dnsAvailable}>DNS-01 über Cloudflare – auch Wildcards (*.domain){dnsAvailable ? '' : ' · Token fehlt'}</option>
    </select>
    {#if wildcard && !dnsAvailable}
      <span class="field-error">Wildcard-Domains brauchen DNS-01 – Cloudflare-Token unter Einstellungen › Integrationen eintragen.</span>
    {/if}
  </label>

  {#if !compact}
    <fieldset class="nodes">
      <legend>Auf welchem Node läuft der Dienst?</legend>
      <div class="node-grid">
        {#each nodes as n (n.id)}
          <label class="node" class:on={value.node_id === n.id}>
            <span class="node-head">
              <span class="mono strong">{n.name}</span>
              <input type="radio" name="{id}-node" value={n.id} bind:group={value.node_id} />
            </span>
            <span class="muted small">{n.location}</span>
            <span class="small" class:ok={n.in_sync} class:warn={!n.in_sync}>
              {n.in_sync ? 'synchron' : 'nicht synchron'}
            </span>
          </label>
        {/each}
      </div>
      <span class="muted small">Weitere Nodes kommen mit Phase 4.</span>
    </fieldset>
  {:else}
    <label class="field" for="{id}-node">
      Node
      <select id="{id}-node" class="input" bind:value={value.node_id}>
        {#each nodes as n (n.id)}<option value={n.id}>{n.name}</option>{/each}
      </select>
    </label>
  {/if}

  <div class="target">
    <label class="field" for="{id}-scheme">
      Protokoll
      <select id="{id}-scheme" class="input" bind:value={value.upstream_scheme}>
        <option value="http">http</option>
        <option value="https">https</option>
      </select>
    </label>
    <label class="field" for="{id}-host">
      Ziel-Adresse (vom Node aus)
      <input
        id="{id}-host"
        class="input mono"
        type="text"
        autocomplete="off"
        spellcheck="false"
        placeholder="10.0.1.20"
        required
        bind:value={value.upstream_host}
      />
    </label>
    <label class="field" for="{id}-port">
      Port
      <input
        id="{id}-port"
        class="input mono"
        type="number"
        min="1"
        max="65535"
        required
        bind:value={value.upstream_port}
      />
    </label>
  </div>

  <div class="options">
    <label class="check"><input type="checkbox" bind:checked={value.websockets} />WebSockets erlauben</label>
    <label class="check"><input type="checkbox" bind:checked={value.force_https} />HTTP → HTTPS umleiten</label>
    <label class="check"><input type="checkbox" bind:checked={value.compression} />Kompression (gzip/zstd)</label>
    {#if compact}
      <label class="check"><input type="checkbox" bind:checked={value.enabled} />Aktiv</label>
    {/if}
  </div>
</div>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .form.compact {
    gap: 14px;
  }
  .nodes {
    margin: 0;
    padding: 0;
    border: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  legend {
    padding: 0;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--text-muted);
  }
  .node-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 10px;
  }
  .node {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border-input);
    cursor: pointer;
  }
  .node.on {
    background: rgba(139, 124, 246, 0.1);
    border-color: var(--accent);
  }
  .node-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .node input {
    margin: 0;
    accent-color: var(--accent);
  }
  .strong {
    font-weight: 600;
    font-size: 13px;
  }
  .small {
    font-size: 12px;
  }
  .ok {
    color: var(--ok-text);
    font-weight: 600;
  }
  .warn {
    color: var(--warn-text);
    font-weight: 600;
  }
  .target {
    display: grid;
    grid-template-columns: 110px minmax(0, 1fr) 110px;
    gap: 12px;
  }
  .compact .target {
    grid-template-columns: 90px minmax(0, 1fr) 90px;
  }
  .options {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 20px;
  }
  @media (max-width: 520px) {
    .target,
    .compact .target {
      grid-template-columns: 1fr 1fr;
    }
    .target label:nth-child(2) {
      grid-column: 1 / -1;
      grid-row: 1;
    }
  }
</style>
