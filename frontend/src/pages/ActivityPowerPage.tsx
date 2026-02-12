import { useState, useEffect, useCallback } from 'react';
import type { PowerAnalysisResponse, StreamResponse } from '../api/types.ts';
import { getPowerAnalysis } from '../api/metrics.ts';
import { getActivityStreams } from '../api/streams.ts';
import PowerDistribution from '../components/charts/PowerDistribution.tsx';
import PeakEffortsTable from '../components/charts/PeakEffortsTable.tsx';
import PowerScatterPlot from '../components/charts/PowerScatterPlot.tsx';
import ZoneLegend from '../components/charts/ZoneLegend.tsx';
import { formatWatts, formatDecimal1, formatDecimal2 } from '../utils/format.ts';
import './ActivityPowerPage.css';

interface Props {
  activityId: number;
  ftp: number | null;
}

export default function ActivityPowerPage({ activityId, ftp }: Props) {
  const [analysis, setAnalysis] = useState<PowerAnalysisResponse | null>(null);
  const [stream, setStream] = useState<StreamResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [analysisResult, streamResult] = await Promise.allSettled([
        getPowerAnalysis(activityId, ftp ?? 0),
        getActivityStreams(activityId),
      ]);

      if (analysisResult.status === 'fulfilled') {
        setAnalysis(analysisResult.value);
      } else {
        setError('Failed to load power analysis');
      }

      if (streamResult.status === 'fulfilled') {
        setStream(streamResult.value);
      }
    } catch {
      setError('Failed to load power analysis');
    } finally {
      setLoading(false);
    }
  }, [activityId, ftp]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="loading-state">
        <span className="spinner" /> Loading power analysis...
      </div>
    );
  }

  if (error || !analysis) {
    return <div className="alert alert-error">{error || 'No power data available'}</div>;
  }

  const { stats } = analysis;

  return (
    <div className="activity-power-page">
      {/* Advanced Stats Card */}
      <div className="card power-stats-card">
        <h3 className="card-title">Power Statistics</h3>
        {ftp && <ZoneLegend ftp={analysis.ftp} />}
        <div className="power-stats-grid">
          <div className="power-stat">
            <span className="power-stat-label">NP</span>
            <span className="power-stat-value">{formatWatts(stats.normalized_power)}<span className="power-stat-unit">W</span></span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">Avg Power</span>
            <span className="power-stat-value">{formatWatts(stats.avg_power)}<span className="power-stat-unit">W</span></span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">Max Power</span>
            <span className="power-stat-value">{formatWatts(stats.max_power)}<span className="power-stat-unit">W</span></span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">VI</span>
            <span className="power-stat-value">{formatDecimal2(stats.variability_index)}</span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">IF</span>
            <span className="power-stat-value">{formatDecimal2(stats.intensity_factor)}</span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">TSS</span>
            <span className="power-stat-value">{formatDecimal1(stats.tss)}</span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">Work</span>
            <span className="power-stat-value">{formatDecimal1(stats.work_kj)}<span className="power-stat-unit">kJ</span></span>
          </div>
          <div className="power-stat">
            <span className="power-stat-label">W/kg</span>
            <span className="power-stat-value">{formatDecimal2(stats.watts_per_kg)}</span>
          </div>
        </div>
      </div>

      {/* Two-column layout for charts */}
      <div className="power-charts-grid">
        <div className="card power-chart-card">
          <PowerDistribution distribution={analysis.distribution} />
        </div>
        <div className="card power-chart-card">
          <PeakEffortsTable efforts={analysis.peak_efforts} />
        </div>
      </div>

      {/* Power vs HR scatter plot */}
      {stream && (
        <div className="card power-chart-card">
          <PowerScatterPlot stream={stream} />
        </div>
      )}
    </div>
  );
}
