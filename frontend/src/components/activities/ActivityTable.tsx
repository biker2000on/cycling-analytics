import { useNavigate } from 'react-router-dom';
import type { Activity } from '../../api/types.ts';
import {
  formatActivityDate,
  formatDuration,
  formatDecimal1,
  formatDecimal2,
} from '../../utils/format.ts';
import { useUnits } from '../../hooks/useUnits.ts';
import './ActivityTable.css';

type SortField = 'activity_date' | 'duration_seconds' | 'distance_meters' | 'tss' | 'name';

interface Props {
  activities: Activity[];
  sortField: SortField;
  sortDir: 'asc' | 'desc';
  onSort: (field: SortField) => void;
}

export default function ActivityTable({ activities, sortField, sortDir, onSort }: Props) {
  const navigate = useNavigate();
  const { formatDistance, distanceUnit } = useUnits();

  function sortIndicator(field: SortField) {
    if (sortField !== field) return '';
    return sortDir === 'asc' ? ' \u25B2' : ' \u25BC';
  }

  return (
    <div className="activity-table-wrapper">
      <table className="activity-table">
        <thead>
          <tr>
            <th className="sortable" onClick={() => onSort('activity_date')}>
              Date{sortIndicator('activity_date')}
            </th>
            <th className="sortable" onClick={() => onSort('name')}>
              Name{sortIndicator('name')}
            </th>
            <th>Sport</th>
            <th className="sortable num" onClick={() => onSort('duration_seconds')}>
              Duration{sortIndicator('duration_seconds')}
            </th>
            <th className="num sortable" onClick={() => onSort('distance_meters')}>
              Distance ({distanceUnit}){sortIndicator('distance_meters')}
            </th>
            <th className="num sortable" onClick={() => onSort('tss')}>
              TSS{sortIndicator('tss')}
            </th>
            <th className="num">NP</th>
            <th className="num">IF</th>
          </tr>
        </thead>
        <tbody>
          {activities.map((a) => (
            <tr key={a.id} className="activity-row" onClick={() => navigate(`/activities/${a.id}`)}>
              <td>{formatActivityDate(a.activity_date)}</td>
              <td className="activity-name">{a.name}</td>
              <td>{a.sport_type ?? '--'}</td>
              <td className="num">{formatDuration(a.duration_seconds)}</td>
              <td className="num">{formatDistance(a.distance_meters)}</td>
              <td className="num">{formatDecimal1(a.tss)}</td>
              <td className="num">{a.np_watts != null ? Math.round(a.np_watts) : '--'}</td>
              <td className="num">{formatDecimal2(a.intensity_factor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
