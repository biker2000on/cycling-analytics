import { useNavigate } from 'react-router-dom';
import type { Activity } from '../../api/types.ts';
import { formatDateTime } from '../../utils/format.ts';
import './ActivityHeader.css';

interface Props {
  activity: Activity;
  onDelete: () => void;
}

export default function ActivityHeader({ activity, onDelete }: Props) {
  const navigate = useNavigate();

  return (
    <div className="activity-header">
      <div className="activity-header-left">
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/activities')}>
          &larr; Back
        </button>
        <div>
          <h1 className="activity-header-title">{activity.name}</h1>
          <div className="activity-header-meta">
            <span>{formatDateTime(activity.activity_date)}</span>
            {activity.sport_type && (
              <>
                <span className="meta-sep">&middot;</span>
                <span>{activity.sport_type}</span>
              </>
            )}
            {activity.source && (
              <>
                <span className="meta-sep">&middot;</span>
                <span className="source-badge">{activity.source}</span>
              </>
            )}
          </div>
        </div>
      </div>
      <button className="btn btn-danger btn-sm" onClick={onDelete}>
        Delete
      </button>
    </div>
  );
}
