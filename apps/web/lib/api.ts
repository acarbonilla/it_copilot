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

export type VaultCredentialType = "LOGIN" | "API_TOKEN" | "SSH_KEY" | "GENERIC_SECRET";
export type VaultCredential = {
  id: string;
  credential_type: VaultCredentialType;
  label: string;
  service_label: string;
  origin: string;
  revision: number;
  created_at: string;
  updated_at: string;
};
export type DeletedVaultCredential = Pick<VaultCredential, "id" | "credential_type" | "label" | "service_label" | "origin" | "revision"> & {
  restorationEligible: boolean;
  restorationExpiresAt: string;
};
export type VaultPage<T> = { credentials: T[]; nextCursor: string | null };
export type VaultSecretFields = Record<string, string>;
export type VaultCredentialInput = {
  credentialType: VaultCredentialType;
  label: string;
  serviceLabel?: string;
  origin?: string;
  secretFields: VaultSecretFields;
};

/*
 * Sensitive vault mutations deliberately use a separate, single-attempt path.
 * A CSRF token may be bootstrapped before the mutation, but the mutation itself
 * is never replayed: a grant is single-use even when the business action fails.
 */
async function vaultSensitiveRequest<T>(path: string, grant: string, body?: object, method = "POST"): Promise<T> {
  const token = csrfToken ?? await bootstrapCsrf();
  return request<T>(path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": token, "X-Vault-Grant": grant },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function listVaultCredentials(filters: { cursor?: string; type?: VaultCredentialType | ""; prefix?: string; limit?: number } = {}): Promise<VaultPage<VaultCredential>> {
  const query = new URLSearchParams({ limit: String(filters.limit ?? 25) });
  if (filters.cursor) query.set("cursor", filters.cursor);
  if (filters.type) query.set("type", filters.type);
  if (filters.prefix) query.set("prefix", filters.prefix);
  return request(`/api/v1/vault/credentials?${query}`);
}

export async function listDeletedVaultCredentials(cursor?: string, limit = 25): Promise<VaultPage<DeletedVaultCredential>> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("cursor", cursor);
  return request(`/api/v1/vault/deleted-credentials?${query}`);
}

export async function reauthenticateVault(password: string): Promise<{ grant: string; expiresAt: string }> {
  const token = await bootstrapCsrf();
  return request("/api/v1/vault/reauthenticate", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify({ password }),
  });
}

export async function createVaultCredential(input: VaultCredentialInput, grant: string): Promise<VaultCredential> {
  return (await vaultSensitiveRequest<{ credential: VaultCredential }>("/api/v1/vault/credentials", grant, input)).credential;
}

export async function updateVaultCredential(item: VaultCredential, changes: { metadata: { label: string; service_label?: string; origin?: string }; secretFields?: VaultSecretFields }, grant: string): Promise<VaultCredential> {
  return (await vaultSensitiveRequest<{ credential: VaultCredential }>(`/api/v1/vault/credentials/${encodeURIComponent(item.id)}`, grant, {
    expectedRevision: item.revision,
    metadata: changes.metadata,
    ...(changes.secretFields ? { secretFields: changes.secretFields } : {}),
  }, "PATCH")).credential;
}

export async function revealVaultCredential(id: string, grant: string): Promise<VaultSecretFields> {
  return (await vaultSensitiveRequest<{ credential: { id: string; revealed: VaultSecretFields } }>(`/api/v1/vault/credentials/${encodeURIComponent(id)}/reveal`, grant)).credential.revealed;
}

export async function deleteVaultCredential(item: VaultCredential, grant: string): Promise<void> {
  await vaultSensitiveRequest(`/api/v1/vault/credentials/${encodeURIComponent(item.id)}`, grant, { expectedRevision: item.revision }, "DELETE");
}

export async function restoreVaultCredential(item: DeletedVaultCredential, grant: string): Promise<VaultCredential> {
  return (await vaultSensitiveRequest<{ credential: VaultCredential }>(`/api/v1/vault/credentials/${encodeURIComponent(item.id)}/restore`, grant, { expectedRevision: item.revision })).credential;
}

export type CopilotCitation = { id: string; document_id: string; version_id: string; label: string; version_sequence: number };
export type CopilotMessage = { id: string; role: "user" | "assistant"; content: string; grounding_status: "not_applicable" | "references" | "insufficient"; provider_status: "not_applicable" | "disabled" | "unavailable"; citations: CopilotCitation[]; created_at: string };
export type CopilotConversation = { id: string; title: string; created_at: string; updated_at: string; last_activity_at: string; retention_expires_at: string };
export type CopilotConversationPage = { conversations: CopilotConversation[]; pagination: { page: number; page_size: number; count: number; total_pages: number } };
export type CopilotConversationDetail = { conversation: CopilotConversation; messages: CopilotMessage[] };

export async function listCopilotConversations(page = 1): Promise<CopilotConversationPage> { return request(`/api/v1/copilot/conversations?page=${page}&page_size=25`); }
export async function getCopilotConversation(id: string): Promise<CopilotConversationDetail> { return request(`/api/v1/copilot/conversations/${encodeURIComponent(id)}`); }
export async function createCopilotConversation(title = "New conversation"): Promise<CopilotConversation> { return (await unsafeRequest<{ conversation: CopilotConversation }>("/api/v1/copilot/conversations", { title })).conversation; }
export async function deleteCopilotConversation(id: string): Promise<void> { await unsafeRequest(`/api/v1/copilot/conversations/${encodeURIComponent(id)}`, undefined, "DELETE"); }
export async function submitCopilotQuestion(id: string, question: string): Promise<{ conversation: CopilotConversation; user_message: CopilotMessage; assistant_message: CopilotMessage }> { return unsafeRequest(`/api/v1/copilot/conversations/${encodeURIComponent(id)}/messages`, { question }); }

export function resetApiStateForTests() { csrfToken = null; }
