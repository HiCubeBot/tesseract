<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import { api, formatAgo } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  interface SyncResult {
    at: string;
    ok: boolean;
    error?: string;
    dry_run?: boolean;
    users?: number;
    groups?: number;
    created?: string[];
    updated?: string[];
    disabled?: string[];
    enabled?: string[];
    revoked_devices?: number;
    groups_created?: string[];
    memberships_changed?: number;
  }
  interface LdapCfg {
    enabled: boolean;
    url: string;
    starttls: boolean;
    bind_dn: string;
    bind_password_set: boolean;
    user_base: string;
    user_filter: string;
    attr_uid: string;
    attr_name: string;
    attr_mail: string;
    disabled_filter: string;
    group_base: string;
    group_filter: string;
    attr_group_name: string;
    attr_member: string;
    interval_minutes: number;
    revoke_devices: boolean;
    last: SyncResult | null;
  }

  // Vorlagen für verbreitete Verzeichnisse
  const PRESETS: Record<string, Partial<LdapCfg>> = {
    'OpenLDAP / lldap': { user_filter: '(objectClass=person)', attr_uid: 'uid', attr_name: 'cn', attr_mail: 'mail', disabled_filter: '', group_filter: '(|(objectClass=groupOfNames)(objectClass=groupOfUniqueNames))', attr_member: 'member' },
    'Active Directory': { user_filter: '(&(objectCategory=person)(objectClass=user))', attr_uid: 'sAMAccountName', attr_name: 'displayName', attr_mail: 'mail', disabled_filter: '(userAccountControl:1.2.840.113556.1.4.803:=2)', group_filter: '(objectClass=group)', attr_member: 'member' },
    'FreeIPA / 389ds': { user_filter: '(objectClass=person)', attr_uid: 'uid', attr_name: 'cn', attr_mail: 'mail', disabled_filter: '(nsAccountLock=TRUE)', group_filter: '(objectClass=groupOfNames)', attr_member: 'member' }
  };

  let cfg = $state<LdapCfg | null>(null);
  let password = $state('');
  let error = $state('');
  let busy = $state<string | null>(null);
  let preview = $state<SyncResult | null>(null);

  async function load() {
    try {
      cfg = await api.get<LdapCfg>('/settings/ldap');
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function save(): Promise<boolean> {
    if (!cfg) return false;
    busy = 'save';
    try {
      const { bind_password_set: _p, last: _l, ...rest } = cfg;
      cfg = await api.put<LdapCfg>('/settings/ldap', { ...rest, interval_minutes: Number(rest.interval_minutes), bind_password: password || null });
      password = '';
      toasts.show('ok', 'Gespeichert.');
      return true;
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
      return false;
    } finally {
      busy = null;
    }
  }

  async function sync(dry: boolean) {
    if (!(await save())) return;
    busy = dry ? 'preview' : 'sync';
    try {
      const r = await api.post<SyncResult>(`/settings/ldap/sync?dry_run=${dry}`);
      if (dry) preview = r;
      else {
        preview = null;
        if (r.ok) toasts.show('ok', `Abgeglichen: ${r.users} Personen, ${r.groups} Gruppen.`);
        else toasts.show('bad', r.error ?? 'Abgleich fehlgeschlagen', 12000);
        await load();
      }
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      busy = null;
    }
  }

  const list = (xs: string[] | undefined) => (xs && xs.length ? xs.join(', ') : '–');
</script>

<AppShell active="settings">
  <PageHeader
    title="Einstellungen"
    subtitle="Personen und Gruppen aus einem LDAP-Verzeichnis übernehmen. Geräte und Zertifikate verwaltet weiter Tesseract."
    primaryLabel={busy === 'save' ? 'Speichert …' : 'Speichern'}
    primaryIcon="check"
    onPrimary={save}
  />
  <SettingsTabs current="#/settings-ldap" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if cfg}
    {#if cfg.last}
      <Alert
        tone={cfg.last.ok ? 'ok' : 'bad'}
        title={cfg.last.ok ? `Letzter Abgleich ${formatAgo(cfg.last.at)}` : `Letzter Abgleich fehlgeschlagen (${formatAgo(cfg.last.at)})`}
        text={cfg.last.ok ? `${cfg.last.users} Personen, ${cfg.last.groups} Gruppen · neu: ${list(cfg.last.created)} · gesperrt: ${list(cfg.last.disabled)}` : (cfg.last.error ?? '')}
      />
    {/if}

    <section class="card" aria-labelledby="conn-title">
      <h2 id="conn-title">Verbindung</h2>
      <Toggle label="Regelmäßig abgleichen" description={`alle ${cfg.interval_minutes} Minuten`} bind:checked={cfg.enabled} />
      <div class="grid">
        <label class="field col"><span class="label">Adresse</span><input class="input mono" bind:value={cfg.url} placeholder="ldaps://ldap.beispiel.de:636" /></label>
        <label class="field col"><span class="label">Bind-DN</span><input class="input mono" bind:value={cfg.bind_dn} placeholder="cn=tesseract,ou=dienste,dc=beispiel,dc=de" /></label>
        <label class="field col"><span class="label">Passwort{cfg.bind_password_set ? ' · gesetzt' : ''}</span><input class="input" type="password" bind:value={password} placeholder={cfg.bind_password_set ? 'unverändert lassen' : ''} autocomplete="off" /></label>
        <label class="field col"><span class="label">Abstand (Minuten)</span><input class="input" type="number" min="5" bind:value={cfg.interval_minutes} /></label>
      </div>
      <label class="check"><input type="checkbox" bind:checked={cfg.starttls} /> STARTTLS (bei ldap://)</label>
    </section>

    <section class="card" aria-labelledby="map-title">
      <div class="row">
        <h2 id="map-title">Personen und Gruppen</h2>
        <span class="spacer"></span>
        <label class="preset">Vorlage
          <select class="input" onchange={(e) => { const p = PRESETS[(e.currentTarget as HTMLSelectElement).value]; if (p && cfg) Object.assign(cfg, p); }}>
            <option value="">–</option>
            {#each Object.keys(PRESETS) as k (k)}<option value={k}>{k}</option>{/each}
          </select>
        </label>
      </div>
      <div class="grid">
        <label class="field col"><span class="label">Suchbasis Personen</span><input class="input mono" bind:value={cfg.user_base} placeholder="ou=people,dc=beispiel,dc=de" /></label>
        <label class="field col"><span class="label">Filter Personen</span><input class="input mono" bind:value={cfg.user_filter} /></label>
        <label class="field col"><span class="label">Attribut Kennung</span><input class="input mono" bind:value={cfg.attr_uid} /></label>
        <label class="field col"><span class="label">Attribut Name</span><input class="input mono" bind:value={cfg.attr_name} /></label>
        <label class="field col"><span class="label">Attribut E-Mail</span><input class="input mono" bind:value={cfg.attr_mail} /></label>
        <label class="field col"><span class="label">Filter „deaktiviert“ (optional)</span><input class="input mono" bind:value={cfg.disabled_filter} placeholder="(nsAccountLock=TRUE)" /></label>
        <label class="field col"><span class="label">Suchbasis Gruppen (leer = keine)</span><input class="input mono" bind:value={cfg.group_base} placeholder="ou=groups,dc=beispiel,dc=de" /></label>
        <label class="field col"><span class="label">Filter Gruppen</span><input class="input mono" bind:value={cfg.group_filter} /></label>
        <label class="field col"><span class="label">Attribut Gruppenname</span><input class="input mono" bind:value={cfg.attr_group_name} /></label>
        <label class="field col"><span class="label">Attribut Mitglieder</span><input class="input mono" bind:value={cfg.attr_member} /></label>
      </div>
      <Toggle
        label="Geräte gesperrter Personen widerrufen"
        description="Wer in LDAP deaktiviert ist oder dort verschwindet, wird gesperrt. Mit diesem Schalter werden auch die Zertifikate widerrufen – endgültig, auch wenn die Person später wieder aktiv wird."
        bind:checked={cfg.revoke_devices}
      />
      <div class="row">
        <Button variant="secondary" label={busy === 'preview' ? 'Prüft …' : 'Vorschau'} disabled={busy !== null} onClick={() => sync(true)} />
        <Button label={busy === 'sync' ? 'Gleicht ab …' : 'Jetzt abgleichen'} icon="refresh" disabled={busy !== null} onClick={() => sync(false)} />
      </div>
    </section>

    {#if preview}
      <section class="card" aria-labelledby="pre-title">
        <h2 id="pre-title">Vorschau – noch nichts geändert</h2>
        {#if preview.ok}
          <dl>
            <dt>Gefunden</dt><dd>{preview.users} Personen, {preview.groups} Gruppen</dd>
            <dt>Neu</dt><dd>{list(preview.created)}</dd>
            <dt>Geändert/verknüpft</dt><dd>{list(preview.updated)}</dd>
            <dt>Würden gesperrt</dt><dd class:bad={!!preview.disabled?.length}>{list(preview.disabled)}{#if preview.revoked_devices} · {preview.revoked_devices} Geräte widerrufen{/if}</dd>
            <dt>Wieder aktiv</dt><dd>{list(preview.enabled)}</dd>
            <dt>Neue Gruppen</dt><dd>{list(preview.groups_created)}</dd>
            <dt>Mitgliedschaften</dt><dd>{preview.memberships_changed} Änderungen</dd>
          </dl>
        {:else}
          <Alert tone="bad" title="Abgleich nicht möglich" text={preview.error ?? ''} />
        {/if}
      </section>
    {/if}

    <p class="muted small">
      LDAP-Personen und -Gruppen sind unter Nutzer gekennzeichnet. Name, E-Mail, Sperre und die Mitglieder von LDAP-Gruppen kommen aus LDAP –
      Änderungen daran in Tesseract überschreibt der nächste Abgleich. Freigaben, Geräte und Tesseract-eigene Gruppen bleiben.
    </p>
  {/if}
</AppShell>

<style>
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
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }
  .col {
    flex-direction: column;
    gap: 6px;
  }
  .preset {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-muted);
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 16px;
    font-size: 13px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .bad {
    color: var(--bad-text);
  }
</style>
