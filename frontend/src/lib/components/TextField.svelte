<script lang="ts">
  interface Props {
    label?: string;
    /** bindbar: bind:value */
    value?: string;
    placeholder?: string;
    hint?: string;
    /** Fehlermeldung – ersetzt den Hinweis und färbt das Feld rot */
    error?: string;
    mono?: boolean;
    type?: 'text' | 'email' | 'url' | 'number' | 'password' | 'search';
  }

  let {
    label = '',
    value = $bindable(''),
    placeholder = '',
    hint = '',
    error = '',
    mono = true,
    type = 'text'
  }: Props = $props();

  const id = $props.id();
  const message = $derived(error || hint);
</script>

<div class="field">
  <label for="{id}-input">{label}</label>
  <input
    id="{id}-input"
    {type}
    bind:value
    {placeholder}
    class:mono
    class:invalid={!!error}
    aria-invalid={error ? 'true' : undefined}
    aria-describedby={message ? `${id}-msg` : undefined}
  />
  {#if message}
    <span id="{id}-msg" class="msg" class:error={!!error}>{message}</span>
  {/if}
</div>

<style>
  .field {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--text-muted);
  }
  input {
    width: 100%;
    min-height: 44px;
    padding: 0 12px;
    border-radius: var(--radius);
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 14px;
    border: 1px solid var(--border-input);
  }
  input.mono {
    font-family: var(--font-mono);
  }
  input.invalid {
    border-color: var(--bad);
  }
  .msg {
    font-size: 12px;
    color: var(--text-muted);
  }
  .msg.error {
    color: var(--bad-text);
  }
</style>
