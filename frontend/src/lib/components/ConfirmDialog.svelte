<script lang="ts">
  import { t } from '../i18n';
  import Icon from './Icon.svelte';

  interface Props {
    title?: string;
    text?: string;
    /** Wort, das zum Bestätigen eingetippt werden muss */
    word?: string;
    confirmLabel?: string;
    tone?: 'danger' | 'warn';
    onConfirm?: () => void;
    onCancel?: () => void;
  }

  let {
    title = '',
    text = '',
    word = t('bestätigen'),
    confirmLabel = t('Bestätigen'),
    tone = 'danger',
    onConfirm,
    onCancel
  }: Props = $props();

  const id = $props.id();
  let typed = $state('');
  const ok = $derived(typed.trim().toLowerCase() === word.toLowerCase());
</script>

<section role="dialog" aria-modal="true" aria-labelledby="{id}-title" class="dialog {tone}">
  <div class="head">
    <div class="icon"><Icon name="warn" size={18} strokeWidth={2} /></div>
    <h2 id="{id}-title">{title}</h2>
  </div>
  {#if text}<p>{text}</p>{/if}
  <label>
    <span>{t('Zum Bestätigen')} <strong>{word}</strong> {t('eingeben')}</span>
    <input type="text" autocomplete="off" bind:value={typed} />
  </label>
  <div class="actions">
    <button type="button" class="cancel" onclick={() => onCancel?.()}>{t('Abbrechen')}</button>
    <button type="button" class="confirm" disabled={!ok} onclick={() => ok && onConfirm?.()}>{confirmLabel}</button>
  </div>
</section>

<style>
  .dialog {
    --c: var(--bad-text);
    --soft: rgba(240, 113, 103, 0.16);
    --solid: var(--bad);
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 22px;
    border-radius: 14px;
    background: var(--surface);
    border: 1px solid var(--border-input);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
    font-family: var(--font-sans);
    color: var(--text);
  }
  .warn {
    --c: var(--warn-text);
    --soft: rgba(229, 164, 67, 0.16);
    --solid: var(--warn);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .icon {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--c);
    background: var(--soft);
  }
  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.5;
    color: var(--text-soft);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    color: var(--text-muted);
  }
  strong {
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text);
  }
  input {
    width: 100%;
    min-height: 44px;
    padding: 0 12px;
    border-radius: var(--radius);
    background: var(--bg);
    border: 1px solid var(--border-input);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 14px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 10px;
  }
  button {
    min-height: 44px;
    padding: 0 16px;
    border-radius: var(--radius);
    font: inherit;
    cursor: pointer;
  }
  .cancel {
    border: 1px solid var(--border-input);
    background: var(--surface);
    color: var(--text);
    font-weight: 500;
  }
  .confirm {
    font-weight: 600;
    border: 1px solid var(--solid);
    background: var(--solid);
    color: var(--bg);
  }
  .confirm:disabled {
    background: transparent;
    color: var(--c);
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
