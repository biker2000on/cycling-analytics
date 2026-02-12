import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { Activity, StreamSummaryResponse } from '../api/types.ts';
import client from '../api/client.ts';
import { getStreamSummary } from '../api/streams.ts';
import { getCurrentFtp } from '../api/metrics.ts';
import ActivityHeader from '../components/activities/ActivityHeader.tsx';
import ActivityStats from '../components/activities/ActivityStats.tsx';
import TimelineChart from '../components/charts/TimelineChart.tsx';
import './ActivityDetailPage.css';

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activity, setActivity] = useState<Activity | null>(null);
  const [stream, setStream] = useState<StreamSummaryResponse | null>(null);
  const [ftp, setFtp] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError('');
    try {
      const { data: act } = await client.get<Activity>(`/activities/${id}`);
      setActivity(act);

      // Load stream and FTP in parallel, ignore stream errors (manual activities)
      const [streamResult, ftpResult] = await Promise.allSettled([
        getStreamSummary(Number(id)),
        getCurrentFtp(),
      ]);

      if (streamResult.status === 'fulfilled') {
        setStream(streamResult.value);
      }
      if (ftpResult.status === 'fulfilled') {
        setFtp(ftpResult.value.ftp_watts);
      }
    } catch {
      setError('Failed to load activity');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete() {
    if (!id) return;
    if (!confirm('Delete this activity? This cannot be undone.')) return;
    try {
      await client.delete(`/activities/${id}`);
      navigate('/activities');
    } catch {
      setError('Failed to delete activity');
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <span className="spinner" /> Loading activity...
      </div>
    );
  }

  if (error || !activity) {
    return (
      <div>
        <div className="alert alert-error">{error || 'Activity not found'}</div>
        <button className="btn btn-secondary" onClick={() => navigate('/activities')}>
          Back to Activities
        </button>
      </div>
    );
  }

  return (
    <div className="activity-detail-page">
      <ActivityHeader activity={activity} onDelete={handleDelete} />
      <ActivityStats activity={activity} ftp={ftp} />

      {stream && stream.point_count > 0 ? (
        <TimelineChart stream={stream} ftp={ftp} />
      ) : (
        <div className="card" style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            No stream data available for this activity.
          </p>
        </div>
      )}
    </div>
  );
}
