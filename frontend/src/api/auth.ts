import client from './client.ts';
import type {
  TokenResponse,
  UserResponse,
  SetupStatus,
  InitialSetupRequest,
} from './types.ts';

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/login', { email, password });
  return data;
}

export async function register(
  email: string,
  password: string,
  displayName: string,
): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/register', {
    email,
    password,
    display_name: displayName,
  });
  return data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/refresh', {
    refresh_token: refreshToken,
  });
  return data;
}

export async function getCurrentUser(): Promise<UserResponse> {
  const { data } = await client.get<UserResponse>('/users/me');
  return data;
}

export async function checkSetup(): Promise<SetupStatus> {
  const { data } = await client.get<SetupStatus>('/setup/status');
  return data;
}

export async function initialSetup(req: InitialSetupRequest): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/setup/init', req);
  return data;
}
