<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import { api, type AdminAccess, type GeneralSettings } from '../lib/api';
  import { session } from '../lib/session.svelte';
  import { toasts } from '../lib/toast.svelte';

  let general = $state<GeneralSettings | null>(null);
  let pwFromEnv = $state(false);
  api.get<{ password_from_env?: boolean }>('/auth/me').then((m) => (pwFromEnv = !!m.password_from_env));
  let email = $state('');
  let saving = $state(false);
  let error = $state('');

  let access = $state<AdminAccess | null>(null);
  let accessBusy = $state(false);

  async function loadAccess() {
    try {
      access = await api.get<AdminAccess>('/settings/admin-access');
    } catch {
      access = null;
    }
  }
  loadAccess();

  async function setAccess(enabled: boolean) {
    if (!access) return;
    accessBusy = true;
    try {
      access = await api.put<AdminAccess>('/settings/admin-access', { enabled });
      if (access.apply_error) toasts.show('warn', `Gespeichert, aber nicht übertragen: ${access.apply_error}`, 12000);
      else
        toasts.show(
          'ok',
          enabled ? 'Die Oberfläche ist jetzt nur noch mit Admin-Zertifikat erreichbar.' : 'Admin-Zertifikat abgeschaltet.'
        );
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
      await loadAccess();
    } finally {
      accessBusy = false;
    }
  }

  let currentPw = $state('');
  let newPw = $state('');
  let newPw2 = $state('');
  let pwError = $state('');
  let pwSaving = $state(false);

  function fill(g: GeneralSettings) {
    general = g;
    email = g.acme_email;
  }

  api.get<GeneralSettings>('/settings/general').then(fill, (e) => (error = String(e.message ?? e)));

  async function save(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    error = '';
    try {
      const body = { acme_email: email.trim() || null };
      fill(await api.put<GeneralSettings>('/settings/general', body));
      toasts.show('ok', 'Einstellungen gespeichert.');
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      saving = false;
    }
  }

  async function changePassword(e: SubmitEvent) {
    e.preventDefault();
    pwError = '';
    if (newPw !== newPw2) {
      pwError = 'Die neuen Passwörter stimmen nicht überein.';
      return;
    }
    pwSaving = true;
    try {
      await api.post('/auth/password', { current_password: currentPw, new_password: newPw });
      toasts.show('ok', 'Passwort geändert. Bitte neu anmelden.');
      session.user = null;
    } catch (err) {
      pwError = err instanceof Error ? err.message : String(err);
    } finally {
      pwSaving = false;
    }
  }
</script>

<AppShell active="settings">
  <PageHeader title="Einstellungen" subtitle="Gilt für den Controller und als Standard für alle Nodes." />

  <SettingsTabs current="#/settings" />
  {#if general?.env_managed.length}
    <Alert
      tone="info"
      title="Teilweise über die .env festgelegt"
      text={`${general.env_managed.join(', ')} – kommt aus der Umgebung und wird bei jedem Start gesetzt. Änderungen hier gelten nur bis zum nächsten Neustart.`}
    />
  {/if}

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  <div class="grid">
    <form class="card" onsubmit={save} aria-labelledby="le-title">
      <h2 id="le-title">Let's Encrypt</h2>
      <label class="field">
        E-Mail für Ablauf-Warnungen
        <input class="input" type="email" autocomplete="email" placeholder="admin@beispiel.de" bind:value={email} />
        <span class="muted small">Leer lassen geht auch – dann ohne Benachrichtigung von Let's Encrypt.</span>
      </label>
      <p class="muted small">
        Öffentliche IPs stehen jetzt bei jedem Node einzeln (<a href="#/nodes">Nodes</a> › Bearbeiten) – damit prüft „Host anlegen“, ob der
        DNS-Eintrag auf den gewählten Node zeigt.
      </p>
      <div class="row"><Button type="submit" label={saving ? 'Speichert …' : 'Speichern'} disabled={saving} /></div>
    </form>

    <section class="card" aria-labelledby="ctl-title">
      <h2 id="ctl-title">Controller</h2>
      <dl>
        <dt>Domain der Oberfläche</dt>
        <dd class="mono">{general?.controller_domain || '–'}</dd>
        <dt>Version</dt>
        <dd class="mono">{general?.version ?? '–'}</dd>
      </dl>
      <p class="muted small">
        Die Domain kommt aus <code>TESSERACT_CONTROLLER_DOMAIN</code> (Compose: <code>TESSERACT_DOMAIN</code>) –
        so kann sich der Controller nicht versehentlich aussperren.
      </p>
    </section>

    <section class="card" aria-labelledby="access-title">
      <h2 id="access-title">Zugang zur Oberfläche</h2>
      {#if access}
        <Toggle
          label="Nur mit Admin-Zertifikat"
          description="Ohne Zertifikat eines Geräts aus der Gruppe „Admin“ ist die Oberfläche nicht erreichbar. Die Einladungsseite bleibt öffentlich."
          checked={access.enabled}
          onChange={(v) => setAccess(v)}
        />
        <dl>
          <dt>Dieses Gerät</dt>
          <dd>{access.current_device ?? 'kein Admin-Zertifikat erkannt'}</dd>
          <dt>Admin-Geräte</dt>
          <dd>{access.admin_devices} · <a href="#/users">verwalten</a></dd>
          <dt>Erreichbar aus</dt>
          <dd>
            {#if !general || general.admin_networks_open}allen Netzen{:else}<span class="mono">{general.admin_networks.join(', ')}</span>{/if}
            <span class="muted small">· <code>TESSERACT_ADMIN_NETWORKS</code> in der <code>.env</code></span>
          </dd>
        </dl>
        {#if !access.enabled && access.reason}
          <p class="muted small">Zum Einschalten: {access.reason}.</p>
        {/if}
        <p class="muted small">
          Notausgang, falls das Gerät verloren ist – auf dem Controller: <code>tesseract admin mtls off</code>
        </p>
        {#if accessBusy}<p class="muted small" aria-live="polite">Überträgt …</p>{/if}
      {/if}
    </section>

    {#if pwFromEnv}
    <section class="card" aria-labelledby="pw-title">
      <h2 id="pw-title">Passwort</h2>
      <p class="muted small">
        Das Passwort ist in der Umgebung festgelegt (<span class="mono">TESSERACT_ADMIN_PASSWORD</span> in der
        <span class="mono">.env</span>). Zum Ändern dort anpassen und den Controller neu starten.
      </p>
    </section>
    {:else}
    <form class="card" onsubmit={changePassword} aria-labelledby="pw-title">
      <h2 id="pw-title">Passwort ändern</h2>
      <input type="text" autocomplete="username" value={session.user?.username ?? ''} hidden readonly />
      <label class="field">
        Aktuelles Passwort
        <input class="input" type="password" autocomplete="current-password" required bind:value={currentPw} />
      </label>
      <label class="field">
        Neues Passwort (mind. 12 Zeichen)
        <input class="input" type="password" autocomplete="new-password" minlength="12" required bind:value={newPw} />
      </label>
      <label class="field">
        Neues Passwort wiederholen
        <input class="input" type="password" autocomplete="new-password" minlength="12" required bind:value={newPw2} />
      </label>
      {#if pwError}<p class="field-error" role="alert">{pwError}</p>{/if}
      <p class="muted small">Danach werden alle Sitzungen beendet – auch diese.</p>
      <div class="row"><Button type="submit" label={pwSaving ? 'Ändert …' : 'Passwort ändern'} disabled={pwSaving} /></div>
    </form>
    {/if}
  </div>
</AppShell>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
    align-items: start;
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px 16px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  code {
    font-family: var(--font-mono);
    color: var(--text-soft);
  }
</style>
