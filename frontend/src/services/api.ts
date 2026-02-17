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
    }>(`/api/sessions/${sessionId}/shortlist`, { vehicle_ids: vehicleIds, auto_select: autoSelect })
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

export default api;
