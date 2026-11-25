<script lang="ts">
  /** Sprache umschalten (Deutsch ↔ English) – lädt die Seite neu. */
  import { lang, LANGUAGES, setLang, t, type Lang } from '../i18n';

  interface Props {
    /** "icon" = kompakter Knopf (Seitenleiste), "link" = Textlink (Anmeldeseite) */
    variant?: 'icon' | 'link';
  }

  let { variant = 'icon' }: Props = $props();

  const codes = Object.keys(LANGUAGES) as Lang[];
  const next = $derived(codes[(codes.indexOf(lang) + 1) % codes.length]);
</script>

{#if variant === 'icon'}
  <button
    type="button"
    class="lang"
    onclick={() => setLang(next)}
    aria-label={t('Sprache: {0} – wechseln zu {1}', LANGUAGES[lang].label, LANGUAGES[next].label)}
    title={t('Sprache: {0} – wechseln zu {1}', LANGUAGES[lang].label, LANGUAGES[next].label)}
    lang={next}
  >
    {lang.toUpperCase()}
  </button>
{:else}
  <button type="button" class="link" onclick={() => setLang(next)} lang={next}>{LANGUAGES[next].label}</button>
{/if}

<style>
  .lang {
    width: 36px;
    height: 36px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    font: 600 11px var(--font-sans);
    letter-spacing: 0.04em;
    cursor: pointer;
    flex-shrink: 0;
  }
  .lang:hover {
    color: var(--text);
  }
  .link {
    border: 0;
    background: none;
    padding: 0;
    color: var(--text-muted);
    font: inherit;
    font-size: 12px;
    text-decoration: underline;
    cursor: pointer;
  }
  .link:hover {
    color: var(--text);
  }
</style>
