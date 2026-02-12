import client from './client.ts';
import type { StreamResponse, StreamSummaryResponse } from './types.ts';

export async function getActivityStreams(activityId: number): Promise<StreamResponse> {
  const { data } = await client.get<StreamResponse>(`/activities/${activityId}/streams`);
  return data;
}

export async function getStreamSummary(
  activityId: number,
  points = 500,
): Promise<StreamSummaryResponse> {
  const { data } = await client.get<StreamSummaryResponse>(
    `/activities/${activityId}/streams/summary`,
    { params: { points } },
  );
  return data;
}
