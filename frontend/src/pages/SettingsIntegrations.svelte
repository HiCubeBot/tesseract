<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import ChipInput from '../lib/components/ChipInput.svelte';
  import IpListEditor from '../lib/components/IpListEditor.svelte';
  import BansCard from '../lib/components/BansCard.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import { api, WAF_MODES, type GeneralSettings, type IpList, type WafMode } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  let general = $state<GeneralSettings | null>(null);
  let ipLists = $state<IpList[]>([]);
  let error = $state('');
  let saving = $state(false);

  async function load() {
    try {
      [general, ipLists] = await Promise.all([
        api.get<GeneralSettings>('/settings/general'),
        api.get<IpList[]>('/ip-lists')
      ]);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!general) return;
    saving = true;
    try {
      general = await api.put<GeneralSettings>('/settings/general', {
        acme_email: general.acme_email || null,
        public_ips: general.public_ips,
        waf_default_mode: general.waf_default_mode,
        waf_default_paranoia: Number(general.waf_default_paranoia),
        controller_waf_mode: general.controller_waf_mode,
        trusted_proxies: general.trusted_proxies,
        trusted_proxy_list_ids: general.trusted_proxy_list_ids,
        authelia_url: general.authelia_url,
        authelia_headers: general.authelia_headers,
        autoban_enabled: general.autoban_enabled,
        autoban_hits: Number(general.autoban_hits),
        autoban_window_minutes: Number(general.autoban_window_minutes),
        autoban_hours: Number(general.autoban_hours),
        autoban_exempt: general.autoban_exempt
      });
      ipLists = await api.get<IpList[]>('/ip-lists');
      toasts.show('ok', 'Gespeichert.');
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      saving = false;
    }
  }

  const modes = Object.entries(WAF_MODES) as [WafMode, string][];

  let cfToken = $state('');
  let cfSaving = $state(false);

  async function saveToken(token: string) {
    if (!general) return;
    cfSaving = true;
    try {
      general = await api.put<GeneralSettings>('/settings/general', {
        acme_email: general.acme_email || null,
        public_ips: general.public_ips,
        waf_default_mode: general.waf_default_mode,
        waf_default_paranoia: Number(general.waf_default_paranoia),
        controller_waf_mode: general.controller_waf_mode,
        trusted_proxies: general.trusted_proxies,
        trusted_proxy_list_ids: general.trusted_proxy_list_ids,
        authelia_url: general.authelia_url,
        authelia_headers: general.authelia_headers,
        cloudflare_token: token
      });
      cfToken = '';
      toasts.show('ok', token ? 'Cloudflare-Token gespeichert.' : 'Cloudflare-Token gelöscht.');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      cfSaving = false;
    }
  }

  let testing = $state(false);
  let testResult = $state<{ ok: boolean; detail: string } | null>(null);

  async function testAuthelia() {
    testing = true;
    try {
      testResult = await api.post<{ ok: boolean; detail: string }>('/settings/authelia/test');
    } catch (e) {
      testResult = { ok: false, detail: e instanceof Error ? e.message : String(e) };
    } finally {
      testing = false;
    }
  }
</script>

<AppShell active="settings">
  <PageHeader title="Einstellungen" subtitle="Externe Dienste und Caddy-Module, die Hosts nutzen können." />
  <SettingsTabs current="#/settings-integrations" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if general}
    <form class="card" onsubmit={save} aria-labelledby="waf-title">
      <h2 id="waf-title">Coraza WAF · Standards</h2>
      <div class="grid">
        <label class="field">
          Modus für neue Hosts
          <select class="input" bind:value={general.waf_default_mode}>
            {#each modes as [k, v] (k)}<option value={k}>{v}</option>{/each}
          </select>
        </label>
        <label class="field">
          Paranoia-Level für neue Hosts
          <select class="input" bind:value={general.waf_default_paranoia}>
            {#each [1, 2, 3, 4] as l (l)}<option value={l}>{l}</option>{/each}
          </select>
        </label>
        <label class="field">
          WAF für die Tesseract-Oberfläche
          <select class="input" bind:value={general.controller_waf_mode}>
            {#each modes as [k, v] (k)}<option value={k}>{v}</option>{/each}
          </select>
        </label>
      </div>
      <div class="autoban">
        <Toggle
          label="Auto-Sperre"
          description={`IP für ${general.autoban_hours} h sperren nach ${general.autoban_hits} WAF-Treffern in ${general.autoban_window_minutes} Min. – vor allen Hosts, die Oberfläche bleibt erreichbar.`}
          bind:checked={general.autoban_enabled}
        />
        {#if general.autoban_enabled}
          <div class="grid">
            <label class="field">Treffer<input class="input" type="number" min="1" bind:value={general.autoban_hits} /></label>
            <label class="field">in Minuten<input class="input" type="number" min="1" max="1440" bind:value={general.autoban_window_minutes} /></label>
            <label class="field">sperren für Stunden<input class="input" type="number" min="1" bind:value={general.autoban_hours} /></label>
          </div>
          <div class="field">
            Nie automatisch sperren (z. B. eigenes Netz)
            <ChipInput bind:values={general.autoban_exempt} label="Ausnahme hinzufügen" placeholder="192.168.178.0/24" />
          </div>
          {#if !general.autoban_log_ready}
            <Alert tone="warn" title="Kein WAF-Log angebunden" text="Der Controller liest keine Treffer – TESSERACT_CADDY_WAF_LOG und TESSERACT_WAF_LOG_PATH setzen (im Compose-Stack schon eingerichtet)." />
          {/if}
        {/if}
      </div>
      <p class="muted small">
        Bestehende Hosts behalten ihre Einstellung – die änderst du pro Host unter „Sicherheit“.
        Empfehlung: neue Dienste erst „nur protokollieren“, nach ein paar Tagen ohne Fehlalarme auf „Blockieren“.
      </p>
      <div class="row"><Button type="submit" label={saving ? 'Speichert …' : 'Speichern'} disabled={saving} /></div>
    </form>

    <BansCard />

    <section class="card" aria-labelledby="lists-title">
      <h2 id="lists-title">IP-Listen</h2>
      <p class="muted small">Benannte Listen nutzt du im IP-Filter der Hosts und für vertrauenswürdige Proxys.</p>
      <IpListEditor lists={ipLists} onChange={load} />
    </section>

    <form class="card" onsubmit={save} aria-labelledby="proxy-title">
      <h2 id="proxy-title">Vertrauenswürdige Proxys</h2>
      <p class="muted small">
        Steht ein Proxy wie Cloudflare vor Caddy, sieht Caddy sonst nur dessen IP. Nur von diesen Netzen wird
        <code>X-Forwarded-For</code> als echte Client-IP übernommen – wichtig für IP-Filter und Logs.
        Ohne Eintrag: direkte Verbindung.
      </p>
      <div class="field">
        Netze
        <ChipInput bind:values={general.trusted_proxies} label="Proxy-Netz hinzufügen" placeholder="10.0.0.0/8" />
      </div>
      {#if ipLists.length}
        <fieldset>
          <legend>IP-Listen</legend>
          <div class="chips">
            {#each ipLists as l (l.id)}
              <label class="chip" class:on={general.trusted_proxy_list_ids.includes(l.id)}>
                <input type="checkbox" value={l.id} bind:group={general.trusted_proxy_list_ids} />Liste „{l.name}“
              </label>
            {/each}
          </div>
        </fieldset>
      {/if}
      <div class="row"><Button type="submit" label={saving ? 'Speichert …' : 'Speichern'} disabled={saving} /></div>
    </form>

    <form class="card" onsubmit={(e) => (e.preventDefault(), saveToken(cfToken))} aria-labelledby="dns-title">
      <h2 id="dns-title">DNS-01 über Cloudflare</h2>
      <p class="muted small">
        Damit holt Caddy Zertifikate auch ohne offenen Port 80 und für Wildcard-Hosts (<code>*.beispiel.de</code>).
        Nötig ist ein API-Token mit dem Recht „Zone · DNS · Bearbeiten“ für deine Zone. Er wird verschlüsselt
        gespeichert und nie wieder angezeigt.
      </p>
      <label class="field">
        API-Token {general.cloudflare_token_set ? '· hinterlegt' : ''}
        <input
          class="input mono"
          type="password"
          autocomplete="off"
          placeholder={general.cloudflare_token_set ? 'neuen Token eintragen, um ihn zu ersetzen' : 'Token einfügen'}
          bind:value={cfToken}
        />
      </label>
      <div class="row">
        <Button type="submit" label={cfSaving ? 'Speichert …' : 'Token speichern'} disabled={cfSaving || !cfToken.trim()} />
        {#if general.cloudflare_token_set}
          <Button variant="ghost" label="Token löschen" disabled={cfSaving} onClick={() => saveToken('')} />
        {/if}
      </div>
    </form>

    <form class="card" onsubmit={save} aria-labelledby="authelia-title">
      <h2 id="authelia-title">Authelia</h2>
      <p class="muted small">
        Optionales Login vor einzelnen Hosts. Nutzer, Gruppen und Regeln (ein/zwei Faktoren) pflegst du in Authelia.
        Tesseract richtet nur die Weiterleitung ein – die Tesseract-Oberfläche selbst nutzt Authelia nicht.
      </p>
      <label class="field">
        Adresse der Authelia-Instanz (vom Node aus)
        <input class="input mono" placeholder="http://authelia:9091 oder https://auth.beispiel.de" bind:value={general.authelia_url} />
      </label>
      <div class="field">
        An den Dienst weitergereichte Header
        <ChipInput bind:values={general.authelia_headers} label="Header hinzufügen" placeholder="Remote-User" />
      </div>
      <div class="row">
        <Button type="submit" label={saving ? 'Speichert …' : 'Speichern'} disabled={saving} />
        <Button variant="secondary" label={testing ? 'Prüft …' : 'Verbindung testen'} disabled={testing || !general.authelia_url} onClick={testAuthelia} />
        {#if testResult}
          <span class="small" class:ok={testResult.ok} class:bad={!testResult.ok}>{testResult.detail}</span>
        {/if}
      </div>
      <p class="muted small">Getestet wird vom Controller aus; erst speichern, dann testen.</p>
    </form>
  {/if}
</AppShell>

<style>
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  .ok {
    color: var(--ok-text);
  }
  .autoban {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }
  .bad {
    color: var(--bad-text);
  }
  code {
    font-family: var(--font-mono);
    color: var(--text-soft);
  }
  fieldset {
    margin: 0;
    padding: 0;
    border: none;
  }
  legend {
    padding: 0;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--text-muted);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 0 12px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }
  .chip.on {
    background: var(--accent-soft);
    color: #d6d0ff;
  }
  .chip input {
    margin: 0;
    accent-color: var(--accent);
  }
</style>
