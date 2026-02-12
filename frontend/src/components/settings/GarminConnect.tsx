import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import Swal from 'sweetalert2';
import {
  connectGarmin,
  getGarminStatus,
  disconnectGarmin,
  triggerGarminSync,
  triggerGarminBackfill,
} from '../../api/integrations.ts';
import type { GarminStatus } from '../../api/integrations.ts';
import { useTaskPolling } from '../../hooks/useTaskPolling.ts';
import BackfillSelector from './BackfillSelector.tsx';
import './GarminConnect.css';

function formatDate(iso: string | null): string {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleString();
}

export default function GarminConnect() {
  const [status, setStatus] = useState<GarminStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Connect form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [connecting, setConnecting] = useState(false);

  // Sync state
  const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const syncTask = useTaskPolling(syncTaskId);

  useEffect(() => {
    loadStatus();
  }, []);

  async function loadStatus() {
    setLoading(true);
    try {
      const data = await getGarminStatus();
      setStatus(data);
    } catch {
      // No integration yet -- that's fine, show connect form
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('Email and password are required');
      return;
    }

    setConnecting(true);
    setError('');
    try {
      const data = await connectGarmin(email.trim(), password);
      setStatus(data);
      // Clear sensitive data from state
      setEmail('');
      setPassword('');
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to connect';
      // Try to extract backend message from axios error
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail ?? msg);
    } finally {
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    const result = await Swal.fire({
      title: 'Disconnect Garmin Connect?',
      text: 'Your imported activities will be kept.',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Disconnect',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#d33',
    });
    if (!result.isConfirmed) return;
    try {
      await disconnectGarmin();
      setStatus(null);
      setSyncTaskId(null);
    } catch {
      setError('Failed to disconnect');
    }
  }

  async function handleSync() {
    setSyncing(true);
    setSyncTaskId(null);
    try {
      const resp = await triggerGarminSync();
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
      <div className="card garmin-card">
        <div className="garmin-header">
          <span className="garmin-title">Garmin Connect</span>
          <span className="garmin-badge garmin-badge--disconnected">Loading...</span>
        </div>
      </div>
    );
  }

  const isConnected = status !== null;
  const isActive = status?.status === 'active';
  const isSyncRunning = syncTaskId !== null && !syncTask.isComplete;

  return (
    <div className="card garmin-card">
      <div className="garmin-header">
        <span className="garmin-title">Garmin Connect</span>
        {!isConnected && (
          <span className="garmin-badge garmin-badge--disconnected">
            Not connected
          </span>
        )}
        {isConnected && isActive && (
          <span className="garmin-badge garmin-badge--active">Active</span>
        )}
        {isConnected && !isActive && (
          <span className="garmin-badge garmin-badge--error">Error</span>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* ── Connected view ──────────────────────────────────────────── */}
      {isConnected && (
        <>
          <div className="garmin-info">
            <p>Last sync: {formatDate(status.last_sync_at)}</p>
            <p>Connected: {formatDate(status.created_at)}</p>
            {status.error_message && (
              <p className="garmin-error-msg">{status.error_message}</p>
            )}
          </div>

          <div className="garmin-actions">
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
            <div className="garmin-sync-progress">
              <div className="garmin-sync-bar-track">
                <div
                  className="garmin-sync-bar-fill"
                  style={{ width: `${syncTask.progress}%` }}
                />
              </div>
              <div className="garmin-sync-text">
                {syncTask.stage ?? 'Starting sync...'}{' '}
                {syncTask.progress > 0 ? `${syncTask.progress}%` : ''}
              </div>
            </div>
          )}

          {syncTaskId && syncTask.status === 'SUCCESS' && (
            <div className="garmin-sync-success">Sync completed.</div>
          )}

          {syncTaskId && syncTask.status === 'FAILURE' && (
            <div className="garmin-sync-error">
              Sync failed: {syncTask.error ?? 'Unknown error'}
            </div>
          )}

          {/* Backfill */}
          <BackfillSelector onBackfill={triggerGarminBackfill} />
        </>
      )}

      {/* ── Disconnected / Connect form ─────────────────────────────── */}
      {!isConnected && (
        <>
          <p className="garmin-connect-text">
            Connect your Garmin account to automatically import activities.
          </p>
          <form onSubmit={handleConnect}>
            <div className="form-group">
              <label className="form-label" htmlFor="garmin-email">
                Garmin Email
              </label>
              <input
                id="garmin-email"
                type="email"
                className="form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="garmin-password">
                Garmin Password
              </label>
              <input
                id="garmin-password"
                type="password"
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={connecting}
            >
              {connecting ? <span className="spinner" /> : 'Connect'}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
