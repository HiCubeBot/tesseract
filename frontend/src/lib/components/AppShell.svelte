<script lang="ts">
  import type { Snippet } from 'svelte';
  import Sidebar from './Sidebar.svelte';

  type NavId =
    | 'main'
    | 'hosts'
    | 'certificates'
    | 'users'
    | 'devices'
    | 'access'
    | 'nodes'
    | 'stats'
    | 'audit'
    | 'settings'
    | 'me';

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
    display: flex;
    background: var(--sidebar);
    border-right: 1px solid var(--border);
  }
  /* Breit genug für die Seitenleiste neben dem Inhalt: über die volle Höhe, mitlaufend */
  @media (min-width: 820px) {
    .side {
      position: sticky;
      top: 0;
      height: 100vh;
      align-self: flex-start;
      overflow-y: auto;
    }
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
