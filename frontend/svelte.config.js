import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  compilerOptions: {
    // Die aus dem Design übernommenen Screens nutzen bewusst Inline-Styles;
    // A11y-Warnungen bleiben aktiv, damit man sie beim Überarbeiten sieht.
  }
};
