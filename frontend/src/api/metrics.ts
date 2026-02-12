import client from './client.ts';
import type {
  ActivityMetricsResponse,
  FitnessTimeSeries,
  HRAnalysisResponse,
  PeriodSummary,
  PowerAnalysisResponse,
  FtpResponse,
} from './types.ts';

export async function getActivityMetrics(
  activityId: number,
  thresholdMethod = 'manual',
): Promise<ActivityMetricsResponse> {
  const { data } = await client.get<ActivityMetricsResponse>(
    `/metrics/activities/${activityId}`,
    { params: { threshold_method: thresholdMethod } },
  );
  return data;
}

export async function getFitnessData(
  startDate?: string,
  endDate?: string,
  thresholdMethod = 'manual',
): Promise<FitnessTimeSeries> {
  const { data } = await client.get<FitnessTimeSeries>('/metrics/fitness', {
    params: {
      start_date: startDate,
      end_date: endDate,
      threshold_method: thresholdMethod,
    },
  });
  return data;
}

export async function getMetricsSummary(
  startDate?: string,
  endDate?: string,
): Promise<PeriodSummary> {
  const { data } = await client.get<PeriodSummary>('/metrics/summary', {
    params: { start_date: startDate, end_date: endDate },
  });
  return data;
}

export async function getCurrentFtp(): Promise<FtpResponse> {
  const { data } = await client.get<FtpResponse>('/settings/ftp');
  return data;
}

export async function getPowerAnalysis(
  activityId: number,
  ftp = 0,
): Promise<PowerAnalysisResponse> {
  const { data } = await client.get<PowerAnalysisResponse>(
    `/metrics/activities/${activityId}/power-analysis`,
    { params: { ftp } },
  );
  return data;
}

export async function getHRAnalysis(
  activityId: number,
  maxHR = 190,
): Promise<HRAnalysisResponse> {
  const { data } = await client.get<HRAnalysisResponse>(
    `/metrics/activities/${activityId}/hr-analysis`,
    { params: { max_hr: maxHR } },
  );
  return data;
}
