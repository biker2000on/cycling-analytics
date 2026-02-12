import type { PeakEffort } from '../../api/types.ts';
import './PeakEffortsTable.css';

interface Props {
  efforts: PeakEffort[];
}

export default function PeakEffortsTable({ efforts }: Props) {
  if (efforts.length === 0) {
    return <div className="chart-empty">No peak effort data available.</div>;
  }

  return (
    <div className="peak-efforts">
      <h4 className="chart-subtitle">Peak Efforts</h4>
      <table className="peak-efforts-table">
        <thead>
          <tr>
            <th>Duration</th>
            <th>Power (W)</th>
            <th>Power (W/kg)</th>
          </tr>
        </thead>
        <tbody>
          {efforts.map((e) => (
            <tr key={e.duration_seconds}>
              <td>{e.duration_label}</td>
              <td className="peak-value">
                {e.power_watts != null ? Math.round(Number(e.power_watts)) : '--'}
              </td>
              <td className="peak-value">
                {e.power_wpkg != null ? Number(e.power_wpkg).toFixed(2) : '--'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
