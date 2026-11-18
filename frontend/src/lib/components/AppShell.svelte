<script lang="ts">
  import type { Snippet } from 'svelte';
  import Sidebar from './Sidebar.svelte';

  type NavId = 'main' | 'hosts' | 'users' | 'devices' | 'access' | 'nodes' | 'stats' | 'audit' | 'settings';

  interface Props {
    active: NavId;
    children: Snippet;
  }

  let { active, children }: Props = $props();
</script>

<div class="shell">
  <div class="side"><Sidebar {active} /></div>
  <main>{@render children()}</main>
</div>

<style>
  .shell {
    min-height: 100vh;
    display: flex;
    flex-wrap: wrap;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 14px;
  }
  .side {
    flex: 1 1 240px;
    background: var(--sidebar);
    border-right: 1px solid var(--border);
  }
  main {
    flex: 999 1 560px;
    min-width: 0;
    padding: 24px 32px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  @media (max-width: 640px) {
    main {
      padding: 20px 16px;
    }
  }
</style>
