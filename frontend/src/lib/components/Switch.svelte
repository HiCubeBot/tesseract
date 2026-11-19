<script lang="ts">
  // Kleiner Ein/Aus-Schalter ohne sichtbaren Text (z. B. in Tabellenzeilen)
  interface Props {
    checked: boolean;
    /** Beschriftung für Screenreader und Tooltip */
    label: string;
    disabled?: boolean;
    onChange: (checked: boolean) => void;
  }

  let { checked, label, disabled = false, onChange }: Props = $props();
</script>

<button
  type="button"
  role="switch"
  class="switch"
  class:on={checked}
  aria-checked={checked}
  aria-label={label}
  title={label}
  {disabled}
  onclick={() => onChange(!checked)}
>
  <span class="knob"></span>
</button>

<style>
  .switch {
    position: relative;
    width: 40px;
    height: 24px;
    flex-shrink: 0;
    padding: 0;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border-input);
    background: var(--surface-raised);
    cursor: pointer;
    transition: background 0.15s;
  }
  .switch.on {
    background: var(--accent);
    border-color: var(--accent);
  }
  .switch:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
    transition: transform 0.15s;
  }
  .on .knob {
    transform: translateX(16px);
  }
  /* Klickfläche größer als der Schalter selbst */
  .switch::after {
    content: '';
    position: absolute;
    inset: -10px -4px;
  }
</style>
