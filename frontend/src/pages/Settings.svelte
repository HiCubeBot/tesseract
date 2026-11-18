<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, type GeneralSettings } from '../lib/api';
  import { session } from '../lib/session.svelte';
  import { toasts } from '../lib/toast.svelte';

  let general = $state<GeneralSettings | null>(null);
  let email = $state('');
  let ips = $state('');
  let saving = $state(false);
  let error = $state('');

  let currentPw = $state('');
  let newPw = $state('');
  let newPw2 = $state('');
  let pwError = $state('');
  let pwSaving = $state(false);

  function fill(g: GeneralSettings) {
    general = g;
    email = g.acme_email;
    ips = g.public_ips.join(', ');
  }

  api.get<GeneralSettings>('/settings/general').then(fill, (e) => (error = String(e.message ?? e)));

  async function save(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    error = '';
    try {
      const body = {
        acme_email: email.trim() || null,
        public_ips: ips.split(/[\s,]+/).filter(Boolean)
      };
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

  <nav class="tabs" aria-label="Bereiche">
    <a href="#/settings" aria-current="page">Allgemein</a>
    <a href="#/design/settings-integrations">Integrationen</a>
    <a href="#/design/settings-ca">Zertifizierungsstelle</a>
    <a href="#/design/settings-notify">Benachrichtigungen</a>
    <a href="#/design/settings-metrics">Metriken</a>
    <a href="#/design/settings-backup">Backup</a>
  </nav>

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  <div class="grid">
    <form class="card" onsubmit={save} aria-labelledby="le-title">
      <h2 id="le-title">Let's Encrypt</h2>
      <label class="field">
        E-Mail für Ablauf-Warnungen
        <input class="input" type="email" autocomplete="email" placeholder="admin@beispiel.de" bind:value={email} />
        <span class="muted small">Leer lassen geht auch – dann ohne Benachrichtigung von Let's Encrypt.</span>
      </label>
      <label class="field">
        Öffentliche IP(s) des Nodes
        <input class="input mono" type="text" placeholder="203.0.113.7, 2001:db8::7" bind:value={ips} />
        <span class="muted small">Damit prüft „Host anlegen“, ob der DNS-Eintrag auf den Node zeigt.</span>
      </label>
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
  </div>
</AppShell>

<style>
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    border-bottom: 1px solid var(--border);
  }
  .tabs a {
    padding: 10px 14px;
    color: var(--text-muted);
    text-decoration: none;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }
  .tabs a[aria-current='page'] {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
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
