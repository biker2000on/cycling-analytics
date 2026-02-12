import { useEffect, useState, useCallback } from 'react';
import type { TotalsResponse } from '../api/types.ts';
import { getTotals } from '../api/metrics.ts';
import TotalsBarChart from '../components/charts/TotalsBarChart.tsx';
import TotalsSummaryCards from '../components/charts/TotalsSummaryCards.tsx';
import PeriodSelector from '../components/charts/PeriodSelector.tsx';
import DateRangePicker from '../components/charts/DateRangePicker.tsx';
import type { DateRangePreset } from '../stores/metricsStore.ts';
import { format, subDays, subMonths, subYears } from 'date-fns';
import './TotalsPage.css';

function getDefaultRange(period: string): { startDate: string; endDate: string } {
  const today = new Date();
  const endDate = format(today, 'yyyy-MM-dd');
  let startDate: string;
  switch (period) {
    case 'weekly':
      startDate = format(subDays(today, 90), 'yyyy-MM-dd');
      break;
    case 'monthly':
      startDate = format(subYears(today, 1), 'yyyy-MM-dd');
      break;
    case 'yearly':
      startDate = format(subYears(today, 3), 'yyyy-MM-dd');
      break;
    default:
      startDate = format(subDays(today, 90), 'yyyy-MM-dd');
  }
  return { startDate, endDate };
}

function getDateRange(preset: DateRangePreset): { startDate: string; endDate: string } {
  const today = new Date();
  const endDate = format(today, 'yyyy-MM-dd');
  let startDate: string;
  switch (preset) {
    case '30d':
      startDate = format(subDays(today, 30), 'yyyy-MM-dd');
      break;
    case '90d':
      startDate = format(subDays(today, 90), 'yyyy-MM-dd');
      break;
    case '6m':
      startDate = format(subMonths(today, 6), 'yyyy-MM-dd');
      break;
    case '1y':
      startDate = format(subYears(today, 1), 'yyyy-MM-dd');
      break;
    case 'all':
      startDate = '2000-01-01';
      break;
  }
  return { startDate, endDate };
}

export default function TotalsPage() {
  const [period, setPeriod] = useState('weekly');
  const [data, setData] = useState<TotalsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preset, setPreset] = useState<DateRangePreset>('90d');
  const [startDate, setStartDate] = useState(() => getDefaultRange('weekly').startDate);
  const [endDate, setEndDate] = useState(() => getDefaultRange('weekly').endDate);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getTotals(period, startDate, endDate);
      setData(result);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load totals data';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [period, startDate, endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function handlePeriodChange(newPeriod: string) {
    setPeriod(newPeriod);
    const range = getDefaultRange(newPeriod);
    setStartDate(range.startDate);
    setEndDate(range.endDate);
    // Reset preset to match
    if (newPeriod === 'weekly') setPreset('90d');
    else if (newPeriod === 'monthly') setPreset('1y');
    else setPreset('all');
  }

  function handlePresetChange(p: DateRangePreset) {
    const range = getDateRange(p);
    setPreset(p);
    setStartDate(range.startDate);
    setEndDate(range.endDate);
  }

  function handleCustomChange(s: string, e: string) {
    setPreset('all');
    setStartDate(s);
    setEndDate(e);
  }

  return (
    <div className="totals-page">
      <div className="page-header">
        <h1 className="page-title">Training Totals</h1>
      </div>

      {/* Summary Cards */}
      {data && !loading && (
        <TotalsSummaryCards periods={data.periods} />
      )}

      {/* Controls */}
      <div className="card totals-controls">
        <div className="totals-controls-row">
          <PeriodSelector value={period} onChange={handlePeriodChange} />
          <DateRangePicker
            preset={preset}
            startDate={startDate}
            endDate={endDate}
            onPresetChange={handlePresetChange}
            onCustomChange={handleCustomChange}
          />
        </div>
      </div>

      {/* Bar Chart */}
      <div className="card totals-chart-card">
        <h2 className="totals-section-title">Trends by {period.charAt(0).toUpperCase() + period.slice(1)} Period</h2>
        {error && <div className="alert alert-error">{error}</div>}
        {loading ? (
          <div className="loading-state">
            <span className="spinner" /> Loading totals...
          </div>
        ) : data ? (
          <TotalsBarChart periods={data.periods} />
        ) : null}
      </div>
    </div>
  );
}
