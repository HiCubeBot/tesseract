<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import ChipInput from '../lib/components/ChipInput.svelte';
  import { api, ROBOTS_MODES, type AdminAccess, type GeneralSettings, type RobotsMode } from '../lib/api';
  import { session } from '../lib/session.svelte';
  import { toasts } from '../lib/toast.svelte';

  let general = $state<GeneralSettings | null>(null);
  let pwFromEnv = $state(false);
  api.get<{ password_from_env?: boolean }>('/auth/me').then((m) => (pwFromEnv = !!m.password_from_env));
  let email = $state('');
  let saving = $state(false);
  let error = $state('');

  let access = $state<AdminAccess | null>(null);
  let statusBusy = $state(false);

  async function setStatusPage(enabled: boolean) {
    statusBusy = true;
    try {
      fill(await api.put<GeneralSettings>('/settings/general', { status_page_enabled: enabled }));
      toasts.show('ok', enabled ? 'Die Statusseite ist jetzt öffentlich erreichbar.' : 'Statusseite ausgeschaltet.');
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    } finally {
      statusBusy = false;
    }
  }
  let accessBusy = $state(false);

  // robots.txt
  const robotsDefaults: RobotsMode[] = ['off', 'allow', 'deny', 'deny_ai'];
  let robotsDefault = $state<RobotsMode>('off');
  let robotsMtls = $state(true);
  let aiBots = $state<string[]>([]);
  let robotsBusy = $state(false);

  async function saveRobots(reset = false) {
    robotsBusy = true;
    try {
      fill(
        await api.put<GeneralSettings>('/settings/general', {
          robots_default: robotsDefault,
          robots_mtls_deny: robotsMtls,
          robots_ai_bots: reset ? [] : aiBots
        })
      );
      toasts.show('ok', 'robots.txt-Einstellungen gespeichert.');
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    } finally {
      robotsBusy = false;
    }
  }

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
    robotsDefault = g.robots_default;
    robotsMtls = g.robots_mtls_deny;
    aiBots = [...g.robots_ai_bots];
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
          {#if general && !general.admin_networks_open}
            <dt>Nodes</dt>
            <dd>
              {general.agent_api_public ? 'aus allen Netzen (Schnittstelle ausgenommen)' : 'nur aus diesen Netzen'}
              <span class="muted small">· <code>TESSERACT_AGENT_API_PUBLIC</code></span>
            </dd>
          {/if}
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

    <section class="card" aria-labelledby="status-title">
      <h2 id="status-title">Öffentliche Statusseite</h2>
      {#if general}
        <Toggle
          label="Statusseite einschalten"
          description="Zeigt ohne Anmeldung, ob die ausgewählten Dienste laufen – nur Name, Stand und Erreichbarkeit der letzten 90 Tage, keine Domains oder Adressen. Auch bei TESSERACT_ADMIN_NETWORKS von überall erreichbar."
          checked={general.status_page_enabled}
          onChange={(v) => setStatusPage(v)}
        />
        {#if statusBusy}<p class="muted small" aria-live="polite">Überträgt …</p>{/if}
        {#if general.status_page_enabled}
          <p class="small"><a class="mono" href={general.status_page_url} target="_blank" rel="noopener">{general.status_page_url}</a></p>
        {/if}
        <p class="muted small">
          Welche Dienste dort stehen, legst du je Host fest: Allgemein › Überwachung › „Auf der öffentlichen Statusseite zeigen“.
        </p>
      {/if}
    </section>

    <section class="card" aria-labelledby="robots-title">
      <h2 id="robots-title">robots.txt</h2>
      {#if general}
        <label class="field">
          Standard für neue Hosts
          <select class="input" bind:value={robotsDefault}>
            {#each robotsDefaults as m (m)}<option value={m}>{ROBOTS_MODES[m]}</option>{/each}
          </select>
        </label>
        <Toggle
          label="Hosts nur mit Zertifikat: alles verbieten"
          description="mTLS-Hosts ohne eigene robots.txt-Einstellung bekommen automatisch „Disallow: /“."
          bind:checked={robotsMtls}
        />
        <ChipInput label="KI-Crawler (für „KI-Crawler verbieten“)" bind:values={aiBots} placeholder="GPTBot, ClaudeBot …" />
        <div class="row">
          <Button label={robotsBusy ? 'Speichert …' : 'Speichern'} disabled={robotsBusy} onClick={() => saveRobots()} />
          <Button variant="ghost" label="Liste zurücksetzen" disabled={robotsBusy} onClick={() => saveRobots(true)} />
        </div>
        <p class="muted small">Pro Host unter Hosts › Sicherheit › robots.txt; per Docker-Label <code>tesseract.robots=deny-ai</code>.</p>
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
