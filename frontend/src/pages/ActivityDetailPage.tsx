import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Swal from 'sweetalert2';
import type { Activity, StreamSummaryResponse } from '../api/types.ts';
import client from '../api/client.ts';
import { getStreamSummary } from '../api/streams.ts';
import { getCurrentFtp } from '../api/metrics.ts';
import { reprocessActivity } from '../api/activities.ts';
import ActivityHeader from '../components/activities/ActivityHeader.tsx';
import ActivityStats from '../components/activities/ActivityStats.tsx';
import ZoneShadedTimeline from '../components/charts/ZoneShadedTimeline.tsx';
import ActivityPowerPage from './ActivityPowerPage.tsx';
import ActivityHRPage from './ActivityHRPage.tsx';
import ActivityMapPage from './ActivityMapPage.tsx';
import './ActivityDetailPage.css';

type TabKey = 'overview' | 'power' | 'hr' | 'map';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'power', label: 'Power' },
  { key: 'hr', label: 'Heart Rate' },
  { key: 'map', label: 'Map' },
];

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activity, setActivity] = useState<Activity | null>(null);
  const [stream, setStream] = useState<StreamSummaryResponse | null>(null);
  const [ftp, setFtp] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [reprocessing, setReprocessing] = useState(false);

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
    const result = await Swal.fire({
      title: 'Delete Activity?',
      text: 'This cannot be undone.',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#d33',
    });
    if (!result.isConfirmed) return;
    try {
      await client.delete(`/activities/${id}`);
      navigate('/activities');
    } catch {
      setError('Failed to delete activity');
    }
  }

  async function handleReprocess() {
    if (!id) return;
    const result = await Swal.fire({
      title: 'Reprocess Activity?',
      text: 'This will re-parse the original FIT file and rebuild all streams and laps.',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Reprocess',
      cancelButtonText: 'Cancel',
    });
    if (!result.isConfirmed) return;
    setReprocessing(true);
    setError('');
    try {
      await reprocessActivity(Number(id));
      // Refetch activity to show updated status
      await load();
    } catch (err) {
      setError('Failed to reprocess activity');
    } finally {
      setReprocessing(false);
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

  const activityId = Number(id);

  return (
    <div className="activity-detail-page">
      <ActivityHeader
        activity={activity}
        onDelete={handleDelete}
        onReprocess={handleReprocess}
        reprocessing={reprocessing}
      />
      <ActivityStats activity={activity} ftp={ftp} />

      {/* Tab Navigation */}
      <div className="activity-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`activity-tab ${activeTab === tab.key ? 'activity-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="activity-tab-content">
        {activeTab === 'overview' && (
          <>
            {stream && stream.point_count > 0 ? (
              <ZoneShadedTimeline stream={stream} ftp={ftp} activityId={activityId} />
            ) : (
              <div className="card" style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
                <p style={{ color: 'var(--color-text-secondary)' }}>
                  No stream data available for this activity.
                </p>
              </div>
            )}
          </>
        )}

        {activeTab === 'power' && (
          <ActivityPowerPage activityId={activityId} ftp={ftp} />
        )}

        {activeTab === 'hr' && (
          <ActivityHRPage activityId={activityId} />
        )}

        {activeTab === 'map' && (
          <ActivityMapPage activityId={activityId} stream={stream} />
        )}
      </div>
    </div>
  );
}
