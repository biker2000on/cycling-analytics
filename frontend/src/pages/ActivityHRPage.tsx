import { useState, useEffect, useCallback } from 'react';
import type { HRAnalysisResponse } from '../api/types.ts';
import { getHRAnalysis } from '../api/metrics.ts';
import HRDistribution from '../components/charts/HRDistribution.tsx';
import HRTimeInZone from '../components/charts/HRTimeInZone.tsx';
import { formatHR } from '../utils/format.ts';
import './ActivityHRPage.css';

interface Props {
  activityId: number;
}

export default function ActivityHRPage({ activityId }: Props) {
  const [analysis, setAnalysis] = useState<HRAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await getHRAnalysis(activityId);
      setAnalysis(result);
    } catch {
      setError('Failed to load HR analysis');
    } finally {
      setLoading(false);
    }
  }, [activityId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="loading-state">
        <span className="spinner" /> Loading HR analysis...
      </div>
    );
  }

  if (error || !analysis) {
    return <div className="alert alert-error">{error || 'No HR data available'}</div>;
  }

  return (
    <div className="activity-hr-page">
      {/* HR Stats Card */}
      <div className="card hr-stats-card">
        <h3 className="card-title">Heart Rate Statistics</h3>
        <div className="hr-stats-grid">
          <div className="hr-stat">
            <span className="hr-stat-label">Avg HR</span>
            <span className="hr-stat-value">{formatHR(analysis.avg_hr)}<span className="hr-stat-unit">bpm</span></span>
          </div>
          <div className="hr-stat">
            <span className="hr-stat-label">Max HR</span>
            <span className="hr-stat-value">{formatHR(analysis.max_hr)}<span className="hr-stat-unit">bpm</span></span>
          </div>
          <div className="hr-stat">
            <span className="hr-stat-label">Min HR</span>
            <span className="hr-stat-value">{formatHR(analysis.min_hr)}<span className="hr-stat-unit">bpm</span></span>
          </div>
          <div className="hr-stat">
            <span className="hr-stat-label">Max HR Setting</span>
            <span className="hr-stat-value">{analysis.max_hr_setting}<span className="hr-stat-unit">bpm</span></span>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="hr-charts-grid">
        <div className="card hr-chart-card">
          <HRDistribution distribution={analysis.distribution} />
        </div>
        <div className="card hr-chart-card">
          <HRTimeInZone zones={analysis.time_in_zones} />
        </div>
      </div>
    </div>
  );
}
