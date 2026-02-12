import { useState } from 'react';
import { useTaskPolling } from '../../hooks/useTaskPolling.ts';
import type { TaskResponse } from '../../api/integrations.ts';
import './BackfillSelector.css';

const PERIODS = [
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '6 months', days: 180 },
  { label: '1 year', days: 365 },
  { label: '2 years', days: 730 },
  { label: 'All time', days: 3650 },
] as const;

interface Props {
  onBackfill: (days: number) => Promise<TaskResponse>;
  label?: string;
}

export default function BackfillSelector({
  onBackfill,
  label = 'Historical Import',
}: Props) {
  const [days, setDays] = useState(90);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  const task = useTaskPolling(taskId);

  async function handleBackfill() {
    setStarting(true);
    setStartError('');
    try {
      const resp = await onBackfill(days);
      setTaskId(resp.task_id);
    } catch {
      setStartError('Failed to start backfill');
    } finally {
      setStarting(false);
    }
  }

  const isRunning = taskId !== null && !task.isComplete;
  const showWarning = days > 365;

  return (
    <div className="backfill">
      <span className="backfill-label">{label}</span>

      <div className="backfill-row">
        <select
          className="backfill-select"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          disabled={isRunning}
        >
          {PERIODS.map((p) => (
            <option key={p.days} value={p.days}>
              {p.label}
            </option>
          ))}
        </select>

        <button
          className="btn btn-secondary btn-sm"
          onClick={handleBackfill}
          disabled={isRunning || starting}
        >
          {starting ? <span className="spinner" /> : 'Start Backfill'}
        </button>
      </div>

      {showWarning && !isRunning && (
        <div className="backfill-warning">
          Large backfills may take several minutes.
        </div>
      )}

      {startError && <div className="backfill-error">{startError}</div>}

      {isRunning && (
        <div className="backfill-progress">
          <div className="backfill-progress-bar-track">
            <div
              className="backfill-progress-bar-fill"
              style={{ width: `${task.progress}%` }}
            />
          </div>
          <div className="backfill-progress-text">
            {task.stage ?? 'Starting...'}{' '}
            {task.progress > 0 ? `${task.progress}%` : ''}
          </div>
        </div>
      )}

      {taskId && task.status === 'SUCCESS' && (
        <div className="backfill-success">Backfill completed successfully.</div>
      )}

      {taskId && task.status === 'FAILURE' && (
        <div className="backfill-error">
          Backfill failed: {task.error ?? 'Unknown error'}
        </div>
      )}
    </div>
  );
}
