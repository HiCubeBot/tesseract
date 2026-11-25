<script lang="ts">
  import { t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, countryName, formatAgo, formatBytes } from '../lib/api';
  import { fmt, weekGrid, WEEKDAYS } from '../lib/stats';

  interface Usage {
    hosts: string[];
    matrix: { person: string; counts: Record<string, number>; total: number }[];
    hourly: { t: string; n: number }[];
    devices: {
      id: number;
      name: string;
      person: string;
      last: string;
      requests: number;
      bytes: number;
      top_host: string;
      countries: string[];
      revoked: boolean;
    }[];
  }

  let range = $state(0);
  let data = $state<Usage | null>(null);
  let error = $state('');
  let cell = $state<{ d: number; h: number } | null>(null);

  async function load() {
    try {
      data = await api.get<Usage>(`/stats/usage?range=${range === 0 ? '7d' : '30d'}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  const grid = $derived(data ? weekGrid(data.hourly) : []);
  const gridMax = $derived(Math.max(1, ...grid.flat()));
  const matrixMax = $derived(Math.max(1, ...(data?.matrix.flatMap((m) => Object.values(m.counts)) ?? [])));
  /** Sequenziell, ein Farbton (Akzent-Violett), hell = wenig → kräftig = viel */
  const shade = (v: number, max: number) => (v ? `rgba(144, 133, 233, ${0.15 + 0.85 * (v / max)})` : 'transparent');
  const short = (h: string) => h.split('.')[0];
  const busiest = $derived.by(() => {
    let best = { d: 0, h: 0, v: 0 };
    grid.forEach((row, d) => row.forEach((v, h) => v > best.v && (best = { d, h, v })));
    return best.v ? t('{0} {1}–{2} Uhr', WEEKDAYS[best.d], best.h, best.h + 1) : null;
  });
</script>

<AppShell active="stats">
  <PageHeader title={t('Statistik')} subtitle={t('Wer welche privaten Dienste nutzt – erkannt am Gerätezertifikat.')} />
  <StatsTabs current="#/stats-usage" />

  <div class="row">
    <SegmentedControl groupLabel={t('Zeitraum')} options={[t('Letzte 7 Tage'), t('30 Tage')]} bind:selected={range} onChange={load} />
  </div>

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if data}
    {#if data.matrix.length === 0}
      <Alert
        tone="info"
        title={t('Noch keine Zugriffe mit Gerätezertifikat')}
        text={t('Hier erscheinen Anfragen, die ein freigegebenes Gerät mit seinem Zertifikat gestellt hat – also Zugriffe auf private (mTLS-)Dienste.')}
      />
    {:else}
      <section class="card" aria-labelledby="matrix-title">
        <h2 id="matrix-title">{t('Wer nutzt was?')}</h2>
        <p class="muted small">{t('Anfragen {0} · – = kein Zugriff', range === 0 ? t('in 7 Tagen') : t('in 30 Tagen'))}</p>
        <div class="table-wrap">
          <table class="table matrix">
            <thead>
              <tr>
                <th scope="col">{t('Person')}</th>
                {#each data.hosts as h (h)}<th scope="col" class="num" title={h}>{short(h)}</th>{/each}
                <th scope="col" class="num">{t('Summe')}</th>
              </tr>
            </thead>
            <tbody>
              {#each data.matrix as row (row.person)}
                <tr>
                  <th scope="row">{row.person}</th>
                  {#each data.hosts as h (h)}
                    {@const v = row.counts[h] ?? 0}
                    <td class="num" style:background={shade(v, matrixMax)}>{v ? fmt(v) : '–'}</td>
                  {/each}
                  <td class="num strong">{fmt(row.total)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="card" aria-labelledby="heat-title">
        <h2 id="heat-title">{t('Wann wird genutzt?')}</h2>
        <p class="muted small">{t('alle privaten Dienste · Wochentag × Uhrzeit (Ortszeit)')}{#if busiest} {t('· am meisten los: {0}', busiest)}{/if}</p>
        <div class="heat" role="img" aria-label={t('Nutzung nach Wochentag und Uhrzeit{0}', busiest ? t(', am meisten ') + busiest : '')}>
          <div class="hours" aria-hidden="true">
            <span></span>
            {#each Array(24) as _, h (h)}<span>{h % 6 === 0 ? t('{0} Uhr', h) : ''}</span>{/each}
          </div>
          {#each grid as row, d (d)}
            <div class="heat-row">
              <span class="day">{WEEKDAYS[d]}</span>
              {#each row as v, h (h)}
                <span
                  class="cell"
                  role="presentation"
                  title={t('{0} {1} Uhr: {2} Anfragen', WEEKDAYS[d], h, v)}
                  style:background={v ? shade(v, gridMax) : 'var(--surface-raised)'}
                  onmouseenter={() => (cell = { d, h })}
                  onmouseleave={() => (cell = null)}
                ></span>
              {/each}
            </div>
          {/each}
        </div>
        <p class="muted small hint">
          {#if cell}{t('{0} {1}–{2} Uhr: {3} Anfragen', WEEKDAYS[cell.d], cell.h, cell.h + 1, fmt(grid[cell.d][cell.h]))}{:else}{t('Feld berühren für Einzelwerte')}{/if}
        </p>
      </section>

      <section class="card" aria-labelledby="dev-title">
        <h2 id="dev-title">{t('Geräte-Aktivität')}</h2>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th scope="col">{t('Gerät')}</th>
                <th scope="col">{t('Zuletzt')}</th>
                <th scope="col" class="num">{t('Anfragen')}</th>
                <th scope="col" class="num">{t('Daten')}</th>
                <th scope="col">{t('Meistgenutzt')}</th>
                <th scope="col">{t('Ort')}</th>
                <th scope="col">{t('Auffällig')}</th>
              </tr>
            </thead>
            <tbody>
              {#each data.devices as d (d.id)}
                <tr>
                  <td><span class="strong">{d.name}</span> <span class="muted small">· {d.person}</span></td>
                  <td>{formatAgo(d.last)}</td>
                  <td class="num"><a href={`#/logs?q=${encodeURIComponent('device:' + d.name)}`}>{fmt(d.requests)}</a></td>
                  <td class="num">{formatBytes(d.bytes)}</td>
                  <td>{short(d.top_host)}</td>
                  <td>{d.countries.map(countryName).join(', ') || '–'}</td>
                  <td class:warn={d.revoked || d.countries.length > 1}>
                    {#if d.revoked}{t('gesperrt, aber noch aktiv')}{:else if d.countries.length > 1}{t('mehrere Länder')}{:else}–{/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}
  {/if}
</AppShell>

<style>
  .small {
    font-size: 13px;
    margin: 0;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .strong {
    font-weight: 600;
  }
  .matrix th[scope='row'] {
    font-weight: 500;
    text-align: left;
    padding-left: 16px;
  }
  .heat {
    display: flex;
    flex-direction: column;
    gap: 3px;
    overflow-x: auto;
  }
  .hours,
  .heat-row {
    display: grid;
    grid-template-columns: 32px repeat(24, minmax(14px, 1fr));
    gap: 3px;
    min-width: 420px;
  }
  .hours span {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .day {
    font-size: 12px;
    color: var(--text-muted);
    align-self: center;
  }
  .cell {
    height: 20px;
    border-radius: 3px;
  }
  .hint {
    min-height: 1.5em;
  }
  .warn {
    color: var(--warn-text);
  }
</style>
