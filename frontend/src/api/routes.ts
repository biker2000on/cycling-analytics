import client from './client.ts';
import type { RouteGeoJSON } from './types.ts';

export async function getActivityRoute(activityId: number): Promise<RouteGeoJSON> {
  const { data } = await client.get<RouteGeoJSON>(`/activities/${activityId}/route`);
  return data;
}
