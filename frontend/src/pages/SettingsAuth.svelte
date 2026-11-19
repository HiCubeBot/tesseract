<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import ChipInput from '../lib/components/ChipInput.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import { api, formatAgo, formatDay } from '../lib/api';
  import * as webauthn from '../lib/webauthn';
  import { toasts } from '../lib/toast.svelte';

  interface OIDC {
    enabled: boolean;
    issuer: string;
    client_id: string;
    client_secret_set: boolean;
    scopes: string;
    label: string;
    admin_group: string;
    groups_claim: string;
    allowed_emails: string[];
    username_claim: string;
  }
  interface AuthCfg {
    password_login: boolean;
    oidc: OIDC;
    redirect_uri: string;
    passkeys_total: number;
  }
  interface Passkey {
    id: number;
    name: string;
    created_at: string;
    last_used_at: string | null;
  }

  let cfg = $state<AuthCfg | null>(null);
  let keys = $state<Passkey[]>([]);
  let secret = $state('');
  let error = $state('');
  let saving = $state(false);
  let adding = $state(false);
  let keyName = $state('');
  let remove = $state<Passkey | null>(null);

  async function load() {
    try {
      [cfg, keys] = await Promise.all([api.get<AuthCfg>('/settings/admin-auth'), api.get<Passkey[]>('/auth/passkeys')]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function save(passwordLogin?: boolean) {
    if (!cfg) return;
    saving = true;
    try {
      const { client_secret_set: _s, ...oidc } = cfg.oidc;
      cfg = await api.put<AuthCfg>('/settings/admin-auth', {
        password_login: passwordLogin ?? cfg.password_login,
        oidc: { ...oidc, client_secret: secret || null }
      });
      secret = '';
      toasts.show('ok', 'Gespeichert.');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
      await load();
    } finally {
      saving = false;
    }
  }

  async function addPasskey() {
    adding = true;
    try {
      const { id, options } = await api.post<{ id: string; options: Record<string, unknown> }>('/auth/passkeys/options');
      const credential = await webauthn.create(options);
      await api.post('/auth/passkeys', { id, credential, name: keyName || 'Passkey' });
      keyName = '';
      toasts.show('ok', 'Passkey hinzugefügt. Ab jetzt geht die Anmeldung auch ohne Passwort.');
      await load();
    } catch (e) {
      toasts.show('bad', webauthn.explain(e), 10000);
    } finally {
      adding = false;
    }
  }

  async function doRemove() {
    const k = remove;
    remove = null;
    if (!k) return;
    try {
      await api.del(`/auth/passkeys/${k.id}`);
      toasts.show('ok', `„${k.name}“ entfernt.`);
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    }
  }

  function copy(text: string) {
    navigator.clipboard?.writeText(text).then(() => toasts.show('ok', 'Kopiert.'));
  }
</script>

<AppShell active="settings">
  <PageHeader
    title="Einstellungen"
    subtitle="Wie sich Admins an der Oberfläche anmelden. Das Admin-Gerätezertifikat bleibt davor die erste Hürde."
    primaryLabel={saving ? 'Speichert …' : 'Speichern'}
    primaryIcon="check"
    onPrimary={() => save()}
  />
  <SettingsTabs current="#/settings-auth" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if cfg}
    <section class="card" aria-labelledby="pk-title">
      <div class="row">
        <h2 id="pk-title">Passkeys (für mein Konto)</h2>
        <span class="spacer"></span>
      </div>
      <p class="muted small">
        Anmelden per Fingerabdruck, Gesicht oder Sicherheitsschlüssel statt Passwort – kein Name, kein Passwort, nicht phishbar.
        Passkeys gelten nur für diese Domain.
      </p>
      {#if !webauthn.supported()}
        <Alert tone="warn" title="Hier nicht möglich" text="Passkeys brauchen HTTPS (oder localhost) und einen aktuellen Browser." />
      {/if}
      {#if keys.length}
        <ul class="list">
          {#each keys as k (k.id)}
            <li>
              <span class="strong">{k.name}</span>
              <span class="muted small">angelegt {formatDay(k.created_at)} · zuletzt {formatAgo(k.last_used_at)}</span>
              <span class="spacer"></span>
              <Button variant="ghost" size="sm" icon="trash" label="Entfernen" onClick={() => (remove = k)} />
            </li>
          {/each}
        </ul>
      {/if}
      <div class="row">
        <input class="input name" placeholder="Name, z. B. YubiKey oder MacBook" bind:value={keyName} maxlength="64" />
        <Button label={adding ? 'Wartet auf das Gerät …' : 'Passkey hinzufügen'} icon="plus" disabled={adding || !webauthn.supported()} onClick={addPasskey} />
      </div>
    </section>

    <section class="card" aria-labelledby="sso-title">
      <h2 id="sso-title">SSO über OpenID Connect</h2>
      <p class="muted small">Für Authelia, Keycloak, Authentik, Dex … Betrifft nur Admins der Oberfläche, nicht die Personen mit Zugriff auf Hosts.</p>
      <Toggle label="Anmeldung über SSO" bind:checked={cfg.oidc.enabled} />
      <div class="code-row">
        <span class="label">Weiterleitungs-Adresse (beim Anbieter eintragen)</span>
        <div class="row"><code class="mono uri">{cfg.redirect_uri}</code><Button variant="ghost" size="sm" icon="clipboard" label="Kopieren" onClick={() => copy(cfg!.redirect_uri)} /></div>
      </div>
      <div class="grid">
        <label class="field col"><span class="label">Aussteller (Issuer)</span><input class="input mono" bind:value={cfg.oidc.issuer} placeholder="https://auth.beispiel.de" /></label>
        <label class="field col"><span class="label">Client-ID</span><input class="input mono" bind:value={cfg.oidc.client_id} placeholder="tesseract" /></label>
        <label class="field col"><span class="label">Client-Secret{cfg.oidc.client_secret_set ? ' · gesetzt' : ''}</span><input class="input mono" type="password" bind:value={secret} placeholder={cfg.oidc.client_secret_set ? 'unverändert lassen' : ''} autocomplete="off" /></label>
        <label class="field col"><span class="label">Scopes</span><input class="input mono" bind:value={cfg.oidc.scopes} /></label>
        <label class="field col"><span class="label">Text auf der Anmeldeseite</span><input class="input" bind:value={cfg.oidc.label} /></label>
        <label class="field col"><span class="label">Benutzername aus Claim</span><input class="input mono" bind:value={cfg.oidc.username_claim} /></label>
      </div>
      <h3>Wer wird Admin?</h3>
      <div class="grid">
        <label class="field col"><span class="label">Mitglied der Gruppe</span><input class="input mono" bind:value={cfg.oidc.admin_group} placeholder="tesseract-admins" /></label>
        <label class="field col"><span class="label">Gruppen-Claim</span><input class="input mono" bind:value={cfg.oidc.groups_claim} /></label>
      </div>
      <span class="label">… oder eine dieser E-Mail-Adressen</span>
      <ChipInput bind:values={cfg.oidc.allowed_emails} label="E-Mail hinzufügen" placeholder="admin@beispiel.de" mono={false} />
    </section>

    <section class="card" aria-labelledby="pw-title">
      <h2 id="pw-title">Passwort-Anmeldung</h2>
      <Toggle
        label="Anmeldung mit Benutzername und Passwort erlauben"
        description="Abschalten geht erst, wenn SSO oder ein Passkey eingerichtet ist. Notausgang auf dem Controller: tesseract admin password-login on"
        checked={cfg.password_login}
        onChange={(on) => save(on)}
      />
    </section>
  {/if}

  {#if remove}
    <ConfirmDialog
      title={`Passkey „${remove.name}“ entfernen?`}
      text="Mit diesem Passkey ist danach keine Anmeldung mehr möglich. Auf dem Gerät selbst bleibt er gespeichert, bis du ihn dort löschst."
      word="entfernen"
      confirmLabel="Entfernen"
      onConfirm={doRemove}
      onCancel={() => (remove = null)}
    />
  {/if}
</AppShell>

<style>
  h3 {
    margin: 6px 0 0;
    font-size: 14px;
  }
  .small {
    font-size: 13px;
    margin: 0;
    line-height: 1.5;
  }
  .label {
    font-size: 13px;
    color: var(--text-muted);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .col {
    flex-direction: column;
    gap: 6px;
  }
  .list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .list li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: var(--radius);
    background: var(--bg);
    border: 1px solid var(--border);
  }
  .strong {
    font-weight: 600;
  }
  .name {
    flex: 1 1 240px;
  }
  .code-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .uri {
    font-size: 12px;
    padding: 6px 10px;
    border-radius: var(--radius);
    background: var(--bg-sunken);
    overflow-wrap: anywhere;
  }
</style>
