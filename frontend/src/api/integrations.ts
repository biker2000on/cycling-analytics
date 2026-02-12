import client from './client.ts';

// ── Types ────────────────────────────────────────────────────────────────

export interface GarminStatus {
  id: number;
  provider: string;
  sync_enabled: boolean;
  last_sync_at: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface StravaStatus {
  connected: boolean;
  athlete_id: number | null;
  last_sync: string | null;
}

export interface TaskResponse {
  task_id: string;
}

// ── Garmin ────────────────────────────────────────────────────────────────

export async function connectGarmin(
  email: string,
  password: string,
): Promise<GarminStatus> {
  const { data } = await client.post<GarminStatus>(
    '/integrations/garmin/connect',
    { email, password },
  );
  return data;
}

export async function getGarminStatus(): Promise<GarminStatus> {
  const { data } = await client.get<GarminStatus>(
    '/integrations/garmin/status',
  );
  return data;
}

export async function disconnectGarmin(): Promise<void> {
  await client.delete('/integrations/garmin/disconnect');
}

export async function triggerGarminSync(
  days?: number,
): Promise<TaskResponse> {
  const params = days ? { days } : {};
  const { data } = await client.post<TaskResponse>(
    '/integrations/garmin/sync',
    null,
    { params },
  );
  return data;
}

export async function triggerGarminBackfill(
  days: number,
): Promise<TaskResponse> {
  const { data } = await client.post<TaskResponse>(
    '/integrations/garmin/backfill',
    null,
    { params: { days } },
  );
  return data;
}

// ── Strava ────────────────────────────────────────────────────────────────

export async function getStravaAuthUrl(): Promise<string> {
  const { data } = await client.get<{ url: string }>(
    '/integrations/strava/authorize',
  );
  return data.url;
}

export async function getStravaStatus(): Promise<StravaStatus> {
  const { data } = await client.get<StravaStatus>(
    '/integrations/strava/status',
  );
  return data;
}

export async function disconnectStrava(): Promise<void> {
  await client.delete('/integrations/strava/disconnect');
}

export async function triggerStravaSync(): Promise<TaskResponse> {
  const { data } = await client.post<TaskResponse>(
    '/integrations/strava/sync',
  );
  return data;
}

export async function triggerStravaBackfill(
  days: number,
): Promise<TaskResponse> {
  const { data } = await client.post<TaskResponse>(
    '/integrations/strava/backfill',
    null,
    { params: { days } },
  );
  return data;
}
