import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import client from '../api/client.ts';
import type { UserSettings } from '../api/types.ts';
import GarminConnect from '../components/settings/GarminConnect.tsx';
import StravaConnect from '../components/settings/StravaConnect.tsx';

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [ftpInput, setFtpInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    client
      .get<UserSettings>('/settings')
      .then(({ data }) => {
        setSettings(data);
        setFtpInput(data.ftp_watts ? String(data.ftp_watts) : '');
      })
      .catch(() => setError('Failed to load settings'));
  }, []);

  async function handleFtpSave(e: FormEvent) {
    e.preventDefault();
    const watts = parseFloat(ftpInput);
    if (!watts || watts <= 0) {
      setError('Enter a valid FTP value');
      return;
    }

    setSaving(true);
    setError('');
    setMessage('');
    try {
      await client.post('/settings/ftp', { ftp_watts: watts });
      setMessage('FTP updated successfully');
    } catch {
      setError('Failed to update FTP');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 600 }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-lg)' }}>
        Settings
      </h1>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {settings && (
        <div className="card">
          <h2 style={{ fontSize: '1.125rem', marginBottom: 'var(--space-md)' }}>
            Functional Threshold Power
          </h2>
          <form onSubmit={handleFtpSave}>
            <div className="form-group">
              <label className="form-label" htmlFor="ftp">
                FTP (watts)
              </label>
              <input
                id="ftp"
                type="number"
                className="form-input"
                value={ftpInput}
                onChange={(e) => setFtpInput(e.target.value)}
                min={1}
                max={600}
                style={{ maxWidth: 200 }}
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? <span className="spinner" /> : 'Save FTP'}
            </button>
          </form>

          <hr style={{ margin: 'var(--space-lg) 0', borderColor: 'var(--color-border)' }} />

          <h2 style={{ fontSize: '1.125rem', marginBottom: 'var(--space-md)' }}>
            Account Info
          </h2>
          <div style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
            <p>Threshold method: {settings.preferred_threshold_method}</p>
            {settings.weight_kg && <p>Weight: {settings.weight_kg} kg</p>}
          </div>
        </div>
      )}

      {/* ── Integrations ──────────────────────────────────────────── */}
      <h2
        style={{
          fontSize: '1.25rem',
          fontWeight: 600,
          marginTop: 'var(--space-xl)',
          marginBottom: 'var(--space-sm)',
        }}
      >
        Integrations
      </h2>
      <p
        style={{
          fontSize: '0.875rem',
          color: 'var(--color-text-secondary)',
          marginBottom: 'var(--space-md)',
        }}
      >
        Connect external platforms to automatically import your rides.
      </p>

      <GarminConnect />
      <StravaConnect />
    </div>
  );
}
