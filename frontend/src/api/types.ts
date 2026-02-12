/* TypeScript interfaces matching backend Pydantic schemas */

// ── Auth ──────────────────────────────────────────────────────────────

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: number;
  email: string;
  display_name: string;
  created_at: string;
}

// ── Setup ─────────────────────────────────────────────────────────────

export interface SetupStatus {
  setup_complete: boolean;
  user_count: number;
}

export interface InitialSetupRequest {
  email: string;
  password: string;
  display_name: string;
  ftp_watts?: number | null;
}

// ── Activity ──────────────────────────────────────────────────────────

export interface Activity {
  id: number;
  user_id: number;
  external_id: string | null;
  source: string;
  activity_date: string;
  name: string;
  sport_type: string | null;
  duration_seconds: number | null;
  distance_meters: number | null;
  elevation_gain_meters: number | null;
  avg_power_watts: number | null;
  max_power_watts: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_cadence: number | null;
  calories: number | null;
  tss: number | null;
  np_watts: number | null;
  intensity_factor: number | null;
  fit_file_path: string | null;
  device_name: string | null;
  notes: string | null;
  processing_status: string;
  error_message: string | null;
  file_hash: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActivityListResponse {
  items: Activity[];
  total: number;
  limit: number;
  offset: number;
}

export interface ActivityUploadResponse {
  activity_id: number;
  task_id: string;
}

// ── Streams ───────────────────────────────────────────────────────────

export interface StreamStats {
  power_avg: number | null;
  power_max: number | null;
  hr_avg: number | null;
  hr_max: number | null;
  speed_avg: number | null;
  speed_max: number | null;
  altitude_min: number | null;
  altitude_max: number | null;
}

export interface StreamResponse {
  activity_id: number;
  point_count: number;
  stats: StreamStats;
  timestamps: string[];
  power: (number | null)[];
  heart_rate: (number | null)[];
  cadence: (number | null)[];
  speed_mps: (number | null)[];
  altitude_meters: (number | null)[];
  distance_meters: (number | null)[];
  temperature_c: (number | null)[];
  latitude: (number | null)[];
  longitude: (number | null)[];
  grade_percent: (number | null)[];
}

export interface StreamSummaryResponse {
  activity_id: number;
  point_count: number;
  original_point_count: number;
  stats: StreamStats;
  timestamps: string[];
  power: (number | null)[];
  heart_rate: (number | null)[];
  cadence: (number | null)[];
  speed_mps: (number | null)[];
  altitude_meters: (number | null)[];
}

// ── Metrics ───────────────────────────────────────────────────────────

export interface ActivityMetricsResponse {
  activity_id: number;
  normalized_power: number | null;
  tss: number | null;
  intensity_factor: number | null;
  zone_distribution: Record<string, number> | null;
  variability_index: number | null;
  efficiency_factor: number | null;
  ftp_at_computation: number;
  threshold_method: string;
  computed_at: string;
}

export interface FitnessDataPoint {
  date: string;
  tss_total: number;
  ctl: number;
  atl: number;
  tsb: number;
}

export interface FitnessTimeSeries {
  data: FitnessDataPoint[];
  start_date: string;
  end_date: string;
  threshold_method: string;
}

export interface PeriodSummary {
  total_tss: number;
  ride_count: number;
  total_duration_seconds: number;
  total_distance_meters: number;
  start_date: string;
  end_date: string;
}

// ── Settings ──────────────────────────────────────────────────────────

export interface UserSettings {
  ftp_watts: number | null;
  ftp_method: string;
  preferred_threshold_method: string;
  calendar_start_day: number;
  weight_kg: number | null;
  date_of_birth: string | null;
}

export interface FtpResponse {
  ftp_watts: number;
  ftp_method: string;
  updated_at: string | null;
}

// ── Thresholds ────────────────────────────────────────────────────────

export interface ThresholdResponse {
  id: number;
  method: string;
  ftp_watts: number;
  effective_date: string;
  source_activity_id: number | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

// ── Task ──────────────────────────────────────────────────────────────

export interface TaskStatus {
  task_id: string;
  status: string;
  result: unknown;
}
