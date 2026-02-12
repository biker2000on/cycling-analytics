import { useState, useEffect, useRef, useCallback } from 'react';
import { getTaskStatus } from '../api/activities.ts';

interface TaskPollingState {
  status: string;
  progress: number;
  stage: string | null;
  error: string | null;
  isComplete: boolean;
  result: unknown;
}

export function useTaskPolling(taskId: string | null, intervalMs = 2000): TaskPollingState {
  const [state, setState] = useState<TaskPollingState>({
    status: 'PENDING',
    progress: 0,
    stage: null,
    error: null,
    isComplete: false,
    result: null,
  });
  const intervalRef = useRef<number | null>(null);

  const poll = useCallback(async () => {
    if (!taskId) return;
    try {
      const data = await getTaskStatus(taskId);
      const isComplete = data.status === 'SUCCESS' || data.status === 'FAILURE';
      setState({
        status: data.status,
        progress: data.progress ?? 0,
        stage: data.stage ?? null,
        error: data.error ?? null,
        isComplete,
        result: data.result ?? null,
      });
      if (isComplete && intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch {
      // Don't stop polling on transient network errors
    }
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    // Reset state when taskId changes
    setState({
      status: 'PENDING',
      progress: 0,
      stage: null,
      error: null,
      isComplete: false,
      result: null,
    });
    // Immediate first poll, then interval
    poll();
    intervalRef.current = window.setInterval(poll, intervalMs);
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [taskId, intervalMs, poll]);

  return state;
}
