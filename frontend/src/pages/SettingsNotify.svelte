<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import ChipInput from '../lib/components/ChipInput.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import { api } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  type Channel = 'ntfy' | 'email' | 'webhook';
  type Level = 'info' | 'warn' | 'critical';

  interface Notify {
    ntfy: { enabled: boolean; url: string; token_set: boolean };
    email: {
      enabled: boolean;
      host: string;
      port: number;
      security: 'starttls' | 'ssl' | 'none';
      user: string;
      sender: string;
      to: string[];
      password_set: boolean;
    };
    webhook: { enabled: boolean; url: string; secret_set: boolean };
    rules: Record<string, { level: Level; channels: Channel[] }>;
    quiet: { enabled: boolean; start: number; end: number; timezone: string };
    bundle_minutes: number;
    events: { id: string; title: string; default_level: Level }[];
    errors: Partial<Record<Channel, string>>;
    quiet_now: boolean;
  }

  const CHANNELS: { id: Channel; label: string }[] = [
    { id: 'ntfy', label: 'ntfy' },
    { id: 'email', label: 'E-Mail' },
    { id: 'webhook', label: 'Webhook' }
  ];
  const LEVELS: Record<Level, string> = { info: 'Info', warn: 'Warnung', critical: 'Kritisch' };

  let cfg = $state<Notify | null>(null);
  let secrets = $state({ ntfy: '', email: '', webhook: '' });
  let error = $state('');
  let saving = $state(false);
  let testing = $state<Channel | null>(null);

  async function load() {
    try {
      cfg = await api.get<Notify>('/settings/notify');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function save() {
    if (!cfg) return;
    saving = true;
    try {
      const { ntfy, email, webhook } = cfg;
      cfg = await api.put<Notify>('/settings/notify', {
        ntfy: { enabled: ntfy.enabled, url: ntfy.url, token: secrets.ntfy || null },
        email: {
          enabled: email.enabled,
          host: email.host,
          port: Number(email.port),
          security: email.security,
          user: email.user,
          sender: email.sender,
          to: email.to,
          password: secrets.email || null
        },
        webhook: { enabled: webhook.enabled, url: webhook.url, secret: secrets.webhook || null },
        rules: cfg.rules,
        quiet: { ...cfg.quiet, start: Number(cfg.quiet.start), end: Number(cfg.quiet.end) },
        bundle_minutes: Number(cfg.bundle_minutes)
      });
      secrets = { ntfy: '', email: '', webhook: '' };
      toasts.show('ok', 'Gespeichert.');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  async function test(ch: Channel) {
    testing = ch;
    try {
      const r = await api.post<{ ok: boolean; error: string | null }>('/settings/notify/test', { channel: ch });
      if (r.ok) toasts.show('ok', `Testmeldung über ${ch} verschickt.`);
      else toasts.show('bad', `${ch}: ${r.error}`, 12000);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      testing = null;
    }
  }

  function toggle(ev: string, ch: Channel) {
    if (!cfg) return;
    const r = cfg.rules[ev];
    r.channels = r.channels.includes(ch) ? r.channels.filter((c) => c !== ch) : [...r.channels, ch];
  }

  const hours = Array.from({ length: 24 }, (_, h) => h);
</script>

<AppShell active="settings">
  <PageHeader
    title="Einstellungen"
    subtitle="Wohin Tesseract meldet, wenn etwas passiert."
    primaryLabel={saving ? 'Speichert …' : 'Speichern'}
    primaryIcon="check"
    onPrimary={save}
  />
  <SettingsTabs current="#/settings-notify" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if cfg}
    {#each CHANNELS as ch (ch.id)}
      {#if cfg.errors[ch.id]}<Alert tone="bad" title={`${ch.label}: letzte Meldung fehlgeschlagen`} text={cfg.errors[ch.id] ?? ''} />{/if}
    {/each}

    <div class="channels">
      <section class="card" aria-labelledby="ntfy-title">
        <div class="row"><h2 id="ntfy-title">ntfy</h2><span class="spacer"></span><Button variant="ghost" size="sm" label={testing === 'ntfy' ? 'Sendet …' : 'Test senden'} disabled={!cfg.ntfy.enabled || testing !== null} onClick={() => test('ntfy')} /></div>
        <Toggle label="Eingeschaltet" bind:checked={cfg.ntfy.enabled} />
        <label class="field col"><span class="label">Thema (Adresse)</span><input class="input mono" bind:value={cfg.ntfy.url} placeholder="https://ntfy.sh/mein-geheimes-thema" /></label>
        <label class="field col"><span class="label">Zugangstoken (optional){cfg.ntfy.token_set ? ' · gesetzt' : ''}</span><input class="input mono" type="password" bind:value={secrets.ntfy} placeholder={cfg.ntfy.token_set ? 'unverändert lassen' : 'tk_…'} autocomplete="off" /></label>
      </section>

      <section class="card" aria-labelledby="mail-title">
        <div class="row"><h2 id="mail-title">E-Mail</h2><span class="spacer"></span><Button variant="ghost" size="sm" label={testing === 'email' ? 'Sendet …' : 'Test senden'} disabled={!cfg.email.enabled || testing !== null} onClick={() => test('email')} /></div>
        <Toggle label="Eingeschaltet" bind:checked={cfg.email.enabled} />
        <div class="grid2">
          <label class="field col"><span class="label">SMTP-Server</span><input class="input mono" bind:value={cfg.email.host} placeholder="smtp.beispiel.de" /></label>
          <label class="field col"><span class="label">Port</span><input class="input" type="number" bind:value={cfg.email.port} /></label>
          <label class="field col"><span class="label">Verschlüsselung</span>
            <select class="input" bind:value={cfg.email.security}><option value="starttls">STARTTLS</option><option value="ssl">SSL/TLS</option><option value="none">keine</option></select>
          </label>
          <label class="field col"><span class="label">Absender</span><input class="input" bind:value={cfg.email.sender} placeholder="tesseract@beispiel.de" /></label>
          <label class="field col"><span class="label">Benutzer</span><input class="input" bind:value={cfg.email.user} autocomplete="off" /></label>
          <label class="field col"><span class="label">Passwort{cfg.email.password_set ? ' · gesetzt' : ''}</span><input class="input" type="password" bind:value={secrets.email} placeholder={cfg.email.password_set ? 'unverändert lassen' : ''} autocomplete="new-password" /></label>
        </div>
        <ChipInput bind:values={cfg.email.to} label="Empfänger hinzufügen" placeholder="ich@beispiel.de" mono={false} />
      </section>

      <section class="card" aria-labelledby="hook-title">
        <div class="row"><h2 id="hook-title">Webhook</h2><span class="spacer"></span><Button variant="ghost" size="sm" label={testing === 'webhook' ? 'Sendet …' : 'Test senden'} disabled={!cfg.webhook.enabled || testing !== null} onClick={() => test('webhook')} /></div>
        <Toggle label="Eingeschaltet" bind:checked={cfg.webhook.enabled} />
        <label class="field col"><span class="label">Adresse</span><input class="input mono" bind:value={cfg.webhook.url} placeholder="https://hooks.beispiel.de/tesseract" /></label>
        <label class="field col"><span class="label">Geheimnis für die Signatur (optional){cfg.webhook.secret_set ? ' · gesetzt' : ''}</span><input class="input mono" type="password" bind:value={secrets.webhook} placeholder={cfg.webhook.secret_set ? 'unverändert lassen' : ''} autocomplete="off" /></label>
        <p class="muted small">JSON per POST; mit Geheimnis zusätzlich <span class="mono">X-Tesseract-Signature: sha256=…</span> (HMAC über den Inhalt).</p>
      </section>
    </div>

    <div class="opts">
      <section class="card">
        <Toggle label={`Ruhezeit ${cfg.quiet.start}–${cfg.quiet.end} Uhr`} description="nachts nur kritische Meldungen, der Rest kommt morgens gesammelt" bind:checked={cfg.quiet.enabled} />
        <div class="row">
          <label class="field col"><span class="label">von</span><select class="input" bind:value={cfg.quiet.start}>{#each hours as h (h)}<option value={h}>{h} Uhr</option>{/each}</select></label>
          <label class="field col"><span class="label">bis</span><select class="input" bind:value={cfg.quiet.end}>{#each hours as h (h)}<option value={h}>{h} Uhr</option>{/each}</select></label>
          <label class="field col"><span class="label">Zeitzone</span><input class="input" bind:value={cfg.quiet.timezone} /></label>
        </div>
        {#if cfg.quiet_now && cfg.quiet.enabled}<p class="muted small">Gerade ist Ruhezeit.</p>{/if}
      </section>
      <section class="card">
        <Toggle
          label="Gleiche Meldungen bündeln"
          description={`höchstens 1× pro ${cfg.bundle_minutes || 15} Minuten je Ereignis und Kanal`}
          checked={cfg.bundle_minutes > 0}
          onChange={(on) => cfg && (cfg.bundle_minutes = on ? 15 : 0)}
        />
        <label class="field col minutes"><span class="label">Minuten</span><input class="input" type="number" min="0" max="1440" bind:value={cfg.bundle_minutes} /></label>
      </section>
    </div>

    <section class="card" aria-labelledby="rules-title">
      <h2 id="rules-title">Was wird wohin gemeldet?</h2>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Ereignis</th>
              <th scope="col">Stufe</th>
              {#each CHANNELS as ch (ch.id)}<th scope="col" class="center">{ch.label}</th>{/each}
            </tr>
          </thead>
          <tbody>
            {#each cfg.events as ev (ev.id)}
              {@const r = cfg.rules[ev.id]}
              <tr>
                <td>{ev.title}</td>
                <td>
                  <select class="input small-select" bind:value={r.level} aria-label={`Stufe für ${ev.title}`}>
                    {#each Object.entries(LEVELS) as [k, v] (k)}<option value={k}>{v}</option>{/each}
                  </select>
                </td>
                {#each CHANNELS as ch (ch.id)}
                  <td class="center">
                    <input
                      type="checkbox"
                      class="box"
                      checked={r.channels.includes(ch.id)}
                      onchange={() => toggle(ev.id, ch.id)}
                      aria-label={`${ev.title} über ${ch.label}`}
                    />
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="muted small">Kritisch geht immer sofort raus – auch nachts und ohne Bündeln. Selbst gesperrte IPs werden nicht gemeldet, nur automatische Sperren.</p>
    </section>
  {/if}
</AppShell>

<style>
  .channels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    align-items: start;
  }
  .opts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
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
  .center {
    text-align: center;
  }
  .box {
    width: 18px;
    height: 18px;
    accent-color: var(--accent);
  }
  .small-select {
    min-height: 36px;
    padding: 0 8px;
  }
  .minutes {
    max-width: 160px;
  }
</style>
