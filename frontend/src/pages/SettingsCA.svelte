<script lang="ts">
  import { t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import IssuedCertificate from '../lib/components/IssuedCertificate.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import CAImportFields, { emptyImport, importBody, importReady, type CAImport } from '../lib/components/CAImportFields.svelte';
  import { api, downloadFile, formatDay, type AuthorityInfo, type CAStatus, type GeneralSettings, type IssuedDevice } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  let status = $state<CAStatus | null>(null);
  let error = $state('');

  let pass1 = $state('');
  let pass2 = $state('');
  let creating = $state(false);
  let created = $state<{ root_cert_pem: string; root_key_pem: string } | null>(null);
  // Einrichtung: neue CA erzeugen oder bestehende importieren
  let setupMode = $state<'generate' | 'import'>('generate');
  let setupImport = $state<CAImport>(emptyImport());
  let keySaved = $state(false);
  let keyDownloaded = $state(false);

  // Gäste verlängern ihr Gerät selbst
  let selfRenew = $state<{ enabled: boolean; days: number; url: string } | null>(null);
  // .p12 der Geräte aufbewahren
  let keep = $state<{ enabled: boolean; stored: number } | null>(null);

  async function setKeep(enabled: boolean) {
    if (!enabled && keep?.stored && !confirm(t('Alle {0} hinterlegten Zertifikate löschen? Die Geräte bleiben gültig, ihre .p12 lässt sich aber nicht mehr abrufen.', keep.stored))) {
      keep = { ...keep };
      return;
    }
    try {
      const g = await api.put<GeneralSettings>('/settings/general', { device_keep_p12: enabled });
      keep = { enabled: g.device_keep_p12, stored: g.device_p12_stored };
      toasts.show('ok', enabled ? t('Neue Zertifikate werden aufbewahrt.') : t('Aufbewahren aus, hinterlegte Kopien gelöscht.'));
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    }
  }
  let savingRenew = $state(false);

  async function loadRenew() {
    const g = await api.get<GeneralSettings>('/settings/general');
    selfRenew = { enabled: g.device_self_renew, days: g.device_self_renew_days, url: g.device_self_renew_url };
    keep = { enabled: g.device_keep_p12, stored: g.device_p12_stored };
  }

  async function saveRenew() {
    if (!selfRenew) return;
    savingRenew = true;
    try {
      const g = await api.put<GeneralSettings>('/settings/general', {
        device_self_renew: selfRenew.enabled,
        device_self_renew_days: Number(selfRenew.days)
      });
      selfRenew = { enabled: g.device_self_renew, days: g.device_self_renew_days, url: g.device_self_renew_url };
      toasts.show('ok', t('Gespeichert.'));
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      savingRenew = false;
    }
  }

  function copyRenewUrl() {
    if (selfRenew) navigator.clipboard?.writeText(selfRenew.url).then(() => toasts.show('ok', t('Link kopiert.')));
  }

  async function load() {
    loadRenew().catch(() => {});
    try {
      status = await api.get<CAStatus>('/ca');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function setup(e: SubmitEvent) {
    e.preventDefault();
    error = '';
    if (setupMode === 'import') {
      creating = true;
      try {
        status = await api.post<CAStatus>('/ca/import', importBody(setupImport));
        setupImport = emptyImport();
        toasts.show('ok', t('Bestehende CA übernommen.'));
      } catch (err) {
        error = err instanceof Error ? err.message : String(err);
      } finally {
        creating = false;
      }
      return;
    }
    if (pass1 !== pass2) {
      error = t('Die Passphrasen stimmen nicht überein.');
      return;
    }
    creating = true;
    try {
      created = await api.post('/ca/setup', { passphrase: pass1 });
      pass1 = pass2 = '';
      toasts.show('ok', t('Zertifizierungsstelle eingerichtet.'));
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      creating = false;
    }
  }

  function downloadKey() {
    if (!created) return;
    downloadFile('tesseract-root-ca.key', created.root_key_pem, 'application/x-pem-file');
    keyDownloaded = true;
  }

  function downloadRoot() {
    if (created) downloadFile('tesseract-root-ca.pem', created.root_cert_pem, 'application/x-pem-file');
    else window.location.href = '/api/ca/root.pem';
  }

  // Warnen, wenn die Seite verlassen wird, bevor der Root-Schlüssel gesichert ist
  $effect(() => {
    if (!created || keySaved) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  });

  async function finish() {
    created = null;
    await load();
  }

  const yearsLeft = (a: AuthorityInfo) =>
    Math.max(0, Math.round((new Date(a.not_after).getTime() - Date.now()) / (365.25 * 86400_000) * 10) / 10);

  // ---------- Phase 6: Wechsel des Zwischenzertifikats, Verlängern ----------
  let rootKey = $state('');
  let rootPass = $state('');
  let rotating = $state(false);
  let renewing = $state<number | null>(null);
  let renewed = $state<IssuedDevice | null>(null);

  async function readKey(e: Event) {
    const f = (e.currentTarget as HTMLInputElement).files?.[0];
    if (f) rootKey = await f.text();
  }

  async function rotate(e: Event) {
    e.preventDefault();
    rotating = true;
    try {
      status = await api.post<CAStatus>('/ca/rotate', { root_key_pem: rootKey, passphrase: rootPass });
      rootKey = rootPass = '';
      toasts.show('ok', t('Neues Zwischenzertifikat aktiv. Alte Geräte funktionieren weiter und lassen sich nach und nach verlängern.'), 10000);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      rotating = false;
    }
  }

  // ---------- Wechsel der Root-CA ----------
  let rootMode = $state<'generate' | 'import'>('generate');
  let rootImport = $state<CAImport>(emptyImport());
  let newPass1 = $state('');
  let newPass2 = $state('');
  let rootRotating = $state(false);
  let confirmRoot = $state(false);

  const rootReady = $derived(rootMode === 'generate' ? newPass1.length >= 12 && newPass1 === newPass2 : importReady(rootImport));

  async function rotateRoot() {
    confirmRoot = false;
    rootRotating = true;
    try {
      const body = rootMode === 'generate' ? { mode: 'generate', passphrase: newPass1 } : { mode: 'import', ...importBody(rootImport) };
      const r = await api.post<{ status: CAStatus; root_cert_pem: string | null; root_key_pem: string | null }>('/ca/rotate-root', body);
      status = r.status;
      newPass1 = newPass2 = '';
      rootImport = emptyImport();
      if (r.root_cert_pem && r.root_key_pem) {
        // neuen Root-Schlüssel sichern lassen – wie bei der Einrichtung
        created = { root_cert_pem: r.root_cert_pem, root_key_pem: r.root_key_pem };
        keySaved = keyDownloaded = false;
      }
      toasts.show('ok', t('Neue Root-CA aktiv. Alte Geräte funktionieren weiter, Nodes erneuern ihr Zertifikat selbst.'), 10000);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 12000);
    } finally {
      rootRotating = false;
    }
  }

  async function renew(id: number) {
    renewing = id;
    try {
      renewed = await api.post<IssuedDevice>(`/devices/${id}/renew`, { days: 365 });
      status = await api.get<CAStatus>('/ca');
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      renewing = null;
    }
  }
</script>

<AppShell active="settings">
  <PageHeader title={t('Einstellungen')} subtitle={t('Die eigene CA stellt Geräte-, Admin- und Node-Zertifikate aus.')} />
  <SettingsTabs current="#/settings-ca" />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if created}
    <section class="card setup done" aria-labelledby="done-title">
      <h2 id="done-title">{t('Root-Schlüssel jetzt sichern')}</h2>
      {#if status?.configured}
        <p class="muted">{t('Die neue Root-CA ist aktiv. Geräte bekommen beim Verlängern das neue Root-Zertifikat mit.')}</p>
      {/if}
      <p class="muted">
        {t('Der Root-Schlüssel ist mit deiner Passphrase verschlüsselt. Er wird nur gebraucht, um später ein neues Zwischenzertifikat zu signieren – bewahre ihn offline auf (z. B. USB-Stick im Schrank).')}
        <strong>{t('Tesseract speichert ihn nicht.')}</strong>
      </p>
      <div class="row">
        <Button icon="download" label={t('Root-Schlüssel herunterladen')} onClick={downloadKey} />
        <Button variant="secondary" icon="download" label={t('Root-Zertifikat (.pem)')} onClick={downloadRoot} />
      </div>
      <label class="check">
        <input type="checkbox" bind:checked={keySaved} disabled={!keyDownloaded} />
        {t('Ich habe den Root-Schlüssel und die Passphrase sicher gespeichert.')}
      </label>
      <div class="row"><Button label={t('Fertig')} disabled={!keySaved} onClick={finish} /></div>
    </section>
  {:else if status && !status.configured}
    <form class="card setup" onsubmit={setup} aria-labelledby="setup-title">
      <h2 id="setup-title">{t('Zertifizierungsstelle einrichten')}</h2>
      <div class="modes" role="radiogroup" aria-label={t('Art der Einrichtung')}>
        <label class="check"><input type="radio" name="setup-mode" value="generate" bind:group={setupMode} /> {t('Neue CA erzeugen')}</label>
        <label class="check"><input type="radio" name="setup-mode" value="import" bind:group={setupMode} /> {t('Bestehende CA importieren')}</label>
      </div>
      {#if setupMode === 'generate'}
        <ol class="steps muted">
          <li>{t('Tesseract erzeugt eine')} <strong>{t('Root-CA')}</strong> {t('(ECDSA P-384, 10 Jahre) und ein')} <strong>{t('Geräte-Zwischenzertifikat')}</strong> {t('(3 Jahre).')}</li>
          <li>{t('Den Root-Schlüssel lädst du einmal herunter – verschlüsselt mit dieser Passphrase. Danach vergisst Tesseract ihn.')}</li>
          <li>{t('Das Zwischenzertifikat bleibt verschlüsselt auf dem Controller und stellt die Gerätezertifikate aus.')}</li>
        </ol>
        <div class="grid2">
          <label class="field">
            {t('Passphrase für den Root-Schlüssel (mind. 12 Zeichen)')}
            <input class="input" type="password" autocomplete="new-password" minlength="12" required bind:value={pass1} />
          </label>
          <label class="field">
            {t('Passphrase wiederholen')}
            <input class="input" type="password" autocomplete="new-password" minlength="12" required bind:value={pass2} />
          </label>
        </div>
        <div class="row">
          <Button type="submit" label={creating ? t('Erzeugt …') : t('CA erzeugen')} disabled={creating} />
        </div>
      {:else}
        <p class="muted small">
          {t('Für eine vorhandene PKI (z. B. die der Firma oder eine bisherige Homelab-CA). Geräte, die dieser CA schon vertrauen, brauchen kein neues Root-Zertifikat. Schlüssel liegen danach nur verschlüsselt auf dem Controller – ein Root-Schlüssel gar nicht.')}
        </p>
        <CAImportFields bind:value={setupImport} id="setup" />
        <div class="row">
          <Button type="submit" label={creating ? t('Prüft …') : t('CA importieren')} disabled={creating || !importReady(setupImport)} />
        </div>
      {/if}
    </form>
  {:else if status}
    {#if status.devices_beyond_intermediate > 0 && status.intermediate}
      <Alert
        tone="warn"
        title={t('{0} Gerät(e) „unbegrenzt“ gültig', status.devices_beyond_intermediate)}
        text={t('Sie funktionieren nur bis {0} – solange das Zwischenzertifikat gilt.', formatDay(status.intermediate.not_after))}
      />
    {/if}

    <div class="chain" aria-label={t('Aufbau der CA')}>
      {#each [status.root, status.intermediate] as a, i (i)}
        {#if a}
          <section class="card">
            <div class="row">
              <span class="ca-icon"><Icon name="lock" size={16} strokeWidth={2} /></span>
              <h2 class="card-title">{a.kind === 'root' ? t('Root-Zertifikat') : t('Geräte-Zwischenzertifikat')}</h2>
              <span class="spacer"></span>
              <StatusPill tone="ok" label={t('aktiv')} />
            </div>
            <dl>
              <dt>{t('Name')}</dt><dd>{a.subject}</dd>
              <dt>{t('Gültig')}</dt><dd>{t('{0} – {1} · noch {2} Jahre', formatDay(a.not_before), formatDay(a.not_after), yearsLeft(a))}</dd>
              <dt>{t('Schlüssel')}</dt>
              <dd>{a.key_on_controller ? t('verschlüsselt auf dem Controller') : t('offline – nicht auf dem Controller')}</dd>
              <dt>{t('Fingerabdruck')}</dt><dd class="mono fp">{a.fingerprint}</dd>
            </dl>
          </section>
        {/if}
      {/each}
    </div>

    <section class="card">
      <h2>{t('Ausgestellte Gerätezertifikate')}</h2>
      <p class="muted">
        {t('{0} Geräte · {1} aktiv · {2} gesperrt ·', status.devices_total, status.devices_active, status.devices_revoked)} <a href="#/devices">{t('Geräte ansehen')}</a>
      </p>
      <div class="row">
        <Button variant="secondary" icon="download" label={t('Root-Zertifikat herunterladen')} onClick={downloadRoot} />
      </div>
    </section>

    {#if keep}
      <section class="card" aria-labelledby="keep-title">
        <h2 id="keep-title">{t('Zertifikate aufbewahren')}</h2>
        <Toggle
          label={t('Zum erneuten Abruf aufbewahren')}
          description={t('Die .p12 neuer und verlängerter Geräte samt Passwort wird verschlüsselt gespeichert. So lässt sie sich unter Geräte später erneut herunterladen oder per QR-Code aufs Handy holen. Aus = Datei und Passwort gibt es nur einmal beim Ausstellen.')}
          checked={keep.enabled}
          onChange={(v) => setKeep(v)}
        />
        <p class="muted small">
          {t('{0} {1} eine hinterlegte Kopie. Gesperrte Geräte verlieren sie sofort. Zum Entschlüsseln dient der Schlüssel des Controllers (', keep.stored, keep.stored === 1 ? t('Gerät hat') : t('Geräte haben'))}<span class="mono">secret.key</span>{t(') – wer ihn und die Datenbank hat, kommt an die Zertifikate.')}
        </p>
      </section>
    {/if}

    {#if selfRenew}
      <section class="card" aria-labelledby="renew-title">
        <h2 id="renew-title">{t('Gäste verlängern selbst')}</h2>
        <Toggle
          label={t('Selbst verlängern erlauben')}
          description={t('Gäste öffnen den Link auf dem Gerät und bekommen ein neues Zertifikat – ohne neue Einladung und ohne Freigabe. Ausweis ist das noch gültige Zertifikat; gesperrte oder abgelaufene Geräte gehen nicht.')}
          bind:checked={selfRenew.enabled}
        />
        {#if selfRenew.enabled}
          <div class="row renew-row">
            <label class="field days">
              <span class="muted small">{t('Ab wie vielen Tagen vor Ablauf')}</span>
              <input class="input" type="number" min="1" max="365" bind:value={selfRenew.days} />
            </label>
            <span class="mono small link">{selfRenew.url}</span>
            <Button variant="ghost" size="sm" icon="clipboard" label={t('Link kopieren')} onClick={copyRenewUrl} />
          </div>
          <p class="muted small">
            {t('Den Link bekommen Gäste nach der Registrierung angezeigt. Nach einem Wechsel des Zwischenzertifikats geht das Verlängern für alte Geräte sofort.')}
          </p>
        {/if}
        <div class="row">
          <Button variant="secondary" size="sm" icon="check" label={savingRenew ? t('Speichert …') : t('Speichern')} onClick={saveRenew} disabled={savingRenew} />
        </div>
      </section>
    {/if}

    {#each status.previous as prev (prev.authority.fingerprint)}
      <section class="card retiring">
        <div class="row">
          <h2 class="card-title">{t('Altes Zwischenzertifikat – noch vertraut')}</h2>
          <span class="spacer"></span>
          <StatusPill tone="warn" label={t('{0} Gerät(e)', prev.devices.length)} />
        </div>
        <p class="muted small">
          {t('{0} · gültig bis {1}. Caddy vertraut ihm, bis alle Geräte unten verlängert und alle Nodes erneuert sind – danach fällt es weg.', prev.authority.subject, formatDay(prev.authority.not_after))}
          {#if prev.nodes.length}
            {t('Nodes ({0}) erneuern ihr Zertifikat beim nächsten Kontakt selbst.', prev.nodes.map((n) => n.name).join(', '))}
          {/if}
        </p>
        <ul class="devlist">
          {#each prev.devices as d (d.id)}
            <li>
              <span>{d.person} · {d.name}</span>
              <Button variant="secondary" size="sm" label={renewing === d.id ? t('Verlängert …') : t('Verlängern')} disabled={renewing !== null} onClick={() => renew(d.id)} />
            </li>
          {/each}
        </ul>
      </section>
    {/each}

    <form class="card" onsubmit={rotate} aria-labelledby="rot-title">
      <h2 id="rot-title">{t('Wechsel auf ein neues Zwischenzertifikat')}</h2>
      <p class="muted small">
        {t('Dafür wird der Root-Schlüssel gebraucht, den du bei der Einrichtung gesichert hast (Datei')} <span class="mono">tesseract-root-key.pem</span>{t(', mit Passphrase verschlüsselt). Er wird nur für diesen Vorgang entschlüsselt und nicht gespeichert. Bestehende Geräte funktionieren weiter; verlängerte und neue bekommen ihr Zertifikat vom neuen Zwischenzertifikat. Empfohlen spätestens 90 Tage vor Ablauf.')}
      </p>
      <label class="field col">
        <span class="label">{t('Root-Schlüssel (Datei wählen oder Inhalt einfügen)')}</span>
        <input class="input" type="file" accept=".pem,.key,.txt" onchange={readKey} />
        <textarea class="input mono keyarea" rows="4" bind:value={rootKey} placeholder="-----BEGIN ENCRYPTED PRIVATE KEY-----"></textarea>
      </label>
      <label class="field col">
        <span class="label">{t('Passphrase des Root-Schlüssels')}</span>
        <input class="input" type="password" autocomplete="off" bind:value={rootPass} />
      </label>
      <div class="row">
        <Button type="submit" label={rotating ? t('Wechselt …') : t('Wechsel durchführen')} disabled={rotating || !rootKey.trim() || !rootPass} />
      </div>
    </form>

    <section class="card" aria-labelledby="root-title">
      <h2 id="root-title">{t('Wechsel der Root-CA')}</h2>
      <p class="muted small">
        {t('Neue Root samt neuem Zwischenzertifikat – z. B. wenn die Root bald abläuft, der Root-Schlüssel verloren oder kompromittiert ist, oder um auf eine vorhandene PKI umzuziehen. Bestehende Geräte funktionieren weiter, bis sie verlängert sind; Nodes erneuern ihr Zertifikat selbst. Wo das alte Root-Zertifikat als vertrauenswürdig installiert ist, muss das neue hinzu.')}
        {#if status.root}{t('Aktuelle Root gültig bis {0}.', formatDay(status.root.not_after))}{/if}
      </p>
      <div class="modes" role="radiogroup" aria-label={t('Art des Wechsels')}>
        <label class="check"><input type="radio" name="root-mode" value="generate" bind:group={rootMode} /> {t('Neue Root erzeugen')}</label>
        <label class="check"><input type="radio" name="root-mode" value="import" bind:group={rootMode} /> {t('Bestehende Root importieren')}</label>
      </div>
      {#if rootMode === 'generate'}
        <div class="grid2">
          <label class="field">
            {t('Passphrase für den neuen Root-Schlüssel (mind. 12 Zeichen)')}
            <input class="input" type="password" autocomplete="new-password" minlength="12" bind:value={newPass1} />
          </label>
          <label class="field">
            {t('Passphrase wiederholen')}
            <input class="input" type="password" autocomplete="new-password" minlength="12" bind:value={newPass2} />
          </label>
        </div>
      {:else}
        <CAImportFields bind:value={rootImport} id="root" />
      {/if}
      <div class="row">
        <Button variant="secondary" label={rootRotating ? t('Wechselt …') : t('Root wechseln …')} disabled={rootRotating || !rootReady} onClick={() => (confirmRoot = true)} />
      </div>
    </section>

    {#if confirmRoot}
      <ConfirmDialog
        title={t('Root-CA wechseln?')}
        text={t('Neue und verlängerte Geräte bekommen ihr Zertifikat ab sofort von der neuen Root. Das alte Zwischenzertifikat bleibt vertraut, solange Geräte oder Nodes daran hängen. Zurück geht es nur mit einem weiteren Wechsel.')}
        word="wechseln"
        confirmLabel={t('Root wechseln')}
        onConfirm={rotateRoot}
        onCancel={() => (confirmRoot = false)}
      />
    {/if}
    {#if renewed}<IssuedCertificate issued={renewed} onClose={() => (renewed = null)} />{/if}
  {/if}
</AppShell>

<style>
  .modes {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 20px;
  }
  .retiring {
    border-color: rgba(229, 164, 67, 0.45);
  }
  .devlist {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .devlist li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .col {
    flex-direction: column;
    gap: 6px;
  }
  .label {
    font-size: 13px;
    color: var(--text-muted);
  }
  .keyarea {
    font-size: 11px;
    resize: vertical;
  }
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .setup {
    max-width: 760px;
  }
  .done {
    border-color: var(--warn);
  }
  .steps {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    line-height: 1.5;
  }
  .steps strong,
  p strong {
    color: var(--text);
  }
  p {
    margin: 0;
    line-height: 1.55;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }
  .chain {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
  }
  .ca-icon {
    width: 30px;
    height: 30px;
    border-radius: var(--radius);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 124, 246, 0.18);
    color: var(--accent-text);
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px 16px;
    font-size: 13px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .fp {
    font-size: 11px;
  }
  .small {
    font-size: 12px;
  }
  .renew-row {
    align-items: flex-end;
    flex-wrap: wrap;
  }
  .days {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-width: 200px;
  }
  .link {
    overflow-wrap: anywhere;
    padding-bottom: 10px;
  }
</style>
