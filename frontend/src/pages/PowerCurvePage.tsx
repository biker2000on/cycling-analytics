import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { PowerCurveResponse, PowerCurvePoint } from '../api/types.ts';
import { getPowerCurve } from '../api/metrics.ts';
import PowerCurveChart from '../components/charts/PowerCurveChart.tsx';
import DateRangePicker from '../components/charts/DateRangePicker.tsx';
import type { DateRangePreset } from '../stores/metricsStore.ts';
import { format, subDays, subMonths, subYears } from 'date-fns';
import './PowerCurvePage.css';

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

export default function PowerCurvePage() {
  const [data, setData] = useState<PowerCurveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preset, setPreset] = useState<DateRangePreset>('90d');
  const [startDate, setStartDate] = useState(() => getDateRange('90d').startDate);
  const [endDate, setEndDate] = useState(() => getDateRange('90d').endDate);
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getPowerCurve(startDate, endDate);
      setData(result);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load power curve';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  function handlePointClick(point: PowerCurvePoint) {
    navigate(`/activities/${point.activity_id}`);
  }

  return (
    <div className="power-curve-page">
      <div className="page-header">
        <h1 className="page-title">Power Curve</h1>
      </div>

      <div className="card power-curve-controls">
        <DateRangePicker
          preset={preset}
          startDate={startDate}
          endDate={endDate}
          onPresetChange={handlePresetChange}
          onCustomChange={handleCustomChange}
        />
      </div>

      <div className="card power-curve-chart-card">
        <h2 className="power-curve-section-title">Mean-Max Power Curve</h2>
        <p className="power-curve-description">
          Best average power for each duration across all activities. Click a point to view the source activity.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        {loading ? (
          <div className="loading-state">
            <span className="spinner" /> Loading power curve...
          </div>
        ) : data ? (
          <PowerCurveChart data={data.data} onPointClick={handlePointClick} />
        ) : null}
      </div>
    </div>
  );
}
