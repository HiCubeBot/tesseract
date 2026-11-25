<script lang="ts">
  import { t } from '../i18n';
  import Button from './Button.svelte';
  import ChipInput from './ChipInput.svelte';
  import { api, CLOUDFLARE_RANGES, type IpList } from '../api';
  import { toasts } from '../toast.svelte';

  interface Props {
    lists: IpList[];
    onChange: () => void;
  }

  let { lists, onChange }: Props = $props();

  let editId = $state<number | 'new' | null>(null);
  let name = $state('');
  let description = $state('');
  let entries = $state<string[]>([]);
  let busy = $state(false);
  let error = $state('');

  function open(l: IpList | null, template?: 'cloudflare') {
    editId = l ? l.id : 'new';
    name = l?.name ?? (template === 'cloudflare' ? t('Cloudflare') : '');
    description = l?.description ?? (template === 'cloudflare' ? t('Netze von Cloudflare (Proxy)') : '');
    entries = l ? [...l.entries] : template === 'cloudflare' ? [...CLOUDFLARE_RANGES] : [];
    error = '';
  }

  async function save(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    error = '';
    try {
      const body = { name, description, entries };
      if (editId === 'new') await api.post('/ip-lists', body);
      else await api.put(`/ip-lists/${editId}`, body);
      toasts.show('ok', t('Liste „{0}“ gespeichert.', name));
      editId = null;
      onChange();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      busy = false;
    }
  }

  async function remove(l: IpList) {
    if (!confirm(t('Liste „{0}“ löschen?', l.name))) return;
    try {
      await api.del(`/ip-lists/${l.id}`);
      onChange();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }
</script>

<ul class="lists">
  {#each lists as l (l.id)}
    <li>
      <span class="stack">
        <strong>{l.name}</strong>
        <span class="muted small">
          {t('{0} Einträge{1} {2}', l.entries.length, l.description ? ` · ${l.description}` : '', l.used_by.length ? t(' · genutzt von {0}', l.used_by.join(', ')) : '')}
        </span>
      </span>
      <span class="spacer"></span>
      <Button variant="ghost" size="sm" label={t('Bearbeiten')} onClick={() => open(l)} />
      <Button variant="ghost" size="sm" label={t('Löschen')} disabled={l.used_by.length > 0} onClick={() => remove(l)} />
    </li>
  {:else}
    <li class="muted small">{t('Noch keine Listen.')}</li>
  {/each}
</ul>

{#if editId !== null}
  <form class="card editor" onsubmit={save}>
    <div class="grid">
      <label class="field">{t('Name')}<input class="input" required maxlength="64" bind:value={name} /></label>
      <label class="field">{t('Beschreibung')}<input class="input" maxlength="255" bind:value={description} /></label>
    </div>
    <div class="field">
      {t('Einträge (IP oder Netz)')}
      <ChipInput bind:values={entries} label={t('Eintrag hinzufügen')} placeholder="198.51.100.0/24" />
    </div>
    {#if error}<p class="field-error" role="alert">{error}</p>{/if}
    <div class="row">
      <Button type="submit" label={busy ? t('Speichert …') : t('Speichern')} disabled={busy} />
      <Button variant="ghost" label={t('Abbrechen')} onClick={() => (editId = null)} />
    </div>
  </form>
{:else}
  <div class="row">
    <Button variant="secondary" size="sm" icon="plus" label={t('Neue Liste')} onClick={() => open(null)} />
    {#if !lists.some((l) => l.name === 'Cloudflare')}
      <Button variant="ghost" size="sm" label={t('Vorlage: Cloudflare')} onClick={() => open(null, 'cloudflare')} />
    {/if}
  </div>
{/if}

<style>
  .lists {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .lists li {
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
  .small {
    font-size: 12px;
  }
  .editor {
    background: var(--bg);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
  }
</style>
