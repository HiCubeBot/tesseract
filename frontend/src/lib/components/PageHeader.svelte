<script lang="ts">
  import Button from './Button.svelte';
  import type { IconName } from '../icons';

  interface Props {
    title?: string;
    subtitle?: string;
    crumb?: string;
    crumbHref?: string;
    primaryLabel?: string;
    primaryHref?: string;
    primaryIcon?: IconName | 'none';
    onPrimary?: () => void;
    secondaryLabel?: string;
    secondaryHref?: string;
    onSecondary?: () => void;
  }

  let {
    title = '',
    subtitle = '',
    crumb = '',
    crumbHref = '',
    primaryLabel = '',
    primaryHref = '',
    primaryIcon = 'plus',
    onPrimary,
    secondaryLabel = '',
    secondaryHref = '',
    onSecondary
  }: Props = $props();
</script>

<header class="page-header">
  <div class="titles">
    {#if crumb}<a class="crumb" href={crumbHref}>← {crumb}</a>{/if}
    <h1>{title}</h1>
    {#if subtitle}<p>{subtitle}</p>{/if}
  </div>
  <div class="actions">
    {#if secondaryLabel}
      <Button variant="secondary" label={secondaryLabel} href={secondaryHref} onClick={onSecondary} />
    {/if}
    {#if primaryLabel}
      <Button variant="primary" icon={primaryIcon} label={primaryLabel} href={primaryHref} onClick={onPrimary} />
    {/if}
  </div>
</header>

<style>
  .page-header {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    font-family: var(--font-sans);
    color: var(--text);
  }
  .titles {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .crumb {
    font-size: 13px;
    font-weight: 500;
    text-decoration: none;
  }
  h1 {
    margin: 0;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  p {
    margin: 0;
    font-size: 14px;
    color: var(--text-muted);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
</style>
