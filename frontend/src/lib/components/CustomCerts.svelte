<script lang="ts">
  import { t } from '../i18n';
  import Button from './Button.svelte';
  import StatusPill from './StatusPill.svelte';
  import { api, formatDay, type CustomCert } from '../api';
  import { toasts } from '../toast.svelte';

  interface Props {
    onChange?: () => void;
  }

  let { onChange }: Props = $props();

  let certs = $state<CustomCert[]>([]);
  let editId = $state<number | 'new' | null>(null);
  let name = $state('');
  let certificate = $state('');
  let key = $state('');
  let busy = $state(false);
  let error = $state('');

  async function load() {
    try {
      certs = await api.get<CustomCert[]>('/custom-certs');
    } catch {
      certs = [];
    }
  }
  load();

  function open(c: CustomCert | null) {
    editId = c ? c.id : 'new';
    name = c?.name ?? '';
    certificate = '';
    key = '';
    error = '';
  }

  async function readFile(e: Event, target: 'certificate' | 'key') {
    const file = (e.currentTarget as HTMLInputElement).files?.[0];
    if (!file) return;
    const text = await file.text();
    if (target === 'certificate') certificate = text;
    else key = text;
  }

  async function save(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    error = '';
    try {
      const body = { name, certificate, key };
      if (editId === 'new') await api.post('/custom-certs', body);
      else await api.put(`/custom-certs/${editId}`, body);
      toasts.show('ok', t('Zertifikat „{0}“ gespeichert.', name));
      editId = null;
      certificate = key = '';
      await load();
      onChange?.();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      busy = false;
    }
  }

  async function remove(c: CustomCert) {
    if (!confirm(t('Zertifikat „{0}“ löschen?', c.name))) return;
    try {
      await api.del(`/custom-certs/${c.id}`);
      await load();
      onChange?.();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  const days = (iso: string) => Math.floor((new Date(iso).getTime() - Date.now()) / 86400_000);
</script>

<section class="card" aria-labelledby="custom-title">
  <h2 id="custom-title" class="card-title">{t('Eigene Zertifikate')}</h2>
  <p class="muted small">
    {t('Zertifikat und Schlüssel hochladen (z. B. von einer Firmen-CA) und im Host unter „Zertifikat“ auswählen. Der Schlüssel wird verschlüsselt gespeichert. Eigene Zertifikate erneuert niemand automatisch – vor Ablauf hier das neue einspielen.')}
  </p>

  {#if certs.length}
    <ul>
      {#each certs as c (c.id)}
        {@const d = days(c.not_after)}
        <li>
          <span class="stack">
            <strong>{c.name}</strong>
            <span class="muted small mono">{c.names.join(', ')}</span>
            <span class="muted small">
              {t('{0} · bis {1} · {2}', c.issuer, formatDay(c.not_after), c.used_by.length ? t('genutzt von {0}', c.used_by.join(', ')) : t('nicht genutzt'))}
            </span>
          </span>
          <span class="spacer"></span>
          <StatusPill tone={d < 0 ? 'bad' : d < 21 ? 'warn' : 'ok'} label={d < 0 ? 'abgelaufen' : t('{0} Tage', d)} />
          <Button variant="ghost" size="sm" label={t('Erneuern')} onClick={() => open(c)} />
          <Button variant="ghost" size="sm" label={t('Löschen')} disabled={c.used_by.length > 0} onClick={() => remove(c)} />
        </li>
      {/each}
    </ul>
  {/if}

  {#if editId !== null}
    <form class="editor" onsubmit={save}>
      <label class="field">{t('Name')}<input class="input" required maxlength="64" bind:value={name} placeholder={t('Firmen-CA Intranet')} /></label>
      <div class="grid">
        <label class="field">
          {t('Zertifikat (PEM, mit Zwischenzertifikaten)')}
          <input type="file" accept=".pem,.crt,.cer" onchange={(e) => readFile(e, 'certificate')} />
          <textarea class="input mono" rows="5" required bind:value={certificate} placeholder="-----BEGIN CERTIFICATE-----"></textarea>
        </label>
        <label class="field">
          {t('Privater Schlüssel (PEM, unverschlüsselt)')}
          <input type="file" accept=".pem,.key" onchange={(e) => readFile(e, 'key')} />
          <textarea class="input mono" rows="5" required bind:value={key} placeholder="-----BEGIN PRIVATE KEY-----"></textarea>
        </label>
      </div>
      {#if error}<p class="field-error" role="alert">{error}</p>{/if}
      <div class="row">
        <Button type="submit" label={busy ? t('Prüft …') : editId === 'new' ? t('Hochladen') : t('Erneuern & übertragen')} disabled={busy} />
        <Button variant="ghost" label={t('Abbrechen')} onClick={() => (editId = null)} />
      </div>
    </form>
  {:else}
    <div class="row"><Button variant="secondary" size="sm" icon="plus" label={t('Zertifikat hochladen')} onClick={() => open(null)} /></div>
  {/if}
</section>

<style>
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
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
    margin: 0;
    line-height: 1.5;
  }
  .editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border-input);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }
  textarea {
    min-height: 110px;
    padding: 8px 10px;
    font-size: 12px;
    resize: vertical;
  }
  input[type='file'] {
    font-size: 12px;
    color: var(--text-muted);
  }
</style>
