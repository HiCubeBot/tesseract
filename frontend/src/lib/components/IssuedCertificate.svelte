<script lang="ts">
  // Zertifikat eines Geräts: .p12 herunterladen, Passwort zeigen, per QR-Code aufs Handy holen.
  // Für frisch ausgestellte und (wenn hinterlegt) für bestehende Geräte.
  import Button from './Button.svelte';
  import Alert from './Alert.svelte';
  import { api, base64ToBytes, downloadFile, type IssuedDevice } from '../api';
  import { toasts } from '../toast.svelte';

  interface Props {
    issued: IssuedDevice;
    onClose: () => void;
    /** später erneut abgerufen (statt frisch ausgestellt) */
    again?: boolean;
    /** hinterlegte Kopie löschen (nur bei `again`) */
    onForget?: () => void;
  }

  let { issued, onClose, again = false, onForget }: Props = $props();

  let downloaded = $state(false);
  let copied = $state(false);
  let link = $state<{ url: string; expires_at: number; uses: number; qr_svg: string } | null>(null);
  let linkBusy = $state(false);
  const stored = $derived(issued.device.p12_stored);

  function download() {
    downloadFile(issued.filename, base64ToBytes(issued.p12_base64), 'application/x-pkcs12');
    downloaded = true;
  }

  async function copy(text: string, what: 'pw' | 'link') {
    try {
      await navigator.clipboard.writeText(text);
      if (what === 'pw') {
        copied = true;
        setTimeout(() => (copied = false), 2000);
      } else toasts.show('ok', 'Link kopiert.');
    } catch {
      /* Zwischenablage nicht verfügbar – steht ja da */
    }
  }

  async function phone() {
    linkBusy = true;
    try {
      link = await api.post(`/devices/${issued.device.id}/download-link`);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      linkBusy = false;
    }
  }

  const until = (t: number) => new Date(t * 1000).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
</script>

<section class="card issued" aria-labelledby="issued-title">
  <h2 id="issued-title">
    {again ? `Zertifikat von „${issued.device.name}“` : `Zertifikat für „${issued.device.name}“ ist bereit`}
    <span class="muted who">· {issued.device.person_name}</span>
  </h2>
  {#if stored}
    <p class="muted small">
      Datei und Passwort sind verschlüsselt hinterlegt und lassen sich später unter <a href="#/devices">Geräte</a> erneut abrufen.
    </p>
  {:else}
    <Alert tone="warn" title="Nur jetzt verfügbar" text="Datei und Passwort werden nicht aufbewahrt – sie gibt es nur in diesem Fenster." />
  {/if}

  <div class="row">
    <Button icon="download" label="Zertifikat herunterladen (.p12)" onClick={download} />
    {#if stored}
      <Button variant="secondary" label={linkBusy ? 'Erzeugt …' : 'Aufs Handy (QR-Code)'} disabled={linkBusy} onClick={phone} />
    {/if}
  </div>

  {#if link}
    <div class="phone">
      <div class="qr" aria-label="QR-Code mit dem Download-Link">{@html link.qr_svg}</div>
      <div class="stack">
        <strong>Mit der Kamera des Handys scannen</strong>
        <span class="muted small">
          Lädt die .p12 direkt aufs Handy. Gilt bis {until(link.expires_at)} Uhr und für höchstens {link.uses} Abrufe; das Passwort steht nicht im Link.
        </span>
        <span class="mono small url">{link.url}</span>
        <div><Button variant="ghost" size="sm" icon="clipboard" label="Link kopieren" onClick={() => copy(link!.url, 'link')} /></div>
        <span class="muted small">
          Android: nach dem Download unter Einstellungen › Sicherheit › „Zertifikat installieren“ (für Browser) oder direkt in der App importieren, z. B. ntfy ›
          Einstellungen › Erweitert › Zertifikate verwalten. iPhone: Datei öffnen, dann Einstellungen › Profil geladen.
        </span>
      </div>
    </div>
  {/if}

  <div class="field">
    Passwort zum Importieren
    <div class="pw">
      <code class="mono">{issued.password}</code>
      <Button variant="secondary" size="sm" label={copied ? 'Kopiert' : 'Kopieren'} onClick={() => copy(issued.password, 'pw')} />
    </div>
    <span class="muted small">Datei und Passwort möglichst auf getrennten Wegen weitergeben.</span>
  </div>
  <div class="row">
    {#if again && onForget}
      <Button variant="ghost" size="sm" icon="trash" label="Hinterlegte Kopie löschen" onClick={onForget} />
    {/if}
    <span class="spacer"></span>
    <Button variant={downloaded || again ? 'primary' : 'secondary'} label="Fertig" onClick={onClose} />
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
  .who {
    font-weight: 400;
    font-size: 14px;
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
  .phone {
    display: flex;
    gap: 18px;
    align-items: flex-start;
    flex-wrap: wrap;
    padding: 14px;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    background: var(--bg);
  }
  .qr {
    width: 168px;
    height: 168px;
    flex-shrink: 0;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
  }
  .qr :global(svg) {
    width: 100%;
    height: 100%;
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1;
    min-width: 220px;
  }
  .url {
    overflow-wrap: anywhere;
  }
</style>
