export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type UserIdentity = { id: number; email: string; is_app_admin: boolean; it_role: "NONE" | "IT_DOC_ADMIN" | "IT_EDITOR" | "IT_MEMBER" };
type ErrorEnvelope = { error?: { code?: string; message?: string } };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

let csrfToken: string | null = null;

async function decode(response: Response) {
  if (response.status === 204) return null;
  return response.json().catch(() => ({}));
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, credentials: "include", headers: { Accept: "application/json", ...init.headers } });
  } catch {
    throw new ApiError(0, "network_error", "Unable to reach the service");
  }
  const data = await decode(response) as T & ErrorEnvelope;
  if (!response.ok) throw new ApiError(response.status, data.error?.code ?? "request_failed", data.error?.message ?? "Request failed");
  return data;
}

export async function bootstrapCsrf(): Promise<string> {
  const data = await request<{ csrfToken: string }>("/api/v1/auth/csrf");
  csrfToken = data.csrfToken;
  return csrfToken;
}

async function unsafeRequest<T>(path: string, body?: object): Promise<T> {
  const token = csrfToken ?? await bootstrapCsrf();
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": token }, body: body ? JSON.stringify(body) : undefined });
}

export async function login(email: string, password: string): Promise<UserIdentity> {
  const data = await unsafeRequest<{ user: UserIdentity }>("/api/v1/auth/login", { email, password });
  await bootstrapCsrf();
  return data.user;
}

export async function currentUser(): Promise<UserIdentity> {
  return (await request<{ user: UserIdentity }>("/api/v1/auth/me")).user;
}

export async function logout(): Promise<void> {
  await unsafeRequest<null>("/api/v1/auth/logout");
  csrfToken = null;
}

export function resetApiStateForTests() { csrfToken = null; }
