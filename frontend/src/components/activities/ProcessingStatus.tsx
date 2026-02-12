import { useEffect, useRef } from 'react';
import { useTaskPolling } from '../../hooks/useTaskPolling.ts';
import './ProcessingStatus.css';

interface Props {
  taskId: string;
  filename: string;
  onComplete?: () => void;
}

/** Map backend stage strings to user-friendly labels. */
function friendlyStage(stage: string | null): string {
  if (!stage) return 'Starting...';
  const lower = stage.toLowerCase();
  if (lower.startsWith('inserting stream data')) return 'Processing ride data';
  if (lower.startsWith('parsing')) return stage;
  if (lower.startsWith('analyzing lap')) return 'Analyzing laps';
  if (lower.startsWith('updating activity')) return 'Finalizing';
  if (lower.startsWith('computing')) return 'Computing metrics';
  return stage;
}

/** Format elapsed seconds as "Xs" or "M:SS". */
function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function ProcessingStatus({ taskId, filename, onComplete }: Props) {
  const { status, progress, stage, error, isComplete } = useTaskPolling(taskId);
  const startRef = useRef(Date.now());
  const elapsedRef = useRef(0);
  const onCompleteCalledRef = useRef(false);

  // Tick elapsed time every second while processing
  useEffect(() => {
    if (isComplete) return;
    const tick = window.setInterval(() => {
      elapsedRef.current = Math.floor((Date.now() - startRef.current) / 1000);
    }, 1000);
    return () => clearInterval(tick);
  }, [isComplete]);

  // Auto-dismiss: call onComplete 3 seconds after SUCCESS
  useEffect(() => {
    if (status === 'SUCCESS' && onComplete && !onCompleteCalledRef.current) {
      onCompleteCalledRef.current = true;
      const timer = setTimeout(onComplete, 3000);
      return () => clearTimeout(timer);
    }
  }, [status, onComplete]);

  if (status === 'SUCCESS') {
    return (
      <div className="processing-status processing-success">
        <span className="processing-check">&#10003;</span> {filename} processed successfully
      </div>
    );
  }

  if (status === 'FAILURE') {
    return (
      <div className="processing-status processing-error">
        <span className="processing-x">&#10007;</span> {filename}: {error ?? 'Unknown error'}
      </div>
    );
  }

  // In-progress states: PENDING, STARTED, PROGRESS
  return (
    <div className="processing-status">
      <div className="processing-header">
        <span className="processing-filename">{filename}</span>
        <span className="processing-elapsed">{formatElapsed(elapsedRef.current)}</span>
      </div>
      <div className="progress-bar-container">
        <div className="progress-bar" style={{ width: `${progress}%` }} />
      </div>
      <div className="processing-stage">
        {friendlyStage(stage)} {progress > 0 ? `${progress}%` : ''}
      </div>
    </div>
  );
}
