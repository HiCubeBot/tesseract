<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import { api, formatAgo, formatBytes, formatDate } from '../lib/api';
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
    last: Result | null;
    last_test: Result | null;
    next: string | null;
  }

  interface Item {
    target: 'local' | 's3';
    name: string | null;
    size: number;
    error?: string;
  }

  const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];
  const TARGETS = { local: 'Lokal', s3: 'S3' };

  let cfg = $state<BackupConfig | null>(null);
  let items = $state<Item[]>([]);
  let error = $state('');
  let saving = $state(false);
  let running = $state(false);
  let busy = $state<string | null>(null);
  let phrase = $state('');
  let phrase2 = $state('');
  let s3Secret = $state('');
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

  async function save() {
    if (!cfg) return;
    if (phrase && phrase !== phrase2) {
      toasts.show('bad', 'Die Passphrasen stimmen nicht überein.');
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
        ...(phrase ? { passphrase: phrase } : {})
      });
      phrase = phrase2 = s3Secret = '';
      toasts.show('ok', 'Gespeichert.');
      items = await api.get<Item[]>('/backups');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  async function backupNow() {
    running = true;
    try {
      const r = await api.post<Result>('/backups');
      if (r.ok) toasts.show('ok', `Gesichert: ${r.name} (${formatBytes(r.size ?? 0)}) → ${r.targets?.map((t) => TARGETS[t as 'local']).join(', ')}`);
      else toasts.show('warn', `Teilweise gesichert: ${r.error}`, 12000);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 12000);
    } finally {
      running = false;
      await load();
    }
  }

  async function test(it: Item) {
    busy = `test-${it.target}-${it.name}`;
    try {
      const r = await api.post<Result & { manifest: { counts: Record<string, number> } | null }>('/backups/test', { target: it.target, name: it.name });
      if (r.ok) {
        const c = r.manifest?.counts ?? {};
        toasts.show('ok', `Lesbar und intakt: ${c.hosts ?? 0} Hosts, ${c.persons ?? 0} Personen, ${c.devices ?? 0} Geräte, ${c.nodes ?? 0} Nodes.`, 8000);
      } else toasts.show('bad', `Test fehlgeschlagen: ${r.error}`, 12000);
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
      r.apply_errors.length ? `Wiederhergestellt, aber nicht übertragen: ${r.apply_errors.join('; ')}` : 'Wiederhergestellt und an alle Nodes übertragen. Bitte neu anmelden.',
      12000
    );
    setTimeout(() => location.reload(), 2500);
  }

  async function restore() {
    const it = confirm;
    confirm = null;
    if (!it) return;
    busy = `restore-${it.target}-${it.name}`;
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
      const res = await fetch('/api/backups/restore/upload', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/octet-stream', 'X-Backup-Passphrase': upload.phrase },
        body: upload.file
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail ?? `Fehler ${res.status}`);
      afterRestore(data);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 12000);
    } finally {
      busy = null;
    }
  }

  const ago = (r: Result | null) => (r ? formatAgo(r.at) : 'noch nie');
  const testOld = $derived(!cfg?.last_test || Date.now() - new Date(cfg.last_test.at).getTime() > 31 * 86400e3);
</script>

<AppShell active="settings">
  <PageHeader
    title="Einstellungen"
    subtitle="Sicherungen des Controllers. Nodes brauchen keine – sie bekommen ihre Config vom Controller."
    primaryLabel={running ? 'Sichert …' : 'Jetzt sichern'}
    primaryIcon="download"
    onPrimary={() => !running && backupNow()}
    secondaryLabel={saving ? 'Speichert …' : 'Speichern'}
    onSecondary={save}
  />
  <SettingsTabs current="#/settings-backup" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if cfg}
    {#if !cfg.passphrase_set}
      <Alert tone="warn" title="Noch keine Passphrase" text="Ohne Passphrase gibt es keine Sicherungen. Unten festlegen und gut aufbewahren – ohne sie ist keine Sicherung lesbar." />
    {/if}

    <div class="stats">
      <StatCard
        label="Letzte Sicherung"
        value={ago(cfg.last)}
        sub={cfg.last ? (cfg.last.ok ? `erfolgreich · ${formatBytes(cfg.last.size ?? 0)} · ${cfg.last.targets?.length} Ziel(e)` : (cfg.last.error ?? 'fehlgeschlagen')) : '–'}
        tone={cfg.last ? (cfg.last.ok ? 'ok' : 'bad') : 'neutral'}
        subTone={cfg.last && !cfg.last.ok ? 'bad' : 'muted'}
      />
      <StatCard label="Nächste Sicherung" value={cfg.next ? formatDate(cfg.next) : '–'} sub={{ off: 'kein Zeitplan', hourly: 'stündlich', daily: 'täglich', weekly: 'wöchentlich' }[cfg.schedule]} tone="neutral" />
      <StatCard
        label="Letzter Wiederherstellungstest"
        value={ago(cfg.last_test)}
        sub={cfg.last_test && !cfg.last_test.ok ? (cfg.last_test.error ?? 'fehlgeschlagen') : 'monatlich empfohlen · in der Liste „Testen“'}
        tone={cfg.last_test && !cfg.last_test.ok ? 'bad' : testOld ? 'warn' : 'ok'}
        subTone={cfg.last_test && !cfg.last_test.ok ? 'bad' : testOld ? 'warn' : 'muted'}
      />
    </div>

    <div class="cols">
      <section class="card" aria-labelledby="plan-title">
        <h2 id="plan-title">Zeitplan & Inhalt</h2>
        <div class="grid">
          <label class="field col"><span class="label">Zeitplan</span>
            <select class="input" bind:value={cfg.schedule}>
              <option value="off">aus (nur von Hand)</option>
              <option value="hourly">stündlich</option>
              <option value="daily">täglich</option>
              <option value="weekly">wöchentlich</option>
            </select>
          </label>
          {#if cfg.schedule === 'weekly'}
            <label class="field col"><span class="label">Tag</span>
              <select class="input" bind:value={cfg.weekday}>{#each WEEKDAYS as d, i (i)}<option value={i}>{d}</option>{/each}</select>
            </label>
          {/if}
          {#if cfg.schedule === 'daily' || cfg.schedule === 'weekly'}
            <label class="field col"><span class="label">Uhrzeit</span>
              <select class="input" bind:value={cfg.hour}>{#each Array(24) as _, h (h)}<option value={h}>{String(h).padStart(2, '0')}:00</option>{/each}</select>
            </label>
          {/if}
          <label class="field col"><span class="label">Aufbewahren</span>
            <select class="input" bind:value={cfg.keep}>{#each [7, 14, 30, 60, 90] as k (k)}<option value={k}>{k} Sicherungen</option>{/each}</select>
          </label>
        </div>
        <ul class="parts">
          <li>✓ Hosts, Personen, Geräte, Zugriffe, Nodes, Einstellungen</li>
          <li>✓ Verlauf aller Hosts und Audit-Log mit Prüfsummen-Kette</li>
          <li>✓ Schlüssel der Zwischenzertifikate und Hauptschlüssel (verschlüsselt)</li>
        </ul>
        <Toggle label="Zugriffs-Logs mitsichern" description="können groß werden; Statistik fängt nach dem Zurückspielen sonst neu an" bind:checked={cfg.include_logs} />
        <p class="muted small">Der Root-Schlüssel ist nie enthalten – er liegt offline. Alles wird mit deiner Passphrase verschlüsselt (AES-256-GCM, Schlüssel per scrypt).</p>
        <div class="grid">
          <label class="field col"><span class="label">Passphrase {cfg.passphrase_set ? '(gesetzt – leer lassen = behalten)' : ''}</span>
            <input class="input" type="password" autocomplete="new-password" bind:value={phrase} placeholder="mind. 12 Zeichen" />
          </label>
          <label class="field col"><span class="label">Wiederholen</span>
            <input class="input" type="password" autocomplete="new-password" bind:value={phrase2} />
          </label>
        </div>
      </section>

      <section class="card" aria-labelledby="targets-title">
        <h2 id="targets-title">Ziele</h2>
        <div class="target">
          <Toggle label="Lokal" description="auf dem Controller selbst – schützt nicht vor Hardware-Ausfall" bind:checked={cfg.local.enabled} />
          <span class="mono small">{cfg.local.path}</span>
        </div>
        <div class="target">
          <Toggle label="S3-kompatibel" description="z. B. MinIO auf dem NAS, Garage oder ein externer Anbieter" bind:checked={cfg.s3.enabled} />
          {#if cfg.s3.enabled}
            <div class="grid">
              <label class="field col"><span class="label">Adresse</span><input class="input mono" bind:value={cfg.s3.endpoint} placeholder="https://minio.beispiel.de" /></label>
              <label class="field col"><span class="label">Bucket</span><input class="input mono" bind:value={cfg.s3.bucket} /></label>
              <label class="field col"><span class="label">Region</span><input class="input mono" bind:value={cfg.s3.region} /></label>
              <label class="field col"><span class="label">Ordner (Präfix)</span><input class="input mono" bind:value={cfg.s3.prefix} /></label>
              <label class="field col"><span class="label">Access Key</span><input class="input mono" bind:value={cfg.s3.access_key} autocomplete="off" /></label>
              <label class="field col"><span class="label">Secret Key{cfg.s3.secret_key_set ? ' · gesetzt' : ''}</span><input class="input mono" type="password" bind:value={s3Secret} placeholder={cfg.s3.secret_key_set ? 'unverändert lassen' : ''} autocomplete="off" /></label>
            </div>
          {/if}
        </div>
      </section>
    </div>

    <section class="card" aria-labelledby="list-title">
      <h2 id="list-title">Sicherungen</h2>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th scope="col">Stand</th><th scope="col">Ziel</th><th scope="col" class="num">Größe</th><th scope="col">Aktionen</th></tr></thead>
          <tbody>
            {#each items as it, i (i)}
              {#if it.name}
                {@const m = it.name.match(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/)}
                <tr>
                  <td>{m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]} UTC` : it.name}</td>
                  <td>{TARGETS[it.target]}</td>
                  <td class="num">{formatBytes(it.size)}</td>
                  <td class="actions">
                    <Button variant="ghost" size="sm" icon="download" label="Laden" href={`/api/backups/${it.target}/${it.name}`} />
                    <Button variant="ghost" size="sm" label={busy === `test-${it.target}-${it.name}` ? 'Prüft …' : 'Testen'} disabled={busy !== null} onClick={() => test(it)} />
                    <Button variant="secondary" size="sm" label="Wiederherstellen" disabled={busy !== null} onClick={() => (confirm = it)} />
                  </td>
                </tr>
              {:else}
                <tr><td colspan="4" class="bad small">{TARGETS[it.target]}: {it.error}</td></tr>
              {/if}
            {:else}
              <tr><td colspan="4" class="muted">Noch keine Sicherungen.</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="muted small">Wiederherstellen ersetzt den Stand des Controllers. Die Nodes bekommen danach automatisch die passende Config.</p>
    </section>

    <section class="card" aria-labelledby="up-title">
      <h2 id="up-title">Aus Datei wiederherstellen</h2>
      <p class="muted small">Für den Umzug auf einen neuen Controller oder wenn die Sicherung woanders liegt. Ohne Oberfläche geht es auch per Kommandozeile: <span class="mono">tesseract backup restore DATEI</span> (Controller vorher stoppen).</p>
      <div class="grid">
        <label class="field col"><span class="label">Datei (.tsbak)</span><input class="input" type="file" accept=".tsbak" onchange={(e) => (upload.file = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)} /></label>
        <label class="field col"><span class="label">Passphrase dieser Sicherung</span><input class="input" type="password" bind:value={upload.phrase} autocomplete="off" /></label>
      </div>
      <div><Button variant="secondary" label={busy === 'upload' ? 'Spielt zurück …' : 'Wiederherstellen'} disabled={!upload.file || !upload.phrase || busy !== null} onClick={() => (confirmUpload = true)} /></div>
    </section>
  {/if}

  {#if confirm}
    <ConfirmDialog
      title="Diese Sicherung wiederherstellen?"
      text={`Der aktuelle Stand des Controllers wird durch ${confirm.name} ersetzt – Änderungen danach gehen verloren. Tipp: vorher „Jetzt sichern“.`}
      word="wiederherstellen"
      confirmLabel="Wiederherstellen"
      tone="warn"
      onConfirm={restore}
      onCancel={() => (confirm = null)}
    />
  {/if}
  {#if confirmUpload}
    <ConfirmDialog
      title="Aus Datei wiederherstellen?"
      text="Der aktuelle Stand des Controllers wird durch den Inhalt der Datei ersetzt."
      word="wiederherstellen"
      confirmLabel="Wiederherstellen"
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
</style>
