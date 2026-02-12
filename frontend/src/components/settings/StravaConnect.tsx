import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Swal from 'sweetalert2';
import {
  getStravaAuthUrl,
  getStravaStatus,
  disconnectStrava,
  triggerStravaSync,
  triggerStravaBackfill,
} from '../../api/integrations.ts';
import type { StravaStatus } from '../../api/integrations.ts';
import { useTaskPolling } from '../../hooks/useTaskPolling.ts';
import BackfillSelector from './BackfillSelector.tsx';
import './StravaConnect.css';

function formatDate(iso: string | null): string {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleString();
}

export default function StravaConnect() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<StravaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // OAuth redirect
  const [redirecting, setRedirecting] = useState(false);

  // Sync state
  const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const syncTask = useTaskPolling(syncTaskId);

  useEffect(() => {
    loadStatus();
  }, []);

  // Handle OAuth callback query params
  useEffect(() => {
    const connected = searchParams.get('strava_connected');
    const stravaError = searchParams.get('strava_error');

    if (connected === 'true') {
      setMessage('Strava connected successfully!');
      // Reload status to reflect connection
      loadStatus();
      // Clear URL params
      searchParams.delete('strava_connected');
      searchParams.delete('athlete_id');
      setSearchParams(searchParams, { replace: true });
    } else if (stravaError) {
      setError(`Strava authorization failed: ${stravaError}`);
      searchParams.delete('strava_error');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadStatus() {
    setLoading(true);
    try {
      const data = await getStravaStatus();
      setStatus(data);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect() {
    setRedirecting(true);
    setError('');
    try {
      const url = await getStravaAuthUrl();
      window.location.href = url;
    } catch {
      setError('Failed to start Strava authorization');
      setRedirecting(false);
    }
  }

  async function handleDisconnect() {
    const result = await Swal.fire({
      title: 'Disconnect Strava?',
      text: 'Your imported activities will be kept.',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Disconnect',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#d33',
    });
    if (!result.isConfirmed) return;
    try {
      await disconnectStrava();
      setStatus(null);
      setSyncTaskId(null);
      setMessage('');
    } catch {
      setError('Failed to disconnect');
    }
  }

  async function handleSync() {
    setSyncing(true);
    setSyncTaskId(null);
    try {
      const resp = await triggerStravaSync();
      setSyncTaskId(resp.task_id);
    } catch {
      setError('Failed to start sync');
    } finally {
      setSyncing(false);
    }
  }

  // Refresh status after sync completes successfully
  useEffect(() => {
    if (syncTask.status === 'SUCCESS') {
      loadStatus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncTask.status]);

  if (loading) {
    return (
      <div className="card strava-card">
        <div className="strava-header">
          <span className="strava-title">Strava</span>
          <span className="strava-badge strava-badge--disconnected">Loading...</span>
        </div>
      </div>
    );
  }

  const isConnected = status?.connected === true;
  const isSyncRunning = syncTaskId !== null && !syncTask.isComplete;

  return (
    <div className="card strava-card">
      <div className="strava-header">
        <span className="strava-title">Strava</span>
        {isConnected ? (
          <span className="strava-badge strava-badge--connected">Connected</span>
        ) : (
          <span className="strava-badge strava-badge--disconnected">
            Not connected
          </span>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {/* ── Connected view ──────────────────────────────────────────── */}
      {isConnected && status && (
        <>
          <div className="strava-info">
            {status.athlete_id && <p>Athlete ID: {status.athlete_id}</p>}
            <p>Last sync: {formatDate(status.last_sync)}</p>
          </div>

          <div className="strava-actions">
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSync}
              disabled={syncing || isSyncRunning}
            >
              {syncing ? <span className="spinner" /> : 'Sync Now'}
            </button>
            <button
              className="btn btn-danger btn-sm"
              onClick={handleDisconnect}
            >
              Disconnect
            </button>
          </div>

          {/* Sync progress */}
          {isSyncRunning && (
            <div className="strava-sync-progress">
              <div className="strava-sync-bar-track">
                <div
                  className="strava-sync-bar-fill"
                  style={{ width: `${syncTask.progress}%` }}
                />
              </div>
              <div className="strava-sync-text">
                {syncTask.stage ?? 'Starting sync...'}{' '}
                {syncTask.progress > 0 ? `${syncTask.progress}%` : ''}
              </div>
            </div>
          )}

          {syncTaskId && syncTask.status === 'SUCCESS' && (
            <div className="strava-sync-success">Sync completed.</div>
          )}

          {syncTaskId && syncTask.status === 'FAILURE' && (
            <div className="strava-sync-error">
              Sync failed: {syncTask.error ?? 'Unknown error'}
            </div>
          )}

          {/* Backfill */}
          <BackfillSelector onBackfill={triggerStravaBackfill} />
        </>
      )}

      {/* ── Disconnected / Connect ──────────────────────────────────── */}
      {!isConnected && (
        <>
          <p className="strava-connect-text">
            Connect your Strava account to automatically import activities.
          </p>
          <button
            className="btn btn-strava"
            onClick={handleConnect}
            disabled={redirecting}
          >
            {redirecting ? <span className="spinner" /> : 'Connect with Strava'}
          </button>
        </>
      )}
    </div>
  );
}
