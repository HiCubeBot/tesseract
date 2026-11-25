<script lang="ts">
  import { t } from '../i18n';
  import { toasts } from '../toast.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each toasts.items as toast (toast.id)}
    <div class="toast {toast.tone}" role={toast.tone === 'bad' ? 'alert' : 'status'}>
      <span>{toast.text}</span>
      <button type="button" aria-label={t('Schließen')} onclick={() => toasts.dismiss(toast.id)}>×</button>
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    right: 16px;
    bottom: 16px;
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: min(420px, calc(100vw - 32px));
  }
  .toast {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--surface-raised);
    border: 1px solid var(--border-input);
    color: var(--text);
    font-size: 14px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }
  .toast span {
    flex: 1;
    line-height: 1.45;
  }
  .ok {
    border-color: rgba(76, 195, 138, 0.5);
  }
  .warn {
    border-color: rgba(229, 164, 67, 0.55);
  }
  .bad {
    border-color: rgba(240, 113, 103, 0.6);
  }
  button {
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
  }
</style>
