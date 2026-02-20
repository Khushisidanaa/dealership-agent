const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
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
    const msg =
      typeof detail === "string" ? detail : (detail?.msg ?? res.statusText);
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export function analyzeVehicles(
  sessionId: string,
  onEvent: (eventType: string, data: Record<string, unknown>) => void,
): { cancel: () => void } {
  const controller = new AbortController();

  const run = async () => {
    const resp = await fetch(`${API_BASE}/api/sessions/${sessionId}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });

    if (!resp.ok || !resp.body) {
      onEvent("error", { message: `HTTP ${resp.status}` });
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ") && currentEvent) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(currentEvent, data);
          } catch {
            /* skip malformed */
          }
          currentEvent = "";
        }
      }
    }
  };

  run().catch((err) => {
    if (err.name !== "AbortError") {
      onEvent("error", { message: String(err) });
    }
  });

  return { cancel: () => controller.abort() };
}

export interface AuthUser {
  user_id: string;
  name: string;
  email: string;
}

export const api = {
  auth: {
    signup: (name: string, email: string, password: string) =>
      request<AuthUser>("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({ name, email, password }),
      }),
    login: (email: string, password: string) =>
      request<AuthUser>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
  },

  sessions: {
    create: () =>
      request<{ session_id: string; user_id: string; created_at: string }>(
        "/api/sessions",
        {
          method: "POST",
        },
      ),
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
        { method: "POST", body: JSON.stringify({ message }) },
      ),
    history: (sessionId: string) =>
      request<{ messages: import("../types").ChatMessage[] }>(
        `/api/sessions/${sessionId}/chat/history`,
      ),
  },

  preferences: {
    submit: (sessionId: string, body: Record<string, unknown>) =>
      request<{ session_id: string; preferences_saved: boolean }>(
        `/api/sessions/${sessionId}/preferences`,
        { method: "POST", body: JSON.stringify(body) },
      ),
  },

  search: {
    cars: (sessionId: string) =>
      request<import("../types").SearchResultsResponse>(
        `/api/sessions/${sessionId}/search/cars`,
      ),
  },

  shortlist: {
    create: (sessionId: string, vehicleIds: string[], autoSelect = false) =>
      request<{
        shortlisted: {
          vehicle_id: string;
          rank: number;
          overall_score: number;
        }[];
      }>(`/api/sessions/${sessionId}/shortlist`, {
        method: "POST",
        body: JSON.stringify({
          vehicle_ids: vehicleIds,
          auto_select: autoSelect,
        }),
      }),
  },

  dashboard: {
    get: (sessionId: string) =>
      request<import("../types").DashboardResponse>(
        `/api/sessions/${sessionId}/dashboard`,
      ),
  },

  listings: {
    /** Get listings for the session using saved requirements (MarketCheck). */
    forSession: (sessionId: string) =>
      request<import("../types").ListingsResponse>(
        `/api/listings/by-session/${sessionId}`,
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
      },
    ) =>
      request<import("../types").TestDriveResponse>(
        `/api/sessions/${sessionId}/test-drive`,
        { method: "POST", body: JSON.stringify(body) },
      ),
  },
};
