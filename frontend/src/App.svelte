<script lang="ts">
  import { router } from './lib/router.svelte';
  import { routes, aliases } from './routes';
  import ScreenIndex from './ScreenIndex.svelte';

  const path = $derived(aliases[router.path] ?? router.path);
  const current = $derived(routes.find((r) => r.path === path));

  $effect(() => {
    document.title = (current ? current.title + ' – ' : 'Screens – ') + 'Tesseract';
  });
</script>

{#if current}
  {#key current.path}
    <current.component />
  {/key}
{:else}
  <ScreenIndex />
{/if}
