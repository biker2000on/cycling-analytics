import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore.ts';
import * as authApi from '../api/auth.ts';
import './AuthPages.css';

type Step = 'account' | 'ftp';

export default function SetupWizardPage() {
  const [step, setStep] = useState<Step>('account');
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');

  // Account fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  // FTP field
  const [ftpWatts, setFtpWatts] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  useEffect(() => {
    authApi
      .checkSetup()
      .then((status) => {
        if (status.setup_complete) {
          navigate('/login');
        }
        setChecking(false);
      })
      .catch(() => {
        setChecking(false);
      });
  }, [navigate]);

  async function handleAccountSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setStep('ftp');
  }

  async function handleFtpSubmit(e: FormEvent) {
    e.preventDefault();
    await completeSetup();
  }

  async function completeSetup() {
    setSubmitting(true);
    setError('');
    try {
      const ftp = ftpWatts ? parseFloat(ftpWatts) : undefined;
      const tokenData = await authApi.initialSetup({
        email,
        password,
        display_name: displayName.trim(),
        ftp_watts: ftp && ftp > 0 ? ftp : null,
      });

      setTokens(tokenData.access_token, tokenData.refresh_token);
      const user = await authApi.getCurrentUser();
      setUser(user);

      navigate('/activities');
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Setup failed';
      setError(message);
      setSubmitting(false);
    }
  }

  if (checking) {
    return (
      <div className="auth-page">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="setup-page">
      <div className="setup-card card">
        <h1 className="auth-title">Welcome to Cycling Analytics</h1>
        <p className="auth-subtitle">Let's set up your instance</p>

        <div className="setup-steps">
          <div className={`setup-step ${step === 'account' ? 'active' : 'done'}`} />
          <div className={`setup-step ${step === 'ftp' ? 'active' : ''}`} />
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        {step === 'account' && (
          <form onSubmit={handleAccountSubmit}>
            <h2 style={{ fontSize: '1.125rem', marginBottom: 'var(--space-md)' }}>
              Create Admin Account
            </h2>

            <div className="form-group">
              <label className="form-label" htmlFor="displayName">
                Display Name
              </label>
              <input
                id="displayName"
                type="text"
                className="form-input"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="confirmPassword">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                className="form-input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary btn-block btn-lg">
              Continue
            </button>
          </form>
        )}

        {step === 'ftp' && (
          <form onSubmit={handleFtpSubmit}>
            <h2 style={{ fontSize: '1.125rem', marginBottom: 'var(--space-md)' }}>
              Set Your FTP (Optional)
            </h2>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-md)' }}>
              Functional Threshold Power in watts. You can change this later in Settings.
            </p>

            <div className="form-group">
              <label className="form-label" htmlFor="ftp">
                FTP (watts)
              </label>
              <input
                id="ftp"
                type="number"
                className="form-input"
                value={ftpWatts}
                onChange={(e) => setFtpWatts(e.target.value)}
                min={1}
                max={600}
                placeholder="e.g. 250"
                autoFocus
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block btn-lg"
              disabled={submitting}
            >
              {submitting ? <span className="spinner" /> : 'Complete Setup'}
            </button>

            <div className="setup-skip">
              <button type="button" onClick={() => completeSetup()} disabled={submitting}>
                Skip, I'll set this later
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
