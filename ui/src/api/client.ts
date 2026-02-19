const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = (err as { detail?: string | { msg?: string } }).detail;
    const msg = typeof detail === "string" ? detail : detail?.msg ?? res.statusText;
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  sessions: {
    create: () =>
      request<{ session_id: string; user_id: string; created_at: string }>("/api/sessions", {
        method: "POST",
      }),
  },

  users: {
    /** Persist full requirements to MongoDB (user_requirements collection). */
    updateRequirements: (userId: string, body: Record<string, unknown>) =>
      request<Record<string, unknown>>(`/api/users/${userId}/requirements`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  },

  chat: {
    send: (sessionId: string, message: string) =>
      request<import("../types").ChatResponse>(
        `/api/sessions/${sessionId}/chat`,
        { method: "POST", body: JSON.stringify({ message }) }
      ),
    history: (sessionId: string) =>
      request<{ messages: import("../types").ChatMessage[] }>(
        `/api/sessions/${sessionId}/chat/history`
      ),
  },

  preferences: {
    submit: (
      sessionId: string,
      body: Record<string, unknown>
    ) =>
      request<{ session_id: string; preferences_saved: boolean }>(
        `/api/sessions/${sessionId}/preferences`,
        { method: "POST", body: JSON.stringify(body) }
      ),
  },

  search: {
    cars: (sessionId: string) =>
      request<import("../types").SearchResultsResponse>(
        `/api/sessions/${sessionId}/search/cars`
      ),
  },

  shortlist: {
    create: (sessionId: string, vehicleIds: string[], autoSelect = false) =>
      request<{ shortlisted: { vehicle_id: string; rank: number; overall_score: number }[] }>(
        `/api/sessions/${sessionId}/shortlist`,
        {
          method: "POST",
          body: JSON.stringify({ vehicle_ids: vehicleIds, auto_select: autoSelect }),
        }
      ),
  },

  dashboard: {
    get: (sessionId: string) =>
      request<import("../types").DashboardResponse>(
        `/api/sessions/${sessionId}/dashboard`
      ),
  },

  listings: {
    /** Get listings for the session using saved requirements (MarketCheck). */
    forSession: (sessionId: string) =>
      request<import("../types").ListingsResponse>(
        `/api/listings/by-session/${sessionId}`
      ),
  },

  testDrive: {
    book: (
      sessionId: string,
      body: {
        vehicle_id: string;
        preferred_date: string;
        preferred_time: string;
        user_name: string;
        user_phone: string;
        user_email?: string;
        confirm?: boolean;
      }
    ) =>
      request<import("../types").TestDriveResponse>(
        `/api/sessions/${sessionId}/test-drive`,
        { method: "POST", body: JSON.stringify(body) }
      ),
  },
};
