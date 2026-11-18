<script lang="ts">
  import { routes } from './routes';
</script>

<main class="index">
  <header>
    <span class="eyebrow">Tesseract · Prototyp</span>
    <h1>Alle Screens</h1>
    <p>Diese Seite erscheint unter <code>#/screens</code> und bei unbekannten Pfaden.</p>
  </header>
  <ul>
    {#each routes as r (r.path)}
      <li>
        <a href={'#/' + r.path}>
          <span class="title">{r.title}</span>
          <code>#/{r.path}</code>
        </a>
      </li>
    {/each}
  </ul>
</main>

<style>
  .index {
    max-width: 960px;
    margin: 0 auto;
    padding: 40px 24px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  header {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .eyebrow {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  h1 {
    margin: 0;
    font-size: 30px;
    letter-spacing: -0.02em;
  }
  p {
    margin: 0;
    color: var(--text-muted);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 10px;
  }
  a {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-height: 64px;
    padding: 12px 16px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    border: 1px solid var(--border);
    text-decoration: none;
    color: var(--text);
  }
  a:hover {
    border-color: var(--accent);
  }
  .title {
    font-weight: 600;
  }
  code {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
  }
</style>
