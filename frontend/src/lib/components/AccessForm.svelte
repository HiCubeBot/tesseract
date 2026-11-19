<script lang="ts">
  import Icon from './Icon.svelte';
  import Alert from './Alert.svelte';
  import type { HostInput, Group, Person } from '../api';

  interface Props {
    value: HostInput;
    groups: Group[];
    persons: Person[];
    caConfigured: boolean;
    compact?: boolean;
    /** interne Netze unter Einstellungen festgelegt */
    internalAvailable?: boolean;
  }

  let {
    value = $bindable(),
    groups,
    persons,
    caConfigured,
    compact = false,
    internalAvailable = false
  }: Props = $props();
  const id = $props.id();

  let newPath = $state('');

  // Wer bekommt am Ende Zugriff? (Personen direkt oder über Gruppen, nicht gesperrt)
  const reach = $derived.by(() => {
    const groupSet = new Set(value.grant_group_ids);
    const people = persons.filter(
      (p) => !p.disabled && (value.grant_person_ids.includes(p.id) || p.groups.some((g) => groupSet.has(g.id)))
    );
    return { persons: people.length, devices: people.reduce((n, p) => n + p.active_devices, 0) };
  });

  const usesCert = $derived(value.access === 'mtls' || value.paths.length > 0);

  function addPath() {
    let p = newPath.trim();
    if (!p) return;
    if (!p.startsWith('/')) p = '/' + p;
    if (!value.paths.includes(p)) value.paths = [...value.paths, p];
    newPath = '';
  }

  function onPathKey(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addPath();
    }
  }
</script>

<div class="access" class:compact>
  <div class="modes" role="radiogroup" aria-label="Zugriff">
    <label class="mode" class:on={value.access === 'public'}>
      <span class="mode-head">
        <Icon name="globe" size={18} />
        <strong>Öffentlich</strong>
        <input type="radio" name="{id}-access" value="public" bind:group={value.access} />
      </span>
      {#if !compact}<span class="muted">Jeder mit der Adresse. Einzelne Pfade lassen sich trotzdem schützen.</span>{/if}
    </label>
    <label class="mode" class:on={value.access === 'mtls'} class:disabled={!caConfigured}>
      <span class="mode-head">
        <Icon name="lock" size={18} />
        <strong>Nur mit Zertifikat</strong>
        <input type="radio" name="{id}-access" value="mtls" disabled={!caConfigured} bind:group={value.access} />
      </span>
      {#if !compact}<span class="muted">Nur freigegebene Geräte (mTLS). Kein VPN nötig.</span>{/if}
    </label>
  </div>

  <label class="internal" class:on={value.internal} class:disabled={!internalAvailable && !value.internal}>
    <input type="checkbox" bind:checked={value.internal} disabled={!internalAvailable && !value.internal} />
    <span class="stack">
      <strong>Nur aus internen Netzen</strong>
      <span class="muted small">
        {#if internalAvailable}
          Wie hinter einem VPN: nur aus LAN/VPN erreichbar, alle anderen sehen nichts (Verbindung wird abgebrochen).
          Kombinierbar mit „Nur mit Zertifikat“ als zweite Hürde. Zertifikat per DNS-01 oder interner Name (.lan).
        {:else}
          Erst unter <a href="#/settings-integrations">Einstellungen › Integrationen</a> die internen Netze festlegen.
        {/if}
      </span>
    </span>
  </label>

  {#if !caConfigured}
    <Alert tone="info" title="Erst die Zertifizierungsstelle einrichten" text="Ohne CA gibt es keine Gerätezertifikate." actionLabel="CA einrichten" actionHref="#/settings-ca" />
  {/if}

  <fieldset class="paths">
    <legend>
      {value.access === 'mtls' ? 'Öffentliche Ausnahmen (ohne Zertifikat erreichbar)' : 'Geschützte Pfade (nur mit Zertifikat)'}
    </legend>
    {#if value.paths.length}
      <ul>
        {#each value.paths as p, i (p)}
          <li>
            <code class="mono">{p}</code>
            <button
              type="button"
              aria-label={`Pfad ${p} entfernen`}
              onclick={() => (value.paths = value.paths.filter((_, j) => j !== i))}
            >
              <Icon name="close" size={12} strokeWidth={2.5} />
            </button>
          </li>
        {/each}
      </ul>
    {/if}
    <div class="row">
      <input
        class="input mono grow"
        placeholder={value.access === 'mtls' ? '/api' : '/admin'}
        aria-label="Pfad hinzufügen"
        disabled={value.access === 'public' && !caConfigured}
        bind:value={newPath}
        onkeydown={onPathKey}
      />
      <button type="button" class="add" onclick={addPath} disabled={!newPath.trim()}>+ Pfad</button>
    </div>
    <span class="muted small">
      <code>/admin</code> gilt auch für alles darunter. Groß-/Kleinschreibung spielt keine Rolle.
    </span>
  </fieldset>

  {#if usesCert}
    <fieldset>
      <legend>Freigegeben für</legend>
      <div class="chips">
        {#each groups as g (g.id)}
          <label class="chip group" class:on={value.grant_group_ids.includes(g.id)}>
            <input type="checkbox" value={g.id} bind:group={value.grant_group_ids} />Gruppe {g.name}
          </label>
        {/each}
        {#each persons as p (p.id)}
          <label class="chip" class:on={value.grant_person_ids.includes(p.id)} class:off={p.disabled}>
            <input type="checkbox" value={p.id} bind:group={value.grant_person_ids} />{p.name}
          </label>
        {/each}
      </div>
      <div class="reach">
        <span><strong>{reach.persons}</strong> <span class="muted">Personen</span></span>
        <span><strong>{reach.devices}</strong> <span class="muted">Geräte mit gültigem Zertifikat</span></span>
      </div>
    </fieldset>

    <label class="field" for="{id}-nocert">
      Ohne passendes Zertifikat
      <select id="{id}-nocert" class="input" bind:value={value.no_cert_action}>
        <option value="reject">Verbindung ablehnen (TLS-Handshake schlägt fehl)</option>
        <option value="hint">Hinweisseite „Kein Zugang“ anzeigen</option>
      </select>
      {#if value.paths.length && value.no_cert_action === 'reject'}
        <span class="muted small">Mit Pfad-Regeln wird statt eines Abbruchs „403 Kein Zugang“ gesendet – der Pfad ist beim Handshake noch unbekannt.</span>
      {/if}
    </label>
  {/if}
</div>

<style>
  .access {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .compact {
    gap: 12px;
  }
  .internal {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border-input);
    cursor: pointer;
    font-size: 14px;
    line-height: 1.45;
  }
  .internal.on {
    border-color: var(--warn);
    background: var(--warn-soft);
  }
  .internal.disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .internal input {
    margin: 3px 0 0;
    width: 18px;
    height: 18px;
    accent-color: var(--accent);
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .modes {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 8px;
  }
  .mode {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border-input);
    cursor: pointer;
    font-size: 14px;
    line-height: 1.45;
  }
  .mode.on {
    border-color: var(--accent);
    background: rgba(139, 124, 246, 0.1);
  }
  .mode.disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .mode-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .mode-head strong {
    flex: 1;
  }
  .mode input {
    margin: 0;
    accent-color: var(--accent);
  }
  fieldset {
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
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  li {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 4px 0 10px;
    min-height: 32px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    font-size: 13px;
  }
  li button {
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
  .grow {
    flex: 1 1 160px;
  }
  .add {
    min-height: 44px;
    padding: 0 14px;
    border-radius: var(--radius);
    border: 1px dashed var(--border-dashed);
    background: transparent;
    color: var(--text-muted);
    font: inherit;
    cursor: pointer;
  }
  .add:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .small {
    font-size: 12px;
    line-height: 1.5;
  }
  code {
    color: var(--text-soft);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 0 12px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }
  .chip.on {
    background: var(--accent-soft);
    color: var(--accent-text);
  }
  .chip.off {
    opacity: 0.6;
    text-decoration: line-through;
  }
  .chip input {
    margin: 0;
    accent-color: var(--accent);
  }
  .reach {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 10px 12px;
    border-radius: var(--radius);
    background: var(--bg);
    font-size: 13px;
  }
</style>
