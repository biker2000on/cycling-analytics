import client from './client.ts';
import type {
  ActivityListResponse,
  ActivityUploadResponse,
  MultiUploadResponse,
  TaskStatus,
} from './types.ts';

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

export async function uploadMultiple(
  files: File[],
  onProgress?: (percent: number) => void,
): Promise<MultiUploadResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));

  const { data } = await client.post<MultiUploadResponse>(
    '/activities/upload',
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

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const { data } = await client.get<TaskStatus>(`/tasks/${taskId}`);
  return data;
}

export async function deleteActivity(id: number): Promise<void> {
  await client.delete(`/activities/${id}`);
}

export async function reprocessActivity(activityId: number): Promise<{ activity_id: number; task_id: string }> {
  const { data } = await client.post(`/activities/${activityId}/reprocess`);
  return data;
}
