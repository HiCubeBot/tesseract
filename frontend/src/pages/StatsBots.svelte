<script lang="ts">
  // Statistik › Bot-Schutz: was Anubis vor den Hosts abfängt – geprüft, abgewiesen, bestanden.
  import { locale, t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import ColumnChart from '../lib/components/ColumnChart.svelte';
  import BarList from '../lib/components/BarList.svelte';
  import KpiCard from '../lib/components/KpiCard.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, countryName, type NodeInfo } from '../lib/api';
  import { bucketize, fmt, type Range } from '../lib/stats';

  type Counts = { challenged: number; denied: number; passed: number; failed: number };
  interface Bots {
    totals: Counts;
    previous: Counts;
    pass_rate: number | null;
    visitors: { challenged: number; passed: number; never_passed: number; denied: number };
    hourly: ({ t: string } & Counts)[];
    by_host: ({ host: string } & Counts)[];
    agents: { user_agent: string; challenged: number; denied: number; kind: string; name: string }[];
    countries: { country: string; count: number }[];
    top_ips: { ip: string; country: string | null; count: number; passed: boolean; denied: boolean }[];
    protected_hosts: string[];
    anubis: boolean;
  }

  const RANGES: Range[] = ['24h', '7d', '30d'];
  let range = $state(0);
  let node = $state('');
  let nodes = $state<NodeInfo[]>([]);
  let data = $state<Bots | null>(null);
  let error = $state('');

  async function load() {
    try {
      data = await api.get<Bots>(`/stats/bots?range=${RANGES[range]}&node=${encodeURIComponent(node)}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();
  api.get<NodeInfo[]>('/nodes').then((n) => (nodes = n.filter((x) => x.state !== 'pending')));

  const SERIES = [
    { key: 'challenged', label: t('Zur Prüfung'), color: '#3987E5' },
    { key: 'denied', label: t('Abgewiesen'), color: '#D95926' },
    { key: 'passed', label: t('Bestanden'), color: '#199E70' },
    { key: 'failed', label: t('Gescheitert'), color: '#8A91A0' }
  ];
  const buckets = $derived(data ? bucketize(data.hourly, RANGES[range], SERIES.map((s) => s.key)) : []);
  const spark = (k: string) => buckets.map((b) => b.values[k] ?? 0);
  const delta = (cur: number, prev: number) => (prev ? ((cur - prev) / prev) * 100 : null);
  const rangeText = $derived([t('in 24 Stunden'), t('in 7 Tagen'), t('in 30 Tagen')][range]);
  const empty = $derived(!!data && !Object.values(data.totals).some(Boolean));
  const KIND = { bot: t('Bot'), app: t('App'), browser: t('Browser') } as Record<string, string>;
</script>

<AppShell active="stats">
  <PageHeader title={t('Statistik')} subtitle={t('Was der Bot-Schutz (Anubis) vor den Hosts abfängt.')} />
  <StatsTabs current="#/stats-bots" />

  <div class="row">
    <SegmentedControl groupLabel={t('Zeitraum')} options={[t('Letzte 24 Stunden'), t('7 Tage'), t('30 Tage')]} bind:selected={range} onChange={load} />
    <label class="node-select">
      <span>{t('Node')}</span>
      <select class="input" bind:value={node} onchange={load}>
        <option value="">{t('Alle Nodes')}</option>
        {#each nodes as n (n.id)}<option value={n.name}>{n.name}</option>{/each}
      </select>
    </label>
  </div>

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if data}
    {#if !data.anubis || !data.protected_hosts.length}
      <Alert
        tone="info"
        title={!data.anubis ? t('Bot-Schutz ist nicht eingerichtet') : t('Noch kein Host geschützt')}
        text={!data.anubis
          ? t('Anubis starten (Compose-Profil „anubis“) und unter Einstellungen › Integrationen die Adresse eintragen, dann je Host unter Sicherheit einschalten.')
          : t('Den Bot-Schutz je Host unter Sicherheit einschalten.')}
      />
    {:else}
      <p class="muted small">{t('Geschützt: {0}', data.protected_hosts.join(', '))}</p>
    {/if}

    <section class="kpis" aria-label={t('Kennzahlen')}>
      <!-- „Nie bestanden“: geprüft, aber nie gelöst – meist Bots ohne JavaScript -->
      <KpiCard
        label={t('Zur Prüfung geschickt')}
        value={fmt(data.totals.challenged)}
        delta={delta(data.totals.challenged, data.previous.challenged)}
        sub={rangeText}
        spark={spark('challenged')}
        sparkColor="#3987E5"
      />
      <KpiCard
        label={t('Abgewiesen')}
        value={fmt(data.totals.denied)}
        delta={delta(data.totals.denied, data.previous.denied)}
        sub={t('bekannte schlechte Bots (403)')}
        spark={spark('denied')}
        sparkColor="#D95926"
      />
      <KpiCard
        label={t('Bestanden')}
        value={fmt(data.totals.passed)}
        delta={delta(data.totals.passed, data.previous.passed)}
        sub={data.pass_rate === null ? '–' : t('{0} % der Prüfungen', data.pass_rate.toLocaleString(locale))}
        spark={spark('passed')}
        sparkColor="#199E70"
      />
      <KpiCard
        label={t('Nie bestanden')}
        value={fmt(data.visitors.never_passed)}
        sub={t('von {0} geprüften Adressen', fmt(data.visitors.challenged))}
      />
    </section>

    {#if empty}
      <p class="muted">{t('Keine Bot-Prüfungen im Zeitraum.')}</p>
    {:else}
      <section class="card" aria-labelledby="trend-title">
        <h2 id="trend-title">{t('Verlauf')}</h2>
        <ColumnChart {buckets} series={SERIES} label={t('Bot-Schutz im Verlauf')} height={220} />
        <p class="muted small">
          {t('Gescheitert: {0} – die Lösung wurde abgelehnt (falsch oder zu spät).', fmt(data.totals.failed))}
        </p>
      </section>

      <div class="grid2">
        <section class="card" aria-labelledby="hosts-title">
          <h2 id="hosts-title">{t('Nach Host')}</h2>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th scope="col">{t('Host')}</th>
                  <th scope="col" class="num">{t('Zur Prüfung')}</th>
                  <th scope="col" class="num">{t('Abgewiesen')}</th>
                  <th scope="col" class="num">{t('Bestanden')}</th>
                </tr>
              </thead>
              <tbody>
                {#each data.by_host as h (h.host)}
                  <tr>
                    <td class="mono small nowrap"><a href={`#/logs?q=${encodeURIComponent(`host:${h.host} reason:bot`)}`}>{h.host}</a></td>
                    <td class="num">{fmt(h.challenged)}</td>
                    <td class="num">{fmt(h.denied)}</td>
                    <td class="num">{fmt(h.passed)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>

        <section class="card" aria-labelledby="countries-title">
          <h2 id="countries-title">{t('Herkunft')}</h2>
          <BarList
            color="#3987E5"
            items={data.countries.map((c) => ({ label: countryName(c.country), value: c.count }))}
            empty={t('Keine Länder – GeoIP fehlt oder nur lokale Adressen.')}
          />
        </section>
      </div>

      <section class="card" aria-labelledby="agents-title">
        <h2 id="agents-title">{t('Abgefangene Clients')}</h2>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th scope="col">{t('Erkannt als')}</th>
                <th scope="col">{t('User-Agent')}</th>
                <th scope="col" class="num">{t('Zur Prüfung')}</th>
                <th scope="col" class="num">{t('Abgewiesen')}</th>
              </tr>
            </thead>
            <tbody>
              {#each data.agents as a (a.user_agent)}
                <tr>
                  <td class="small nowrap">{a.name} <span class="muted">· {KIND[a.kind] ?? a.kind}</span></td>
                  <td class="mono small ua" title={a.user_agent}>{a.user_agent || '–'}</td>
                  <td class="num">{fmt(a.challenged)}</td>
                  <td class="num">{fmt(a.denied)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="card" aria-labelledby="ips-title">
        <h2 id="ips-title">{t('Häufigste Adressen')}</h2>
        <ul class="ips">
          {#each data.top_ips as i (i.ip)}
            <li>
              <a class="mono" href={`#/logs?q=${encodeURIComponent(`ip:${i.ip}`)}`}>{i.ip}</a>
              {#if i.country}<span class="muted small">{countryName(i.country)}</span>{/if}
              <span class="grow"></span>
              {#if i.passed}<span class="tag ok">{t('bestanden')}</span>{:else if i.denied}<span class="tag bad">{t('abgewiesen')}</span>{:else}<span class="tag">{t('nie bestanden')}</span>{/if}
              <span class="num">{fmt(i.count)}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</AppShell>

<style>
  h2 {
    margin: 0 0 8px;
    font-size: 16px;
  }
  .small {
    font-size: 12px;
    margin: 0;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
    align-items: start;
  }
  .node-select {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
  }
  .node-select .input {
    width: auto;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .nowrap {
    white-space: nowrap;
  }
  .ua {
    max-width: 420px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }
  .ips li {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .grow {
    flex: 1;
  }
  .tag {
    font-size: 11px;
    padding: 1px 8px;
    border-radius: 999px;
    background: var(--surface-raised);
    color: var(--text-muted);
  }
  .tag.ok {
    color: var(--ok-text, #199e70);
  }
  .tag.bad {
    color: var(--bad-text, #d95926);
  }
</style>
