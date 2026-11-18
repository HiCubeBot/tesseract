<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import ChipInput from '../lib/components/ChipInput.svelte';
  import {
    api,
    IP_MODES,
    WAF_MODES,
    type Host,
    type HostInput,
    type HostSaved,
    type IpList,
    type IpMode,
    type WafMode
  } from '../lib/api';
  import { toInput } from '../lib/hosts';
  import { reportApply } from '../lib/nodes';

  let { params = {} }: { params?: Record<string, string> } = $props();
  const hostId = $derived(Number(params.id));

  let host = $state<Host | null>(null);
  let form = $state<HostInput | null>(null);
  let error = $state('');
  let saving = $state(false);
  let newRule = $state('');

  const modes: WafMode[] = ['off', 'detect', 'block'];
  let modeIndex = $state(0);
  const ipModes: IpMode[] = ['off', 'block', 'allow'];
  let ipIndex = $state(0);
  let ipLists = $state<IpList[]>([]);

  async function load() {
    try {
      [host, ipLists] = await Promise.all([api.get<Host>(`/hosts/${hostId}`), api.get<IpList[]>('/ip-lists')]);
      form = toInput(host);
      modeIndex = modes.indexOf(host.waf_mode);
      ipIndex = ipModes.indexOf(host.ip_mode);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  $effect(() => {
    if (form) form.waf_mode = modes[modeIndex];
  });
  $effect(() => {
    if (form) form.ip_mode = ipModes[ipIndex];
  });

  const KEYS = ['waf_mode', 'waf_paranoia', 'waf_exclusions', 'ip_mode', 'ip_entries', 'ip_list_ids'] as const;
  const pick = (o: Record<string, unknown>) => JSON.stringify(KEYS.map((k) => o[k]));
  const dirty = $derived(!!host && !!form && pick(form) !== pick(toInput(host)));
  const ipEmpty = $derived(!!form && form.ip_mode === 'allow' && !form.ip_entries.length && !form.ip_list_ids.length);

  function addRule() {
    if (!form) return;
    const id = Number(newRule.trim());
    if (!Number.isInteger(id) || id < 1) return;
    if (!form.waf_exclusions.includes(id)) form.waf_exclusions = [...form.waf_exclusions, id].sort((a, b) => a - b);
    newRule = '';
  }

  async function save() {
    if (!form || !host) return;
    saving = true;
    try {
      const r = await api.put<HostSaved>(`/hosts/${host.id}`, { ...form, comment: 'Sicherheit' });
      reportApply(r.apply, r.host.domain);
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  const steps = $derived(
    host
      ? [
          { label: 'IP-Filter', on: (form?.ip_mode ?? host.ip_mode) !== 'off', note: IP_MODES[form?.ip_mode ?? host.ip_mode] },
          {
            label: 'Zertifikat',
            on: host.access === 'mtls' || host.paths.length > 0,
            note: host.access === 'mtls' ? 'mTLS' : host.paths.length ? 'einzelne Pfade' : 'aus'
          },
          { label: 'Coraza WAF', on: (form?.waf_mode ?? host.waf_mode) !== 'off', note: WAF_MODES[form?.waf_mode ?? host.waf_mode] },
          { label: 'Authelia', on: false, note: 'folgt' },
          { label: 'Dienst', on: true, note: `${host.upstream_host}:${host.upstream_port}` }
        ]
      : []
  );
</script>

<AppShell active="hosts">
  <header class="head">
    <a href={`#/hosts/${hostId}`} class="crumb">← {host?.domain ?? 'Proxy-Hosts'}</a>
    <h1>Sicherheit</h1>
  </header>

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if host && form}
    <section class="card" aria-labelledby="flow-title">
      <h2 id="flow-title">Weg einer Anfrage</h2>
      <ol class="flow">
        {#each steps as s, i (s.label)}
          <li class:on={s.on}>
            <span class="step-label">{s.label}</span>
            <span class="muted small">{s.note}</span>
          </li>
          {#if i < steps.length - 1}<li class="arrow" aria-hidden="true"><Icon d="M5 12h14M13 6l6 6l-6 6" size={14} /></li>{/if}
        {/each}
      </ol>
    </section>

    <section class="card" aria-labelledby="waf-title">
      <div class="row">
        <h2 id="waf-title">Coraza WAF</h2>
        <span class="muted small">OWASP Core Rule Set</span>
      </div>
      <SegmentedControl groupLabel="WAF-Modus" options={modes.map((m) => WAF_MODES[m])} bind:selected={modeIndex} />
      <p class="muted small">
        {#if form.waf_mode === 'off'}
          Keine Prüfung der Anfragen.
        {:else if form.waf_mode === 'detect'}
          Angriffe werden erkannt und protokolliert, aber nicht blockiert – gut zum Testen neuer Dienste.
        {:else}
          Erkannte Angriffe werden mit „403“ abgewiesen und kommen nie beim Dienst an.
        {/if}
      </p>

      <div class="grid2">
        <label class="field">
          Paranoia-Level
          <select class="input" bind:value={form.waf_paranoia} disabled={form.waf_mode === 'off'}>
            <option value={1}>1 · Standard, kaum Fehlalarme</option>
            <option value={2}>2 · strenger</option>
            <option value={3}>3 · sehr streng</option>
            <option value={4}>4 · maximal, viele Fehlalarme</option>
          </select>
        </label>
      </div>

      <fieldset>
        <legend>Regel-Ausnahmen für Fehlalarme dieses Dienstes</legend>
        {#if form.waf_exclusions.length}
          <ul class="rules">
            {#each form.waf_exclusions as id (id)}
              <li>
                <code class="mono">{id}</code>
                <button
                  type="button"
                  aria-label={`Ausnahme ${id} entfernen`}
                  onclick={() => form && (form.waf_exclusions = form.waf_exclusions.filter((r) => r !== id))}
                >
                  <Icon name="close" size={12} strokeWidth={2.5} />
                </button>
              </li>
            {/each}
          </ul>
        {/if}
        <form class="row" onsubmit={(e) => (e.preventDefault(), addRule())}>
          <input class="input mono rule-input" inputmode="numeric" placeholder="942100" aria-label="Regel-ID" bind:value={newRule} disabled={form.waf_mode === 'off'} />
          <Button type="submit" variant="secondary" size="sm" icon="plus" label="Ausnahme" disabled={form.waf_mode === 'off' || !newRule.trim()} />
        </form>
        <span class="muted small">Die Regel-ID steht im Log beim jeweiligen Treffer (z. B. 942100 = SQL-Injection erkannt).</span>
      </fieldset>
    </section>

    <section class="card" aria-labelledby="ip-title">
      <h2 id="ip-title">IP-Filter</h2>
      <SegmentedControl groupLabel="IP-Filter-Modus" options={ipModes.map((m) => IP_MODES[m])} bind:selected={ipIndex} />
      <p class="muted small">
        {#if form.ip_mode === 'off'}
          Alle IPs dürfen (weitere Regeln wie Zertifikat und WAF gelten trotzdem).
        {:else if form.ip_mode === 'block'}
          Anfragen von diesen IPs/Netzen werden sofort mit „403“ abgewiesen.
        {:else}
          Nur diese IPs/Netze kommen durch – alle anderen bekommen „403“.
        {/if}
      </p>
      {#if form.ip_mode !== 'off'}
        <div class="field">
          IP, Netz (CIDR) – auch mehrere auf einmal einfügen
          <ChipInput bind:values={form.ip_entries} label="IP oder Netz hinzufügen" placeholder="192.168.178.0/24" />
        </div>
        {#if ipLists.length}
          <fieldset>
            <legend>IP-Listen</legend>
            <div class="chips">
              {#each ipLists as l (l.id)}
                <label class="chip" class:on={form.ip_list_ids.includes(l.id)}>
                  <input type="checkbox" value={l.id} bind:group={form.ip_list_ids} />{l.name}
                  <span class="muted tiny">{l.entries.length}</span>
                </label>
              {/each}
            </div>
          </fieldset>
        {/if}
        <span class="muted small">Listen verwaltest du unter <a href="#/settings-integrations">Einstellungen › Integrationen</a>.</span>
        {#if ipEmpty}<p class="field-error">„Nur erlauben“ braucht mindestens einen Eintrag.</p>{/if}
      {/if}
    </section>

    <div class="row sticky">
      <Button label={saving ? 'Überträgt …' : 'Speichern & übertragen'} disabled={!dirty || saving || ipEmpty} onClick={save} />
      <Button variant="secondary" label="Verwerfen" disabled={!dirty || saving} onClick={load} />
      {#if dirty}<span class="muted small">Ungespeicherte Änderungen</span>{/if}
    </div>

    <section class="card muted-card">
      <h2>Authelia</h2>
      <p class="muted small">Folgt im nächsten Schritt von Phase 3.</p>
    </section>
  {/if}
</AppShell>

<style>
  .head {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .crumb {
    font-size: 13px;
    font-weight: 500;
    text-decoration: none;
  }
  h1 {
    margin: 0;
    font-size: 26px;
    letter-spacing: -0.02em;
  }
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  .flow {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .flow li:not(.arrow) {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 12px;
    border-radius: var(--radius);
    background: var(--bg);
    border: 1px solid var(--border-input);
    opacity: 0.6;
  }
  .flow li.on {
    opacity: 1;
    border-color: var(--accent);
  }
  .step-label {
    font-weight: 600;
    font-size: 13px;
  }
  .arrow {
    color: var(--text-muted);
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 320px));
    gap: 12px;
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
  .rules {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .rules li {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 4px 0 10px;
    min-height: 32px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    font-size: 13px;
  }
  .rules button {
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
  .rule-input {
    max-width: 160px;
  }
  .muted-card {
    opacity: 0.75;
  }
  .tiny {
    font-size: 11px;
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
    color: #d6d0ff;
  }
  .chip input {
    margin: 0;
    accent-color: var(--accent);
  }
  .sticky {
    position: sticky;
    bottom: 0;
    padding: 12px 0;
    background: var(--bg);
    border-top: 1px solid var(--border);
    z-index: 5;
  }
</style>
