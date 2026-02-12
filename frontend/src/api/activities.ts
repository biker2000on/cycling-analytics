import client from './client.ts';
import type { ActivityListResponse, ActivityUploadResponse } from './types.ts';

export async function getActivities(
  limit = 25,
  offset = 0,
  sortField = 'activity_date',
  sortDir = 'desc',
): Promise<ActivityListResponse> {
  const { data } = await client.get<ActivityListResponse>('/activities', {
    params: { limit, offset, sort: sortField, order: sortDir },
  });
  return data;
}

export async function uploadFit(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<ActivityUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await client.post<ActivityUploadResponse>(
    '/activities/upload-fit',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress(Math.round((event.loaded * 100) / event.total));
        }
      },
    },
  );
  return data;
}

export async function deleteActivity(id: number): Promise<void> {
  await client.delete(`/activities/${id}`);
}
