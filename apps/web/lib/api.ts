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

async function unsafeRequest<T>(path: string, body?: object, method = "POST"): Promise<T> {
  const send = (token: string) => request<T>(path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: body ? JSON.stringify(body) : undefined,
  });

  try {
    return await send(csrfToken ?? await bootstrapCsrf());
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 403 || error.code !== "csrf_failed") throw error;
    return send(await bootstrapCsrf());
  }
}

async function unsafeFormRequest<T>(path: string, body: FormData): Promise<T> {
  const send = (token: string) => request<T>(path, { method: "POST", headers: { "X-CSRFToken": token }, body });
  try { return await send(csrfToken ?? await bootstrapCsrf()); }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 403 || error.code !== "csrf_failed") throw error;
    return send(await bootstrapCsrf());
  }
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

export async function activateAccount(token: string, password: string): Promise<void> {
  await unsafeRequest<{ status: "activated" }>("/api/v1/auth/activate", { token, password });
}

export type ManagedUser = UserIdentity & { is_active: boolean; lifecycle_status: "active" | "pending_invitation" | "deactivated" | "inactive_legacy" };
export type UserPage = { users: ManagedUser[]; pagination: { page: number; page_size: number; count: number; total_pages: number } };

export async function listUsers(page = 1): Promise<UserPage> { return request<UserPage>(`/api/v1/users?page=${page}`); }
export async function updateUser(id: number, changes: Pick<ManagedUser, "it_role" | "is_app_admin">): Promise<ManagedUser> {
  return (await unsafeRequest<{ user: ManagedUser }>(`/api/v1/users/${id}`, changes, "PATCH")).user;
}
export async function deactivateUser(id: number): Promise<ManagedUser> { return (await unsafeRequest<{ user: ManagedUser }>(`/api/v1/users/${id}/deactivate`)).user; }
export async function reactivateUser(id: number): Promise<ManagedUser> { return (await unsafeRequest<{ user: ManagedUser }>(`/api/v1/users/${id}/reactivate`)).user; }
export async function requestDeletionReview(id: number, reason_code: "NO_LONGER_NEEDED" | "SECURITY_CONCERN" | "DUPLICATE_ACCOUNT"): Promise<void> {
  await unsafeRequest(`/api/v1/users/${id}/deletion-reviews`, { reason_code });
}
export async function inviteUser(email: string, it_role: UserIdentity["it_role"], is_app_admin: boolean): Promise<void> {
  await unsafeRequest("/api/v1/users/invitations", { email, it_role, is_app_admin });
}

export type DocumentItem = { id: string; title?: string; description?: string; owner_id?: number; visibility: "active" | "archived"; metadata_revision: number; created_at: string; updated_at: string; processing: null | { version_id: string; sequence: number; status: "staged" | "queued" | "processing" | "ready" | "failed" | "cancelled" }; capabilities: { edit: boolean; download: boolean; archive: boolean; restore: boolean; delete: boolean; retry: boolean } };
export type DocumentPage = { documents: DocumentItem[]; pagination: { page: number; page_size: number; count: number; total_pages: number } };
export async function listDocuments(page = 1, visibility = ""): Promise<DocumentPage> { return request<DocumentPage>(`/api/v1/documents?page=${page}${visibility ? `&visibility=${encodeURIComponent(visibility)}` : ""}`); }
export async function uploadDocument(file: File, title: string, description: string): Promise<void> { const body = new FormData(); body.append("file", file); body.append("title", title); body.append("description", description); await unsafeFormRequest("/api/v1/documents", body); }
export async function updateDocument(item: DocumentItem, title: string, description: string): Promise<DocumentItem> { return (await unsafeRequest<{ document: DocumentItem }>(`/api/v1/documents/${item.id}`, { title, description, expected_revision: item.metadata_revision }, "PATCH")).document; }
export async function documentAction(item: DocumentItem, action: "archive" | "restore" | "delete"): Promise<DocumentItem> { return (await unsafeRequest<{ document: DocumentItem }>(`/api/v1/documents/${item.id}/${action}`, { expected_revision: item.metadata_revision })).document; }
export async function retryDocument(item: DocumentItem): Promise<void> { if (!item.processing) throw new ApiError(409, "conflict", "Document has no retryable version"); await unsafeRequest(`/api/v1/documents/${item.id}/retry`, { expected_revision: item.metadata_revision, version_id: item.processing.version_id }); }
export function documentDownloadUrl(id: string): string { return `${API_BASE_URL}/api/v1/documents/${id}/download`; }

export function resetApiStateForTests() { csrfToken = null; }
