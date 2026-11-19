<script lang="ts">
  type Tone = 'ok' | 'warn' | 'bad' | 'mtls' | 'neutral';

  interface Props {
    tone?: Tone;
    label?: string;
    dot?: boolean;
  }

  let { tone = 'ok', label = '', dot = true }: Props = $props();
</script>

<span class="pill {tone}">
  {#if dot}<span class="dot"></span>{/if}
  <span>{label}</span>
</span>

<style>
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-family: var(--font-sans);
    font-size: 12px;
    font-weight: 600;
    line-height: 1.2;
    white-space: nowrap;
  }
  .dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .ok { color: var(--ok-text); background: var(--ok-soft); }
  .ok .dot { background: var(--ok); }
  .warn { color: var(--warn-text); background: var(--warn-soft); }
  .warn .dot { background: var(--warn); }
  .bad { color: var(--bad-text); background: var(--bad-soft); }
  .bad .dot { background: var(--bad); }
  .mtls { color: var(--accent-text); background: var(--accent-soft); }
  .mtls .dot { background: var(--accent); }
  .neutral { color: var(--text-soft); background: var(--surface-raised); }
  .neutral .dot { background: var(--text-muted); }
</style>
