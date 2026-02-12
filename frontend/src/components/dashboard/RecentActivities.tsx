import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Activity } from '../../api/types.ts';
import { getActivities } from '../../api/activities.ts';
import { formatActivityDate, formatDuration, formatDistance } from '../../utils/format.ts';
import './RecentActivities.css';

export default function RecentActivities() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getActivities(5, 0, 'activity_date', 'desc');
        if (!cancelled) {
          setActivities(data.items);
        }
      } catch {
        // Graceful degradation
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="recent-activities card">
      <h3 className="widget-title">Recent Activities</h3>
      {loading ? (
        <div className="loading-state">
          <span className="spinner" /> Loading...
        </div>
      ) : activities.length === 0 ? (
        <div className="widget-empty">No activities yet</div>
      ) : (
        <ul className="recent-list">
          {activities.map((a) => (
            <li
              key={a.id}
              className="recent-item"
              onClick={() => navigate(`/activities/${a.id}`)}
            >
              <div className="recent-item-main">
                <span className="recent-item-name">{a.name}</span>
                <span className="recent-item-date">
                  {formatActivityDate(a.activity_date)}
                </span>
              </div>
              <div className="recent-item-stats">
                {a.duration_seconds != null && (
                  <span className="recent-stat">{formatDuration(a.duration_seconds)}</span>
                )}
                {a.distance_meters != null && (
                  <span className="recent-stat">{formatDistance(a.distance_meters)} km</span>
                )}
                {a.tss != null && (
                  <span className="recent-stat">{Math.round(a.tss)} TSS</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
