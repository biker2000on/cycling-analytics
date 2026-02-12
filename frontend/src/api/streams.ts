import client from './client.ts';
import type { StreamResponse, StreamSummaryResponse, ZoneBlocksResponse } from './types.ts';

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

export async function getStreamZoneBlocks(
  activityId: number,
  ftp: number,
): Promise<ZoneBlocksResponse> {
  const { data } = await client.get<ZoneBlocksResponse>(
    `/activities/${activityId}/streams/zones`,
    { params: { ftp } },
  );
  return data;
}
