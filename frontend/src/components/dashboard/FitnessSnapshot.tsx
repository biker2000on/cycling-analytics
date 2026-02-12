import type { FitnessTimeSeries } from '../../api/types.ts';
import './FitnessSnapshot.css';

interface Props {
  data: FitnessTimeSeries | null;
  loading: boolean;
}

function getTrend(current: number, previous: number): 'up' | 'down' | 'flat' {
  const diff = current - previous;
  if (Math.abs(diff) < 0.5) return 'flat';
  return diff > 0 ? 'up' : 'down';
}

function trendArrow(trend: 'up' | 'down' | 'flat'): string {
  switch (trend) {
    case 'up':
      return '\u25B2'; // triangle up
    case 'down':
      return '\u25BC'; // triangle down
    case 'flat':
      return '\u25C6'; // diamond
  }
}

export default function FitnessSnapshot({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="fitness-snapshot card">
        <div className="loading-state">
          <span className="spinner" /> Loading...
        </div>
      </div>
    );
  }

  if (!data || data.data.length === 0) {
    return (
      <div className="fitness-snapshot card">
        <div className="fitness-snapshot-empty">No fitness data available</div>
      </div>
    );
  }

  const latest = data.data[data.data.length - 1];
  const previous = data.data.length > 1 ? data.data[data.data.length - 2] : latest;

  const ctl = Number(latest.ctl);
  const atl = Number(latest.atl);
  const tsb = Number(latest.tsb);

  const ctlTrend = getTrend(ctl, Number(previous.ctl));
  const atlTrend = getTrend(atl, Number(previous.atl));
  const tsbTrend = getTrend(tsb, Number(previous.tsb));

  return (
    <div className="fitness-snapshot">
      <div className="snapshot-card card">
        <div className="snapshot-label">CTL (Fitness)</div>
        <div className="snapshot-value snapshot-ctl">
          {ctl.toFixed(1)}
          <span className={`snapshot-trend snapshot-trend-${ctlTrend}`}>
            {trendArrow(ctlTrend)}
          </span>
        </div>
      </div>
      <div className="snapshot-card card">
        <div className="snapshot-label">ATL (Fatigue)</div>
        <div className="snapshot-value snapshot-atl">
          {atl.toFixed(1)}
          <span className={`snapshot-trend snapshot-trend-${atlTrend}`}>
            {trendArrow(atlTrend)}
          </span>
        </div>
      </div>
      <div className="snapshot-card card">
        <div className="snapshot-label">TSB (Form)</div>
        <div className={`snapshot-value ${tsb >= 0 ? 'snapshot-tsb-positive' : 'snapshot-tsb-negative'}`}>
          {tsb.toFixed(1)}
          <span className={`snapshot-trend snapshot-trend-${tsbTrend}`}>
            {trendArrow(tsbTrend)}
          </span>
        </div>
      </div>
    </div>
  );
}
