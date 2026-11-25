<script lang="ts">
  import { locale, t } from '../i18n';
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
      } else toasts.show('ok', t('Link kopiert.'));
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

  const until = (sec: number) => new Date(sec * 1000).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
</script>

<section class="card issued" aria-labelledby="issued-title">
  <h2 id="issued-title">
    {again ? t('Zertifikat von „{0}“', issued.device.name) : t('Zertifikat für „{0}“ ist bereit', issued.device.name)}
    <span class="muted who">· {issued.device.person_name}</span>
  </h2>
  {#if stored}
    <p class="muted small">
      {t('Datei und Passwort sind verschlüsselt hinterlegt und lassen sich später unter')} <a href="#/devices">{t('Geräte')}</a> {t('erneut abrufen.')}
    </p>
  {:else}
    <Alert tone="warn" title={t('Nur jetzt verfügbar')} text={t('Datei und Passwort werden nicht aufbewahrt – sie gibt es nur in diesem Fenster.')} />
  {/if}

  <div class="row">
    <Button icon="download" label={t('Zertifikat herunterladen (.p12)')} onClick={download} />
    {#if stored}
      <Button variant="secondary" label={linkBusy ? t('Erzeugt …') : t('Aufs Handy (QR-Code)')} disabled={linkBusy} onClick={phone} />
    {/if}
  </div>

  {#if link}
    <div class="phone">
      <div class="qr" aria-label={t('QR-Code mit dem Download-Link')}>{@html link.qr_svg}</div>
      <div class="stack">
        <strong>{t('Mit der Kamera des Handys scannen')}</strong>
        <span class="muted small">
          {t('Lädt die .p12 direkt aufs Handy. Gilt bis {0} Uhr und für höchstens {1} Abrufe; das Passwort steht nicht im Link.', until(link.expires_at), link.uses)}
        </span>
        <span class="mono small url">{link.url}</span>
        <div><Button variant="ghost" size="sm" icon="clipboard" label={t('Link kopieren')} onClick={() => copy(link!.url, 'link')} /></div>
        <span class="muted small">
          {t('Android: nach dem Download unter Einstellungen › Sicherheit › „Zertifikat installieren“ (für Browser) oder direkt in der App importieren, z. B. ntfy › Einstellungen › Erweitert › Zertifikate verwalten. iPhone: Datei öffnen, dann Einstellungen › Profil geladen.')}
        </span>
      </div>
    </div>
  {/if}

  <div class="field">
    {t('Passwort zum Importieren')}
    <div class="pw">
      <code class="mono">{issued.password}</code>
      <Button variant="secondary" size="sm" label={copied ? t('Kopiert') : t('Kopieren')} onClick={() => copy(issued.password, 'pw')} />
    </div>
    <span class="muted small">{t('Datei und Passwort möglichst auf getrennten Wegen weitergeben.')}</span>
  </div>
  <div class="row">
    {#if again && onForget}
      <Button variant="ghost" size="sm" icon="trash" label={t('Hinterlegte Kopie löschen')} onClick={onForget} />
    {/if}
    <span class="spacer"></span>
    <Button variant={downloaded || again ? 'primary' : 'secondary'} label={t('Fertig')} onClick={onClose} />
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
    width: 200px;
    height: 200px;
    flex-shrink: 0;
    border-radius: 8px;
    background: #fff;
  }
  .qr :global(svg) {
    display: block;
    width: 100%;
    height: 100%;
    /* Module scharf, ohne Kantenglättung – sonst lesen manche Kameras schlechter */
    shape-rendering: crispEdges;
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
