<script lang="ts">
  interface Props {
    time?: string;
    title?: string;
    detail?: string;
    tone?: 'neutral' | 'ok' | 'warn' | 'bad' | 'mtls';
  }

  let { time = '', title = '', detail = '', tone = 'neutral' }: Props = $props();
</script>

<div class="event">
  <span class="time">{time}</span>
  <div class="body">
    <span class="title {tone}">{title}</span>
    {#if detail}<span class="detail">{detail}</span>{/if}
  </div>
</div>

<style>
  .event {
    width: 100%;
    display: flex;
    gap: 12px;
    padding: 9px 0;
    border-top: 1px solid var(--border);
    font-family: var(--font-sans);
    font-size: 14px;
  }
  /* breit genug für „19.11. 22:52“ (zweizeilig); längere Angaben brechen um statt überzulaufen */
  .time {
    width: 60px;
    flex-shrink: 0;
    overflow-wrap: anywhere;
    padding-top: 2px;
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .title { font-weight: 500; color: var(--text); }
  .title.warn { color: var(--warn-text); }
  .title.bad { color: var(--bad-text); }
  .title.mtls { color: var(--accent-text); }
  .detail {
    font-size: 13px;
    color: var(--text-muted);
  }
</style>
