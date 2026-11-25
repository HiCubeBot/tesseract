<script lang="ts">
  import { t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import { api, fetchRetry, formatAgo, formatBytes, formatDate } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  interface Result {
    at: string;
    ok: boolean;
    name: string | null;
    size?: number;
    targets?: string[];
    error: string | null;
  }

  interface BackupConfig {
    schedule: 'off' | 'hourly' | 'daily' | 'weekly';
    hour: number;
    weekday: number;
    timezone: string;
    keep: number;
    include_logs: boolean;
    passphrase_set: boolean;
    local: { enabled: boolean; path: string };
    s3: { enabled: boolean; endpoint: string; bucket: string; region: string; prefix: string; access_key: string; secret_key_set: boolean };
    restic: { enabled: boolean; repository: string; password_set: boolean; env_set: boolean };
    last: Result | null;
    last_test: Result | null;
    next: string | null;
    git: {
      enabled: boolean;
      url: string;
      branch: string;
      auth: 'none' | 'token' | 'ssh';
      username: string;
      token_set: boolean;
      ssh_key_set: boolean;
      last: { at: string; ok: boolean; commit: string | null; changed: boolean; error: string | null } | null;
    };
  }

  interface Item {
    target: 'local' | 's3' | 'restic';
    name: string | null;
    size: number;
    error?: string;
  }

  const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];
  const TARGETS = { local: t('Lokal'), s3: 'S3', restic: t('Restic') };

  let cfg = $state<BackupConfig | null>(null);
  let items = $state<Item[]>([]);
  let error = $state('');
  let saving = $state(false);
  let running = $state(false);
  let busy = $state<string | null>(null);
  let phrase = $state('');
  let phrase2 = $state('');
  let s3Secret = $state('');
  let resticPassword = $state('');
  let resticEnv = $state('');
  let resticChecking = $state(false);
  let gitToken = $state('');
  let gitKey = $state('');
  let mirroring = $state(false);
  let confirm = $state<Item | null>(null);
  let upload = $state<{ file: File | null; phrase: string }>({ file: null, phrase: '' });
  let confirmUpload = $state(false);

  async function load() {
    try {
      [cfg, items] = await Promise.all([api.get<BackupConfig>('/backups/config'), api.get<Item[]>('/backups')]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function checkRestic() {
    resticChecking = true;
    try {
      const r = await api.post<{ ok: boolean; error: string | null; created: boolean; snapshots: number }>('/backups/restic/check');
      if (!r.ok) toasts.show('bad', r.error ?? 'Fehler', 12000);
      else
        toasts.show(
          'ok',
          r.created ? t('Repository angelegt – bereit für Sicherungen.') : t('Verbindung steht · {0} Tesseract-Snapshot(s) im Repository.', r.snapshots)
        );
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      resticChecking = false;
    }
  }

  async function save() {
    if (!cfg) return;
    if (phrase && phrase !== phrase2) {
      toasts.show('bad', t('Die Passphrasen stimmen nicht überein.'));
      return;
    }
    saving = true;
    try {
      cfg = await api.put<BackupConfig>('/backups/config', {
        schedule: cfg.schedule,
        hour: Number(cfg.hour),
        weekday: Number(cfg.weekday),
        timezone: cfg.timezone,
        keep: Number(cfg.keep),
        include_logs: cfg.include_logs,
        local: cfg.local.enabled,
        s3: { ...cfg.s3, secret_key: s3Secret || null },
        restic: {
          enabled: cfg.restic.enabled,
          repository: cfg.restic.repository,
          password: resticPassword || null,
          env: resticEnv || null
        },
        git: {
          enabled: cfg.git.enabled,
          url: cfg.git.url,
          branch: cfg.git.branch,
          auth: cfg.git.auth,
          username: cfg.git.username,
          token: gitToken || null,
          ssh_key: gitKey || null
        },
        ...(phrase ? { passphrase: phrase } : {})
      });
      phrase = phrase2 = s3Secret = resticPassword = resticEnv = gitToken = gitKey = '';
      toasts.show('ok', t('Gespeichert.'));
      items = await api.get<Item[]>('/backups');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  async function mirrorNow() {
    if (!cfg) return;
    mirroring = true;
    try {
      const r = await api.post<NonNullable<BackupConfig['git']['last']>>('/backups/git/sync');
      cfg.git.last = r;
      if (r.ok) toasts.show('ok', r.changed ? t('Gespiegelt (Commit {0}).', r.commit) : t('Keine Änderung – Spiegel ist aktuell.'));
      else toasts.show('bad', t('Git-Spiegel: {0}', r.error), 10000);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      mirroring = false;
    }
  }

  async function backupNow() {
    running = true;
    try {
      const r = await api.post<Result>('/backups');
      if (r.ok) toasts.show('ok', t('Gesichert: {0} ({1}) → {2}', r.name, formatBytes(r.size ?? 0), r.targets?.map((x) => TARGETS[x as 'local']).join(', ')));
      else toasts.show('warn', t('Teilweise gesichert: {0}', r.error), 12000);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 12000);
    } finally {
      running = false;
      await load();
    }
  }

  async function test(it: Item) {
    busy = t('test-{0}-{1}', it.target, it.name);
    try {
      const r = await api.post<Result & { manifest: { counts: Record<string, number> } | null }>('/backups/test', { target: it.target, name: it.name });
      if (r.ok) {
        const c = r.manifest?.counts ?? {};
        toasts.show('ok', t('Lesbar und intakt: {0} Hosts, {1} Personen, {2} Geräte, {3} Nodes.', c.hosts ?? 0, c.persons ?? 0, c.devices ?? 0, c.nodes ?? 0), 8000);
      } else toasts.show('bad', t('Test fehlgeschlagen: {0}', r.error), 12000);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      busy = null;
      await load();
    }
  }

  function afterRestore(r: { apply_errors: string[] }) {
    toasts.show(
      r.apply_errors.length ? 'warn' : 'ok',
      r.apply_errors.length ? t('Wiederhergestellt, aber nicht übertragen: {0}', r.apply_errors.join('; ')) : t('Wiederhergestellt und an alle Nodes übertragen. Bitte neu anmelden.'),
      12000
    );
    setTimeout(() => location.reload(), 2500);
  }

  async function restore() {
    const it = confirm;
    confirm = null;
    if (!it) return;
    busy = t('restore-{0}-{1}', it.target, it.name);
    try {
      afterRestore(await api.post('/backups/restore', { target: it.target, name: it.name }));
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 12000);
    } finally {
      busy = null;
    }
  }

  async function restoreUpload() {
    confirmUpload = false;
    if (!upload.file) return;
    busy = 'upload';
    try {
      const res = await fetchRetry('/api/backups/restore/upload', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/octet-stream', 'X-Backup-Passphrase': upload.phrase },
        body: upload.file
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail ?? t('Fehler {0}', res.status));
      afterRestore(data);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 12000);
    } finally {
      busy = null;
    }
  }

  const ago = (r: Result | null) => (r ? formatAgo(r.at) : t('noch nie'));
  const testOld = $derived(!cfg?.last_test || Date.now() - new Date(cfg.last_test.at).getTime() > 31 * 86400e3);
</script>

<AppShell active="settings">
  <PageHeader
    title={t('Einstellungen')}
    subtitle={t('Sicherungen des Controllers. Nodes brauchen keine – sie bekommen ihre Config vom Controller.')}
    primaryLabel={running ? t('Sichert …') : t('Jetzt sichern')}
    primaryIcon="download"
    onPrimary={() => !running && backupNow()}
    secondaryLabel={saving ? t('Speichert …') : t('Speichern')}
    onSecondary={save}
  />
  <SettingsTabs current="#/settings-backup" />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if cfg}
    {#if !cfg.passphrase_set}
      <Alert tone="warn" title={t('Noch keine Passphrase')} text={t('Ohne Passphrase gibt es keine Sicherungen. Unten festlegen und gut aufbewahren – ohne sie ist keine Sicherung lesbar.')} />
    {/if}

    <div class="stats">
      <StatCard
        label={t('Letzte Sicherung')}
        value={ago(cfg.last)}
        sub={cfg.last ? (cfg.last.ok ? t('erfolgreich · {0} · {1} Ziel(e)', formatBytes(cfg.last.size ?? 0), cfg.last.targets?.length) : (cfg.last.error ?? 'fehlgeschlagen')) : '–'}
        tone={cfg.last ? (cfg.last.ok ? 'ok' : 'bad') : 'neutral'}
        subTone={cfg.last && !cfg.last.ok ? 'bad' : 'muted'}
      />
      <StatCard label={t('Nächste Sicherung')} value={cfg.next ? formatDate(cfg.next) : '–'} sub={{ off: t('kein Zeitplan'), hourly: t('stündlich'), daily: t('täglich'), weekly: t('wöchentlich') }[cfg.schedule]} tone="neutral" />
      <StatCard
        label={t('Letzter Wiederherstellungstest')}
        value={ago(cfg.last_test)}
        sub={cfg.last_test && !cfg.last_test.ok ? (cfg.last_test.error ?? 'fehlgeschlagen') : t('monatlich empfohlen · in der Liste „Testen“')}
        tone={cfg.last_test && !cfg.last_test.ok ? 'bad' : testOld ? 'warn' : 'ok'}
        subTone={cfg.last_test && !cfg.last_test.ok ? 'bad' : testOld ? 'warn' : 'muted'}
      />
    </div>

    <div class="cols">
      <section class="card" aria-labelledby="plan-title">
        <h2 id="plan-title">{t('Zeitplan & Inhalt')}</h2>
        <div class="grid">
          <label class="field col"><span class="label">{t('Zeitplan')}</span>
            <select class="input" bind:value={cfg.schedule}>
              <option value="off">{t('aus (nur von Hand)')}</option>
              <option value="hourly">{t('stündlich')}</option>
              <option value="daily">{t('täglich')}</option>
              <option value="weekly">{t('wöchentlich')}</option>
            </select>
          </label>
          {#if cfg.schedule === 'weekly'}
            <label class="field col"><span class="label">{t('Tag')}</span>
              <select class="input" bind:value={cfg.weekday}>{#each WEEKDAYS as d, i (i)}<option value={i}>{d}</option>{/each}</select>
            </label>
          {/if}
          {#if cfg.schedule === 'daily' || cfg.schedule === 'weekly'}
            <label class="field col"><span class="label">{t('Uhrzeit')}</span>
              <select class="input" bind:value={cfg.hour}>{#each Array(24) as _, h (h)}<option value={h}>{String(h).padStart(2, '0')}:00</option>{/each}</select>
            </label>
          {/if}
          <label class="field col"><span class="label">{t('Aufbewahren')}</span>
            <select class="input" bind:value={cfg.keep}>{#each [7, 14, 30, 60, 90] as k (k)}<option value={k}>{t('{0} Sicherungen', k)}</option>{/each}</select>
          </label>
        </div>
        <ul class="parts">
          <li>{t('✓ Hosts, Personen, Geräte, Zugriffe, Nodes, Einstellungen')}</li>
          <li>{t('✓ Verlauf aller Hosts und Audit-Log mit Prüfsummen-Kette')}</li>
          <li>{t('✓ Schlüssel der Zwischenzertifikate und Hauptschlüssel (verschlüsselt)')}</li>
        </ul>
        <Toggle label={t('Zugriffs-Logs mitsichern')} description={t('können groß werden; Statistik fängt nach dem Zurückspielen sonst neu an')} bind:checked={cfg.include_logs} />
        <p class="muted small">{t('Der Root-Schlüssel ist nie enthalten – er liegt offline. Alles wird mit deiner Passphrase verschlüsselt (AES-256-GCM, Schlüssel per scrypt).')}</p>
        <div class="grid">
          <label class="field col"><span class="label">{t('Passphrase {0}', cfg.passphrase_set ? '(gesetzt – leer lassen = behalten)' : '')}</span>
            <input class="input" type="password" autocomplete="new-password" bind:value={phrase} placeholder={t('mind. 12 Zeichen')} />
          </label>
          <label class="field col"><span class="label">{t('Wiederholen')}</span>
            <input class="input" type="password" autocomplete="new-password" bind:value={phrase2} />
          </label>
        </div>
      </section>

      <section class="card" aria-labelledby="targets-title">
        <h2 id="targets-title">{t('Ziele')}</h2>
        <div class="target">
          <Toggle label={t('Lokal')} description={t('auf dem Controller selbst – schützt nicht vor Hardware-Ausfall')} bind:checked={cfg.local.enabled} />
          <span class="mono small">{cfg.local.path}</span>
        </div>
        <div class="target">
          <Toggle label={t('S3-kompatibel')} description={t('z. B. MinIO auf dem NAS, Garage oder ein externer Anbieter')} bind:checked={cfg.s3.enabled} />
          {#if cfg.s3.enabled}
            <div class="grid">
              <label class="field col"><span class="label">{t('Adresse')}</span><input class="input mono" bind:value={cfg.s3.endpoint} placeholder="https://minio.beispiel.de" /></label>
              <label class="field col"><span class="label">{t('Bucket')}</span><input class="input mono" bind:value={cfg.s3.bucket} /></label>
              <label class="field col"><span class="label">{t('Region')}</span><input class="input mono" bind:value={cfg.s3.region} /></label>
              <label class="field col"><span class="label">{t('Ordner (Präfix)')}</span><input class="input mono" bind:value={cfg.s3.prefix} /></label>
              <label class="field col"><span class="label">{t('Access Key')}</span><input class="input mono" bind:value={cfg.s3.access_key} autocomplete="off" /></label>
              <label class="field col"><span class="label">{t('Secret Key{0}', cfg.s3.secret_key_set ? t(' · gesetzt') : '')}</span><input class="input mono" type="password" bind:value={s3Secret} placeholder={cfg.s3.secret_key_set ? t('unverändert lassen') : ''} autocomplete="off" /></label>
            </div>
          {/if}
        </div>
        <div class="target">
          <Toggle
            label={t('Restic-Repository')}
            description={t('lokal, SFTP, S3, B2, REST-Server, rclone … – Restic verschlüsselt das Repository zusätzlich und räumt alte Snapshots selbst auf')}
            bind:checked={cfg.restic.enabled}
          />
          {#if cfg.restic.enabled}
            <div class="grid">
              <label class="field col wide"
                ><span class="label">{t('Repository')}</span><input
                  class="input mono"
                  bind:value={cfg.restic.repository}
                  placeholder={t('sftp:backup@nas:/restic/tesseract · rest:https://nas:8000/tesseract · s3:https://minio/bucket')}
                /></label
              >
              <label class="field col"
                ><span class="label">{t('Passwort des Repositorys{0}', cfg.restic.password_set ? t(' · gesetzt') : '')}</span><input
                  class="input mono"
                  type="password"
                  bind:value={resticPassword}
                  placeholder={cfg.restic.password_set ? t('unverändert lassen') : ''}
                  autocomplete="off"
                /></label
              >
              <label class="field col wide"
                ><span class="label">{t('Zugangsdaten als Umgebung (KEY=VALUE je Zeile, optional){0}', cfg.restic.env_set ? t(' · gesetzt') : '')}</span
                ><textarea
                  class="input mono area"
                  rows="3"
                  bind:value={resticEnv}
                  placeholder={cfg.restic.env_set ? t('unverändert lassen') : 'AWS_ACCESS_KEY_ID=…\nAWS_SECRET_ACCESS_KEY=…'}
                  autocomplete="off"
                  spellcheck="false"
                ></textarea></label
              >
            </div>
            <div class="row">
              <Button
                variant="secondary"
                size="sm"
                icon="refresh"
                label={resticChecking ? t('Prüft …') : t('Verbindung prüfen')}
                disabled={resticChecking || !cfg.restic.repository}
                onClick={checkRestic}
              />
              <span class="muted small">{t('Erst speichern. Fehlt das Repository, wird es angelegt.')}</span>
            </div>
          {/if}
        </div>
        <div class="target">
          <Toggle
            label={t('Git-Spiegel')}
            description={t('Hosts, Caddy-Configs und Einstellungen lesbar in einem Git-Repository – jede Änderung ein Commit, ohne Schlüssel und Personen')}
            bind:checked={cfg.git.enabled}
          />
          {#if cfg.git.enabled}
            <div class="grid">
              <label class="field col wide"><span class="label">{t('Repository')}</span><input class="input mono" bind:value={cfg.git.url} placeholder="https://git.beispiel.de/homelab/tesseract-config.git" /></label>
              <label class="field col"><span class="label">{t('Branch')}</span><input class="input mono" bind:value={cfg.git.branch} /></label>
              <label class="field col"><span class="label">{t('Anmeldung')}</span>
                <select class="input" bind:value={cfg.git.auth}>
                  <option value="token">{t('Token (HTTPS)')}</option>
                  <option value="ssh">{t('SSH-Schlüssel (Deploy-Key)')}</option>
                  <option value="none">{t('keine')}</option>
                </select>
              </label>
              {#if cfg.git.auth === 'token'}
                <label class="field col"><span class="label">{t('Benutzer (optional)')}</span><input class="input mono" bind:value={cfg.git.username} autocomplete="off" placeholder={t('git')} /></label>
                <label class="field col"><span class="label">{t('Token{0}', cfg.git.token_set ? t(' · gesetzt') : '')}</span><input class="input mono" type="password" bind:value={gitToken} placeholder={cfg.git.token_set ? t('unverändert lassen') : t('mit Schreibrecht')} autocomplete="off" /></label>
              {:else if cfg.git.auth === 'ssh'}
                <label class="field col wide"><span class="label">{t('Privater Schlüssel{0}', cfg.git.ssh_key_set ? t(' · gesetzt') : '')}</span>
                  <textarea class="input mono key" bind:value={gitKey} placeholder={cfg.git.ssh_key_set ? t('unverändert lassen') : '-----BEGIN OPENSSH PRIVATE KEY-----'} autocomplete="off" spellcheck="false"></textarea>
                </label>
              {/if}
            </div>
            <div class="row">
              <Button variant="secondary" size="sm" icon="refresh" label={mirroring ? t('Spiegelt …') : t('Jetzt spiegeln')} onClick={mirrorNow} disabled={mirroring || !cfg.git.url} />
              <span class="muted small" class:bad={cfg.git.last && !cfg.git.last.ok}>
                {#if cfg.git.last}
                  {cfg.git.last.ok ? `zuletzt ${formatAgo(cfg.git.last.at)}${cfg.git.last.commit ? t(' · Commit {0}', cfg.git.last.commit) : ''}` : t('Fehler: {0}', cfg.git.last.error)}
                {:else}
                  {t('noch nicht gespiegelt – erst speichern')}
                {/if}
              </span>
            </div>
            <p class="muted small">{t('Spiegelt automatisch etwa 30 Sekunden nach jeder Änderung. Änderungen im Repository werden überschrieben, fremde Dateien bleiben.')}</p>
          {/if}
        </div>
      </section>
    </div>

    <section class="card" aria-labelledby="list-title">
      <h2 id="list-title">{t('Sicherungen')}</h2>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th scope="col">{t('Stand')}</th><th scope="col">{t('Ziel')}</th><th scope="col" class="num">{t('Größe')}</th><th scope="col">{t('Aktionen')}</th></tr></thead>
          <tbody>
            {#each items as it, i (i)}
              {#if it.name}
                {@const m = it.name.match(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/)}
                <tr>
                  <td>{m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]} UTC` : it.name}</td>
                  <td>{TARGETS[it.target]}</td>
                  <td class="num">{formatBytes(it.size)}</td>
                  <td class="actions">
                    <Button variant="ghost" size="sm" icon="download" label={t('Laden')} href={`/api/backups/${it.target}/${it.name}`} />
                    <Button variant="ghost" size="sm" label={busy === `test-${it.target}-${it.name}` ? t('Prüft …') : t('Testen')} disabled={busy !== null} onClick={() => test(it)} />
                    <Button variant="secondary" size="sm" label={t('Wiederherstellen')} disabled={busy !== null} onClick={() => (confirm = it)} />
                  </td>
                </tr>
              {:else}
                <tr><td colspan="4" class="bad small">{TARGETS[it.target]}: {it.error}</td></tr>
              {/if}
            {:else}
              <tr><td colspan="4" class="muted">{t('Noch keine Sicherungen.')}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="muted small">{t('Wiederherstellen ersetzt den Stand des Controllers. Die Nodes bekommen danach automatisch die passende Config.')}</p>
    </section>

    <section class="card" aria-labelledby="up-title">
      <h2 id="up-title">{t('Aus Datei wiederherstellen')}</h2>
      <p class="muted small">{t('Für den Umzug auf einen neuen Controller oder wenn die Sicherung woanders liegt. Ohne Oberfläche geht es auch per Kommandozeile:')} <span class="mono">{t('tesseract backup restore DATEI')}</span> {t('(Controller vorher stoppen).')}</p>
      <div class="grid">
        <label class="field col"><span class="label">{t('Datei (.tsbak)')}</span><input class="input" type="file" accept=".tsbak" onchange={(e) => (upload.file = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)} /></label>
        <label class="field col"><span class="label">{t('Passphrase dieser Sicherung')}</span><input class="input" type="password" bind:value={upload.phrase} autocomplete="off" /></label>
      </div>
      <div><Button variant="secondary" label={busy === 'upload' ? t('Spielt zurück …') : t('Wiederherstellen')} disabled={!upload.file || !upload.phrase || busy !== null} onClick={() => (confirmUpload = true)} /></div>
    </section>
  {/if}

  {#if confirm}
    <ConfirmDialog
      title={t('Diese Sicherung wiederherstellen?')}
      text={t('Der aktuelle Stand des Controllers wird durch {0} ersetzt – Änderungen danach gehen verloren. Tipp: vorher „Jetzt sichern“.', confirm.name)}
      word="wiederherstellen"
      confirmLabel={t('Wiederherstellen')}
      tone="warn"
      onConfirm={restore}
      onCancel={() => (confirm = null)}
    />
  {/if}
  {#if confirmUpload}
    <ConfirmDialog
      title={t('Aus Datei wiederherstellen?')}
      text={t('Der aktuelle Stand des Controllers wird durch den Inhalt der Datei ersetzt.')}
      word="wiederherstellen"
      confirmLabel={t('Wiederherstellen')}
      tone="warn"
      onConfirm={restoreUpload}
      onCancel={() => (confirmUpload = false)}
    />
  {/if}
</AppShell>

<style>
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 16px;
    align-items: start;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
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
  .small {
    font-size: 13px;
    margin: 0;
    line-height: 1.5;
  }
  .parts {
    margin: 0;
    padding-left: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;
    color: var(--text-muted);
  }
  .target {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--radius);
    background: var(--bg);
    border: 1px solid var(--border);
  }
  .wide {
    grid-column: 1 / -1;
  }
  .key {
    min-height: 90px;
    font-size: 12px;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .bad {
    color: var(--bad-text);
  }
  .area {
    min-height: 80px;
    padding: 10px 12px;
    resize: vertical;
  }
</style>
