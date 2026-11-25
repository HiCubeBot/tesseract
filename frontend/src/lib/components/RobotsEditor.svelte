<script lang="ts">
  /** robots.txt eines Hosts: Vorlage wählen, anpassen, Vorschau mit Syntaxprüfung. */
  import Button from './Button.svelte';
  import ChipInput from './ChipInput.svelte';
  import { api, ROBOTS_MODES, type HostInput, type RobotsMode, type RobotsPreview } from '../api';

  interface Props {
    value: HostInput;
    /** gespeicherter Host – zum Laden der robots.txt des Dienstes */
    hostId?: number;
    /** eigener Text mit Syntaxfehlern – Speichern sperren */
    invalid?: boolean;
  }

  let { value = $bindable(), hostId, invalid = $bindable(false) }: Props = $props();

  const modes = Object.keys(ROBOTS_MODES) as RobotsMode[];
  const mode = $derived<RobotsMode>(value.robots ?? 'off');

  let preview = $state<RobotsPreview | null>(null);
  let loading = $state(false);
  let upstreamError = $state('');

  // Vorschau nach jeder Änderung (kurz verzögert)
  $effect(() => {
    const body = {
      robots: mode,
      robots_paths: value.robots_paths,
      robots_sitemap: value.robots_sitemap,
      robots_text: value.robots_text,
      access: value.access
    };
    const timer = setTimeout(async () => {
      try {
        preview = await api.post<RobotsPreview>('/hosts/robots/preview', body);
      } catch {
        preview = null;
      }
    }, 250);
    return () => clearTimeout(timer);
  });

  $effect(() => {
    invalid = mode === 'custom' && !!preview?.errors.length;
  });

  function choose(m: RobotsMode) {
    // Beim Wechsel auf „Eigener Text“ die aktuelle Vorlage als Startpunkt übernehmen
    if (m === 'custom' && !value.robots_text.trim() && preview?.text) value.robots_text = preview.text;
    value.robots = m;
  }

  async function loadUpstream() {
    if (!hostId) return;
    loading = true;
    upstreamError = '';
    try {
      const r = await api.get<{ text: string }>(`/hosts/${hostId}/robots/upstream`);
      value.robots_text = r.text;
      value.robots = 'custom';
    } catch (e) {
      upstreamError = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }
</script>

<div class="robots">
  <label class="field">
    Vorlage
    <select class="input" value={mode} onchange={(e) => choose((e.currentTarget as HTMLSelectElement).value as RobotsMode)}>
      {#each modes as m (m)}<option value={m}>{ROBOTS_MODES[m]}</option>{/each}
    </select>
  </label>

  {#if mode === 'paths'}
    <ChipInput label="Gesperrte Pfade" bind:values={value.robots_paths} placeholder="/admin, /api …" />
  {/if}

  {#if mode === 'custom'}
    <label class="field">
      Eigener Text
      <textarea class="input mono" rows="10" spellcheck="false" bind:value={value.robots_text}></textarea>
    </label>
  {/if}

  {#if mode !== 'off' && mode !== 'custom'}
    <label class="field">
      <span>Sitemap <span class="muted">(optional)</span></span>
      <input class="input mono" bind:value={value.robots_sitemap} placeholder="https://{value.domain || 'example.org'}/sitemap.xml" />
    </label>
  {/if}

  {#if hostId}
    <div class="row">
      <Button variant="secondary" size="sm" label={loading ? 'Lädt …' : 'robots.txt des Dienstes übernehmen'} disabled={loading} onClick={loadUpstream} />
      <span class="muted small">lädt die Datei vom Ziel als eigenen Text zum Anpassen</span>
    </div>
    {#if upstreamError}<p class="field-error">{upstreamError}</p>{/if}
  {/if}

  {#if preview}
    {#if preview.text}
      <div class="preview">
        <span class="muted small">
          {preview.from_settings
            ? 'Vorschau – kommt aus den Einstellungen (mTLS-Hosts: alles verbieten)'
            : `Vorschau – Caddy liefert https://${value.domain || '…'}/robots.txt so aus`}
        </span>
        <pre class="mono">{preview.text}</pre>
      </div>
    {:else}
      <p class="muted small">Caddy liefert keine eigene robots.txt aus – Anfragen gehen an den Dienst.</p>
    {/if}
    {#each preview.errors as e (e)}<p class="field-error">{e}</p>{/each}
    {#each preview.warnings as w (w)}<p class="warn small">{w}</p>{/each}
  {/if}
</div>

<style>
  .robots {
    display: grid;
    gap: 12px;
  }
  .field {
    display: grid;
    gap: 6px;
    font-size: 13px;
  }
  textarea {
    resize: vertical;
    font-size: 12px;
    line-height: 1.5;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }
  .small {
    font-size: 12px;
    margin: 0;
  }
  .preview {
    display: grid;
    gap: 6px;
  }
  pre {
    margin: 0;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--surface-raised);
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 260px;
    overflow: auto;
  }
  .warn {
    color: var(--warn-text);
  }
</style>
