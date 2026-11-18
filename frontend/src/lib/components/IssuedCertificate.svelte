<script lang="ts">
  import Button from './Button.svelte';
  import Alert from './Alert.svelte';
  import { base64ToBytes, downloadFile, type IssuedDevice } from '../api';

  interface Props {
    issued: IssuedDevice;
    onClose: () => void;
  }

  let { issued, onClose }: Props = $props();

  let downloaded = $state(false);
  let copied = $state(false);

  function download() {
    downloadFile(issued.filename, base64ToBytes(issued.p12_base64), 'application/x-pkcs12');
    downloaded = true;
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(issued.password);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      /* Zwischenablage nicht verfügbar – Passwort steht ja da */
    }
  }
</script>

<section class="card issued" aria-labelledby="issued-title">
  <h2 id="issued-title">Zertifikat für „{issued.device.name}“ ist bereit</h2>
  <Alert
    tone="warn"
    title="Nur jetzt verfügbar"
    text="Der Schlüssel wird nicht gespeichert. Datei und Passwort gibt es nur in diesem Fenster."
  />
  <div class="row">
    <Button icon="download" label="Zertifikat herunterladen (.p12)" onClick={download} />
  </div>
  <div class="field">
    Passwort zum Importieren
    <div class="pw">
      <code class="mono">{issued.password}</code>
      <Button variant="secondary" size="sm" label={copied ? 'Kopiert' : 'Kopieren'} onClick={copy} />
    </div>
    <span class="muted small">Datei und Passwort möglichst auf getrennten Wegen weitergeben.</span>
  </div>
  <div class="row">
    <span class="spacer"></span>
    <Button variant={downloaded ? 'primary' : 'secondary'} label="Fertig" onClick={onClose} />
  </div>
</section>

<style>
  .issued {
    border-color: var(--accent);
  }
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .pw {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }
  code {
    padding: 8px 12px;
    border-radius: var(--radius);
    background: var(--bg);
    border: 1px solid var(--border-input);
    color: var(--text);
    font-size: 15px;
    letter-spacing: 0.03em;
  }
  .small {
    font-size: 12px;
  }
</style>
