/**
 * Fitora - typed API client.
 *
 * Every call goes through `request`, which attaches the stored token, unwraps
 * FastAPI's `{detail}` errors into a plain message, and throws an ApiError the
 * UI can show verbatim.
 */

// Empty string = same-origin relative requests, which always go through
// Next.js's own /api/* rewrite proxy (see next.config.js) to the backend.
// This is deliberate: hardcoding an absolute host like http://127.0.0.1:8000
// here would bake "my own machine" into every teammate's browser bundle when
// they load the app over the LAN (e.g. http://10.x.x.x:3000) - their browser
// would then try to reach 127.0.0.1 on THEIR OWN laptop, not the server.
// Only set NEXT_PUBLIC_API_URL if the backend is deliberately hosted on a
// different origin than the frontend (e.g. separate deployments).
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const PREFIX = "/api/v1";

export type Role = "user" | "gym_owner" | "admin" | "superadmin";

const TOKEN_KEYS: Record<string, string> = {
  user: "fitora_user_token",
  gym_owner: "fitora_owner_token",
  admin: "fitora_admin_token",
};

export function getToken(role: keyof typeof TOKEN_KEYS = "user"): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEYS[role]);
  } catch {
    return null;
  }
}

export function setToken(role: keyof typeof TOKEN_KEYS, token: string) {
  try {
    localStorage.setItem(TOKEN_KEYS[role], token);
  } catch {
    /* private mode - session continues in memory only */
  }
}

export function clearToken(role: keyof typeof TOKEN_KEYS) {
  try {
    localStorage.removeItem(TOKEN_KEYS[role]);
  } catch {
    /* ignore */
  }
}

export function setProfile(role: keyof typeof TOKEN_KEYS, profile: unknown) {
  try {
    localStorage.setItem(`fitora_${role}_profile`, JSON.stringify(profile));
  } catch {
    /* ignore */
  }
}

export function getProfile<T = any>(role: keyof typeof TOKEN_KEYS): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`fitora_${role}_profile`);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: any,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = {
  method?: string;
  body?: unknown;
  role?: keyof typeof TOKEN_KEYS;
  auth?: boolean;
  signal?: AbortSignal;
};

export async function request<T = any>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, role = "user", auth = true, signal } = opts;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken(role);
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}${PREFIX}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (e) {
    throw new ApiError(
      "Cannot reach the Fitora server. Check that the backend is running.",
      0,
    );
  }

  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text.slice(0, 300) };
  }

  if (!res.ok) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail[0]?.msg ?? "Request failed"
          : `Request failed (${res.status})`;
    throw new ApiError(detail, res.status, data);
  }

  return data as T;
}

/** Upload a file through multipart/form-data. */
export async function upload(
  path: string,
  file: File,
  role: keyof typeof TOKEN_KEYS = "user",
): Promise<any> {
  const form = new FormData();
  form.append("file", file);

  const headers: Record<string, string> = {};
  const token = getToken(role);
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}${PREFIX}${path}`, {
    method: "POST",
    headers,
    body: form,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(data?.detail ?? "Upload failed", res.status, data);
  }
  return data;
}

/* ------------------------------------------------------------------ user */
export const api = {
  /* auth */
  signup: (body: any) =>
    request("/auth/signup", { method: "POST", body, auth: false }),
  verifyOtp: (email: string, code: string) =>
    request("/auth/verify-otp", { method: "POST", body: { email, code }, auth: false }),
  resendOtp: (email: string, purpose = "signup") =>
    request("/auth/resend-otp", { method: "POST", body: { email, purpose }, auth: false }),
  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: { email, password }, auth: false }),
  me: () => request("/auth/me"),
  updateProfile: (body: any) => request("/profile", { method: "PUT", body }),

  /* discovery */
  gyms: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)]),
    );
    return request(`/gyms?${q}`);
  },
  gymFilters: () => request("/gyms/filters", { auth: false }),
  gym: (code: string, lat?: number, lon?: number) => {
    const q = lat != null ? `?lat=${lat}&lon=${lon}` : "";
    return request(`/gyms/${code}${q}`);
  },
  compare: (codes: string[]) =>
    request(`/gyms/compare/side-by-side?codes=${codes.join(",")}`),

  /* chat */
  chat: (body: any) => request("/chat", { method: "POST", body }),
  chatSuggestions: () => request("/chat/suggestions", { auth: false }),

  /* join / pay / pass */
  joinPrefill: (code: string) => request(`/join/${code}/prefill`),
  join: (code: string, body: any) =>
    request(`/join/${code}`, { method: "POST", body }),
  pay: (ref: string, body: any) => request(`/pay/${ref}`, { method: "POST", body }),
  pass: (membershipCode: string) => request(`/pass/${membershipCode}`),
  diet: (membershipCode: string) => request(`/diet/${membershipCode}`),
  myMemberships: () => request("/my/memberships"),
  review: (body: any) => request("/reviews", { method: "POST", body }),
};

/**
 * Consumes the chatbot's SSE stream: gym cards arrive almost instantly (the
 * `meta` event), then the answer text streams in token-by-token, then
 * `done` fires. Each callback is optional so callers only wire what they need.
 */
export async function chatStream(
  body: {
    message: string;
    history?: { role: string; content: string }[];
    latitude?: number;
    longitude?: number;
    top_k?: number;
  },
  handlers: {
    onMeta?: (meta: { gyms: any[]; interpretation: any; total_matches: number }) => void;
    onToken?: (token: string) => void;
    onDone?: () => void;
    onError?: (message: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken("user");
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${PREFIX}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    handlers.onError?.("Cannot reach the Fitora server. Check that the backend is running.");
    return;
  }

  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => null);
    handlers.onError?.(data?.detail ?? `Request failed (${res.status})`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line; parse whole frames only,
    // keep any trailing partial frame in the buffer for the next chunk.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const eventLine = frame.split("\n").find((l) => l.startsWith("event: "));
      const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!eventLine || !dataLine) continue;
      const eventName = eventLine.slice("event: ".length).trim();
      const data = JSON.parse(dataLine.slice("data: ".length));

      if (eventName === "meta") handlers.onMeta?.(data);
      else if (eventName === "token") handlers.onToken?.(data.t);
      else if (eventName === "done") handlers.onDone?.();
    }
  }
}

/* ------------------------------------------------------------ gym owner */
export const ownerApi = {
  signup: (body: any) =>
    request("/auth/owner/signup", { method: "POST", body, auth: false }),
  verifyOtp: (email: string, code: string) =>
    request("/auth/owner/verify-otp", { method: "POST", body: { email, code }, auth: false }),
  login: (email: string, password: string) =>
    request("/auth/owner/login", { method: "POST", body: { email, password }, auth: false }),

  dashboard: () => request("/owner/dashboard", { role: "gym_owner" }),
  getGym: () => request("/owner/gym", { role: "gym_owner" }),
  saveGym: (body: any, submit = true) =>
    request(`/owner/gym?submit=${submit}`, { method: "PUT", body, role: "gym_owner" }),
  saveBank: (body: any) =>
    request("/owner/bank", { method: "PUT", body, role: "gym_owner" }),

  coaches: () => request("/owner/coaches", { role: "gym_owner" }),
  addCoach: (body: any) =>
    request("/owner/coaches", { method: "POST", body, role: "gym_owner" }),
  updateCoach: (id: number, body: any) =>
    request(`/owner/coaches/${id}`, { method: "PUT", body, role: "gym_owner" }),
  deleteCoach: (id: number) =>
    request(`/owner/coaches/${id}`, { method: "DELETE", role: "gym_owner" }),

  equipment: () => request("/owner/equipment", { role: "gym_owner" }),
  addEquipment: (body: any) =>
    request("/owner/equipment", { method: "POST", body, role: "gym_owner" }),
  updateEquipment: (id: number, body: any) =>
    request(`/owner/equipment/${id}`, { method: "PUT", body, role: "gym_owner" }),
  deleteEquipment: (id: number) =>
    request(`/owner/equipment/${id}`, { method: "DELETE", role: "gym_owner" }),

  members: (statusFilter?: string) =>
    request(`/owner/members${statusFilter ? `?status_filter=${statusFilter}` : ""}`, {
      role: "gym_owner",
    }),
  dues: () => request("/owner/dues", { role: "gym_owner" }),
  reviews: () => request("/owner/reviews", { role: "gym_owner" }),
  earnings: () => request("/owner/earnings", { role: "gym_owner" }),
  complaints: () => request("/owner/complaints", { role: "gym_owner" }),
  raiseComplaint: (body: any) =>
    request("/owner/complaints", { method: "POST", body, role: "gym_owner" }),
};

/* ---------------------------------------------------------------- admin */
export const adminApi = {
  login: (email: string, password: string) =>
    request("/auth/admin/login", { method: "POST", body: { email, password }, auth: false }),

  dashboard: () => request("/admin/dashboard", { role: "admin" }),

  users: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)]),
    );
    return request(`/admin/users?${q}`, { role: "admin" });
  },
  user: (id: number) => request(`/admin/users/${id}`, { role: "admin" }),
  blockUser: (id: number, reason: string) =>
    request(`/admin/users/${id}/block`, { method: "POST", body: { reason }, role: "admin" }),
  unblockUser: (id: number) =>
    request(`/admin/users/${id}/unblock`, { method: "POST", role: "admin" }),
  deleteUser: (id: number) =>
    request(`/admin/users/${id}`, { method: "DELETE", role: "admin" }),

  gyms: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)]),
    );
    return request(`/admin/gyms?${q}`, { role: "admin" });
  },
  createGym: (body: any) =>
    request("/admin/gyms", { method: "POST", body, role: "admin" }),
  updateGym: (id: number, body: any) =>
    request(`/admin/gyms/${id}`, { method: "PUT", body, role: "admin" }),
  approveGym: (id: number) =>
    request(`/admin/gyms/${id}/approve`, { method: "POST", role: "admin" }),
  suspendGym: (id: number, reason: string) =>
    request(`/admin/gyms/${id}/suspend`, { method: "POST", body: { reason }, role: "admin" }),

  dues: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)]),
    );
    return request(`/admin/dues?${q}`, { role: "admin" });
  },
  extendGrace: (membershipId: number, extraDays: number, reason: string) =>
    request(`/admin/dues/${membershipId}/extend-grace`, {
      method: "POST",
      body: { extra_days: extraDays, reason },
      role: "admin",
    }),
  removeMember: (membershipId: number, reason: string) =>
    request(`/admin/dues/${membershipId}/remove-member`, {
      method: "POST",
      body: { reason },
      role: "admin",
    }),
  runSweep: () =>
    request("/admin/dues/run-sweep", { method: "POST", role: "admin" }),

  payments: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)]),
    );
    return request(`/admin/payments?${q}`, { role: "admin" });
  },
  payouts: () => request("/admin/payouts", { role: "admin" }),
  pendingPayouts: (month?: number, year?: number) => {
    const q = month ? `?month=${month}&year=${year}` : "";
    return request(`/admin/payouts/pending${q}`, { role: "admin" });
  },
  createPayout: (body: any) =>
    request("/admin/payouts", { method: "POST", body, role: "admin" }),
  releasePayout: (id: number, body: any = {}) =>
    request(`/admin/payouts/${id}/release`, { method: "POST", body, role: "admin" }),

  complaints: (statusFilter?: string) =>
    request(`/admin/complaints${statusFilter ? `?status_filter=${statusFilter}` : ""}`, {
      role: "admin",
    }),
  actOnComplaint: (id: number, action: string, adminAction: string) =>
    request(`/admin/complaints/${id}/action`, {
      method: "POST",
      body: { action, admin_action: adminAction },
      role: "admin",
    }),

  auditLogs: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)]),
    );
    return request(`/admin/audit-logs?${q}`, { role: "admin" });
  },
  ragStatus: () => request("/admin/rag/status", { role: "admin" }),
  reindex: () => request("/admin/rag/reindex", { method: "POST", role: "admin" }),
};
