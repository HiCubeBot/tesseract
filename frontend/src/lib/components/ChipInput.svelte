<script lang="ts">
  import { t } from '../i18n';
  /** Liste von Einträgen als Chips + Eingabefeld (Enter fügt hinzu, Einfügen mehrerer Zeilen geht). */
  import Icon from './Icon.svelte';

  interface Props {
    values: string[];
    placeholder?: string;
    label: string;
    disabled?: boolean;
    mono?: boolean;
  }

  let { values = $bindable(), placeholder = '', label, disabled = false, mono = true }: Props = $props();

  let draft = $state('');

  function add() {
    const items = draft
      .split(/[\s,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!items.length) return;
    values = [...new Set([...values, ...items])];
    draft = '';
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      add();
    }
  }
</script>

<div class="chip-input">
  {#if values.length}
    <ul>
      {#each values as v (v)}
        <li>
          <span class:mono>{v}</span>
          <button type="button" aria-label={`${v} entfernen`} {disabled} onclick={() => (values = values.filter((x) => x !== v))}>
            <Icon name="close" size={12} strokeWidth={2.5} />
          </button>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="row">
    <input class="input grow" class:mono {placeholder} aria-label={label} {disabled} bind:value={draft} onkeydown={onKey} onblur={add} />
    <button type="button" class="add" onclick={add} disabled={disabled || !draft.trim()}>{t('+ Hinzufügen')}</button>
  </div>
</div>

<style>
  .chip-input {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    max-height: 180px;
    overflow: auto;
  }
  li {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 4px 0 10px;
    min-height: 30px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    font-size: 13px;
  }
  li button {
    width: 24px;
    height: 24px;
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
</style>
