<script lang="ts">
  interface Props {
    label?: string;
    value?: string;
    sub?: string;
    tone?: 'ok' | 'warn' | 'bad' | 'mtls' | 'neutral';
    subTone?: 'muted' | 'ok' | 'warn' | 'bad';
  }

  let { label = '', value = '', sub = '', tone = 'neutral', subTone = 'muted' }: Props = $props();
</script>

<div class="card">
  <div class="head">
    <span class="dot {tone}"></span>
    <span>{label}</span>
  </div>
  <span class="value">{value}</span>
  {#if sub}<span class="sub {subTone}">{sub}</span>{/if}
</div>

<style>
  .card {
    width: 100%;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 16px 18px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    border: 1px solid var(--border);
    font-family: var(--font-sans);
    color: var(--text);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
  }
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot.ok { background: var(--ok); }
  .dot.warn { background: var(--warn); }
  .dot.bad { background: var(--bad); }
  .dot.mtls { background: var(--accent); }
  .dot.neutral { background: var(--text-muted); }
  .value {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }
  .sub { font-size: 13px; }
  .sub.muted { color: var(--text-muted); }
  .sub.ok { color: var(--ok-text); }
  .sub.warn { color: var(--warn-text); }
  .sub.bad { color: var(--bad-text); }
</style>
