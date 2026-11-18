<script lang="ts">
  /** Host-Bereiche: Pfade mit abweichenden Regeln. Leer/„wie Host“ = Einstellung des Hosts. */
  import Button from './Button.svelte';
  import ChipInput from './ChipInput.svelte';
  import type { AreaInput, Group, IpList, Person } from '../api';

  interface Props {
    areas: AreaInput[];
    groups: Group[];
    persons: Person[];
    ipLists: IpList[];
    autheliaAvailable: boolean;
  }

  let { areas = $bindable(), groups, persons, ipLists, autheliaAvailable }: Props = $props();

  function add() {
    areas = [
      ...areas,
      {
        name: '',
        paths: [],
        access: null,
        grant_group_ids: [],
        grant_person_ids: [],
        waf_mode: null,
        waf_exclusions: [],
        authelia: null,
        ip_mode: null,
        ip_entries: [],
        ip_list_ids: []
      }
    ];
  }

  function move(i: number, d: -1 | 1) {
    const j = i + d;
    if (j < 0 || j >= areas.length) return;
    const next = [...areas];
    [next[i], next[j]] = [next[j], next[i]];
    areas = next;
  }

  // Auswahlfelder arbeiten mit Text; null = „wie Host“
  const toSel = (v: unknown) => (v === null || v === undefined ? '' : String(v));
  const fromSel = <T,>(v: string, map: (s: string) => T): T | null => (v === '' ? null : map(v));
</script>

<div class="areas">
  {#each areas as a, i (i)}
    <section class="area" aria-label={`Bereich ${a.name || i + 1}`}>
      <div class="head">
        <input class="input name" placeholder="Name, z. B. API" maxlength="64" bind:value={a.name} aria-label="Name des Bereichs" />
        <span class="spacer"></span>
        <Button variant="ghost" size="sm" label="↑" disabled={i === 0} onClick={() => move(i, -1)} />
        <Button variant="ghost" size="sm" label="↓" disabled={i === areas.length - 1} onClick={() => move(i, 1)} />
        <Button variant="ghost" size="sm" label="Entfernen" onClick={() => (areas = areas.filter((_, j) => j !== i))} />
      </div>

      <div class="field">
        Pfade
        <ChipInput bind:values={a.paths} label="Pfad hinzufügen" placeholder="/api" />
        {#if !a.paths.length}<span class="field-error">Mindestens ein Pfad.</span>{/if}
      </div>

      <div class="grid">
        <label class="field">
          Zugriff
          <select
            class="input"
            value={toSel(a.access)}
            onchange={(e) => (a.access = fromSel(e.currentTarget.value, (s) => s as 'public' | 'mtls'))}
          >
            <option value="">wie Host</option>
            <option value="public">Öffentlich</option>
            <option value="mtls">Nur mit Zertifikat</option>
          </select>
        </label>
        <label class="field">
          Coraza WAF
          <select
            class="input"
            value={toSel(a.waf_mode)}
            onchange={(e) => (a.waf_mode = fromSel(e.currentTarget.value, (s) => s as 'off' | 'detect' | 'block'))}
          >
            <option value="">wie Host</option>
            <option value="off">Aus</option>
            <option value="detect">Nur protokollieren</option>
            <option value="block">Blockieren</option>
          </select>
        </label>
        <label class="field">
          Authelia
          <select
            class="input"
            value={toSel(a.authelia)}
            onchange={(e) => (a.authelia = fromSel(e.currentTarget.value, (s) => s === 'true'))}
          >
            <option value="">wie Host</option>
            <option value="true" disabled={!autheliaAvailable}>Login über Authelia</option>
            <option value="false">ohne Login</option>
          </select>
        </label>
        <label class="field">
          IP-Filter
          <select
            class="input"
            value={toSel(a.ip_mode)}
            onchange={(e) => (a.ip_mode = fromSel(e.currentTarget.value, (s) => s as 'off' | 'block' | 'allow'))}
          >
            <option value="">wie Host</option>
            <option value="off">Aus</option>
            <option value="block">Sperren</option>
            <option value="allow">Nur erlauben</option>
          </select>
        </label>
      </div>

      {#if a.access === 'mtls'}
        <fieldset>
          <legend>Freigegeben für (leer = wie Host)</legend>
          <div class="chips">
            {#each groups as g (g.id)}
              <label class="chip" class:on={a.grant_group_ids.includes(g.id)}>
                <input type="checkbox" value={g.id} bind:group={a.grant_group_ids} />Gruppe {g.name}
              </label>
            {/each}
            {#each persons as p (p.id)}
              <label class="chip" class:on={a.grant_person_ids.includes(p.id)}>
                <input type="checkbox" value={p.id} bind:group={a.grant_person_ids} />{p.name}
              </label>
            {/each}
          </div>
        </fieldset>
      {/if}

      {#if a.ip_mode === 'block' || a.ip_mode === 'allow'}
        <div class="field">
          IPs/Netze für diesen Bereich
          <ChipInput bind:values={a.ip_entries} label="IP oder Netz hinzufügen" placeholder="192.168.178.0/24" />
        </div>
        {#if ipLists.length}
          <div class="chips">
            {#each ipLists as l (l.id)}
              <label class="chip" class:on={a.ip_list_ids.includes(l.id)}>
                <input type="checkbox" value={l.id} bind:group={a.ip_list_ids} />{l.name}
              </label>
            {/each}
          </div>
        {/if}
      {/if}

      {#if a.waf_mode !== 'off'}
        <div class="field">
          Zusätzliche WAF-Ausnahmen nur hier (Regel-IDs)
          <ChipInput
            bind:values={
              () => a.waf_exclusions.map(String),
              (v) => (a.waf_exclusions = v.map(Number).filter((n) => Number.isInteger(n) && n > 0))
            }
            label="Regel-ID hinzufügen"
            placeholder="942100"
          />
        </div>
      {/if}
    </section>
  {/each}

  <div class="row">
    <Button variant="secondary" size="sm" icon="plus" label="Bereich hinzufügen" onClick={add} />
    <span class="muted small">Der erste passende Bereich gewinnt – Reihenfolge mit ↑ ↓.</span>
  </div>
</div>

<style>
  .areas {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .area {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border-input);
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  .name {
    max-width: 260px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 10px;
  }
  fieldset {
    margin: 0;
    padding: 0;
    border: none;
  }
  legend {
    padding: 0;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--text-muted);
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
    min-height: 32px;
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
  .small {
    font-size: 12px;
  }
</style>
