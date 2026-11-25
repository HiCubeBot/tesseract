<script lang="ts">
  // Profil: persönliche Einstellungen dieses Browsers – Sprache und Farbschema.
  import { t, lang, langChosen, LANGUAGES, setLang, type Lang } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import { theme, THEME_LABELS, type ThemeChoice } from '../lib/theme.svelte';
  import { session } from '../lib/session.svelte';
  import { UI_ROLES } from '../lib/api';

  // Sprache: „Wie Browser“ oder fest gewählt – Umschalten lädt die Seite neu
  const langCodes = Object.keys(LANGUAGES) as Lang[];
  const langOptions = [t('Wie Browser'), ...langCodes.map((c) => LANGUAGES[c].label)];
  let langIndex = $state(langChosen ? langCodes.indexOf(lang) + 1 : 0);

  function pickLang(i: number) {
    setLang(i === 0 ? null : langCodes[i - 1]);
  }

  const themes: ThemeChoice[] = ['system', 'light', 'dark'];
  let themeIndex = $state(themes.indexOf(theme.choice));
</script>

<AppShell active="profile">
  <PageHeader title={t('Profil')} subtitle={t('Persönliche Einstellungen – gelten für diesen Browser.')} />

  <div class="grid">
    <section class="card" aria-labelledby="account-title">
      <h2 id="account-title">{t('Konto')}</h2>
      <dl>
        <dt>{t('Angemeldet als')}</dt>
        <dd>{session.user?.username ?? '–'}</dd>
        {#if session.viaCert}
          <dt>{t('Gerät')}</dt>
          <dd>{session.user?.device ?? '–'}</dd>
          <dt>{t('Rolle')}</dt>
          <dd>{UI_ROLES[session.role]}</dd>
        {:else}
          <dt>{t('Anmeldung')}</dt>
          <dd>{session.user?.source === 'oidc' ? t('SSO (OpenID Connect)') : t('Passwort oder Passkey')}</dd>
        {/if}
      </dl>
      {#if session.viaCert}
        <p class="muted small">
          {t('Per Gerätezertifikat angemeldet – ohne Passwort.')} <a href="#/me">{t('Mein Zugang')}</a>
        </p>
      {:else if session.isAdmin}
        <p class="muted small">
          <a href="#/settings">{t('Passwort ändern')}</a> · <a href="#/settings-auth">{t('Passkeys verwalten')}</a>
        </p>
      {/if}
    </section>

    <section class="card" aria-labelledby="lang-title">
      <h2 id="lang-title">{t('Sprache')}</h2>
      <SegmentedControl groupLabel={t('Sprache')} options={langOptions} bind:selected={langIndex} onChange={pickLang} />
      <p class="muted small">{t('„Wie Browser“ folgt der Spracheinstellung des Browsers. Beim Wechsel lädt die Seite neu.')}</p>
    </section>

    <section class="card" aria-labelledby="theme-title">
      <h2 id="theme-title">{t('Farbschema')}</h2>
      <SegmentedControl
        groupLabel={t('Farbschema')}
        options={themes.map((c) => THEME_LABELS[c])}
        bind:selected={themeIndex}
        onChange={(i) => theme.set(themes[i])}
      />
      <p class="muted small">{t('„Wie System“ folgt dem hellen oder dunklen Modus des Betriebssystems.')}</p>
    </section>
  </div>
</AppShell>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 18px;
    align-items: start;
  }
  h2 {
    margin: 0;
    font-size: 16px;
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
</style>
