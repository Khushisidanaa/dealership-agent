import axios from "axios";
import type {
  Session,
  Preferences,
  PreferencesResponse,
  ChatResponse,
  ChatHistory,
  SearchTrigger,
  SearchStatus,
  SearchResults,
  ShortlistEntry,
  DashboardData,
  TextResponse,
  CallTrigger,
  CallStatus,
  TestDriveRequest,
  TestDriveResponse,
  TestDriveStatus,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export const createSession = () =>
  api.post<Session>("/api/sessions").then((r) => r.data);

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

export const submitPreferences = (sessionId: string, prefs: Preferences) =>
  api
    .post<PreferencesResponse>(`/api/sessions/${sessionId}/preferences`, prefs)
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export const sendChatMessage = (sessionId: string, message: string) =>
  api
    .post<ChatResponse>(`/api/sessions/${sessionId}/chat`, { message })
    .then((r) => r.data);

export const getChatHistory = (sessionId: string) =>
  api
    .get<ChatHistory>(`/api/sessions/${sessionId}/chat/history`)
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export const triggerSearch = (sessionId: string) =>
  api
    .post<SearchTrigger>(`/api/sessions/${sessionId}/search`)
    .then((r) => r.data);

export const getSearchStatus = (sessionId: string, searchId: string) =>
  api
    .get<SearchStatus>(`/api/sessions/${sessionId}/search/${searchId}/status`)
    .then((r) => r.data);

export const getSearchResults = (sessionId: string, searchId: string) =>
  api
    .get<SearchResults>(`/api/sessions/${sessionId}/search/${searchId}/results`)
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Shortlist / Dashboard
// ---------------------------------------------------------------------------

export const createShortlist = (
  sessionId: string,
  vehicleIds: string[],
  autoSelect = false,
) =>
  api
    .post<{
      shortlisted: ShortlistEntry[];
    }>(`/api/sessions/${sessionId}/shortlist`, {
      vehicle_ids: vehicleIds,
      auto_select: autoSelect,
    })
    .then((r) => r.data);

export const getDashboard = (sessionId: string) =>
  api
    .get<DashboardData>(`/api/sessions/${sessionId}/dashboard`)
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Communication
// ---------------------------------------------------------------------------

export const sendText = (
  sessionId: string,
  vehicleId: string,
  template = "inquiry",
) =>
  api
    .post<TextResponse>(`/api/sessions/${sessionId}/communication/text`, {
      vehicle_id: vehicleId,
      message_template: template,
    })
    .then((r) => r.data);

export const startCall = (
  sessionId: string,
  vehicleId: string,
  purpose = "inquiry",
  targetPrice?: number,
) =>
  api
    .post<CallTrigger>(`/api/sessions/${sessionId}/communication/call`, {
      vehicle_id: vehicleId,
      call_purpose: purpose,
      negotiation_target_price: targetPrice,
    })
    .then((r) => r.data);

export const getCallStatus = (sessionId: string, callId: string) =>
  api
    .get<CallStatus>(`/api/sessions/${sessionId}/communication/call/${callId}`)
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Test Drive
// ---------------------------------------------------------------------------

export const bookTestDrive = (sessionId: string, data: TestDriveRequest) =>
  api
    .post<TestDriveResponse>(`/api/sessions/${sessionId}/test-drive`, data)
    .then((r) => r.data);

export const getTestDriveStatus = (sessionId: string, bookingId: string) =>
  api
    .get<TestDriveStatus>(`/api/sessions/${sessionId}/test-drive/${bookingId}`)
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Analyze (dealer calls + ranking via SSE)
// ---------------------------------------------------------------------------

export const analyzeVehicles = (
  sessionId: string,
  onEvent: (eventType: string, data: Record<string, unknown>) => void,
): { cancel: () => void } => {
  const controller = new AbortController();
  const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const run = async () => {
    const resp = await fetch(`${baseURL}/api/sessions/${sessionId}/analyze`, {
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

    while (true) {
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
            // skip malformed
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
};

export default api;
