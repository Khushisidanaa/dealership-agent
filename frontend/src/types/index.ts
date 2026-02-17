// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

export interface Session {
  session_id: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

export interface Preferences {
  make: string;
  model: string;
  year_min: number;
  year_max: number;
  price_min: number;
  price_max: number;
  condition: "new" | "used" | "any";
  zip_code: string;
  radius_miles: number;
  max_mileage: number | null;
}

export interface PreferencesResponse {
  session_id: string;
  preferences_saved: boolean;
  next_step: string;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  reply: string;
  updated_filters: Record<string, unknown> | null;
  is_ready_to_search: boolean;
}

export interface ChatHistory {
  messages: ChatMessage[];
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchTrigger {
  search_id: string;
  status: string;
  estimated_time_seconds: number;
}

export interface SearchStatus {
  search_id: string;
  status: "scraping" | "analyzing" | "completed" | "failed";
  progress_percent: number;
  results_count: number;
}

export interface Vehicle {
  vehicle_id: string;
  rank: number;
  title: string;
  price: number;
  mileage: number | null;
  condition: string;
  dealer_name: string;
  dealer_phone: string;
  dealer_address: string;
  dealer_distance_miles: number | null;
  listing_url: string;
  image_urls: string[];
  features: string[];
  condition_score: number;
  price_score: number;
  overall_score: number;
  known_issues: string[];
  source: string;
}

export interface PriceStats {
  avg_market_price: number;
  lowest_price: number;
  highest_price: number;
}

export interface SearchResults {
  results: Vehicle[];
  price_stats: PriceStats | null;
}

// ---------------------------------------------------------------------------
// Shortlist / Dashboard
// ---------------------------------------------------------------------------

export interface ShortlistEntry {
  vehicle_id: string;
  rank: number;
  overall_score: number;
}

export interface CommunicationStatus {
  vehicle_id: string;
  text_sent: boolean;
  call_made: boolean;
  response: string | null;
}

export interface DashboardData {
  shortlist: Vehicle[];
  comparison_chart: Record<string, unknown> | null;
  communication_status: CommunicationStatus[];
}

// ---------------------------------------------------------------------------
// Communication
// ---------------------------------------------------------------------------

export interface TextResponse {
  text_id: string;
  status: string;
  dealer_phone: string;
  message_body: string;
}

export interface CallTrigger {
  call_id: string;
  status: string;
  dealer_phone: string;
}

export interface TranscriptEntry {
  speaker: string;
  text: string;
  timestamp: number;
}

export interface CallStatus {
  call_id: string;
  status: "initiating" | "ringing" | "in_progress" | "completed" | "failed";
  duration_seconds: number | null;
  transcript: TranscriptEntry[];
  summary: string | null;
  recording_url: string | null;
}

// ---------------------------------------------------------------------------
// Test Drive
// ---------------------------------------------------------------------------

export interface TestDriveRequest {
  vehicle_id: string;
  preferred_date: string;
  preferred_time: string;
  user_name: string;
  user_phone: string;
  user_email?: string;
  confirm: boolean;
}

export interface TestDriveResponse {
  booking_id: string;
  status: string;
  dealer_name: string;
  vehicle_title: string;
  scheduled_date: string;
  scheduled_time: string;
}

export interface TestDriveStatus {
  booking_id: string;
  status: string;
  confirmation_method: string | null;
  dealer_response: string | null;
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

export type WSMessageType =
  | "search_progress"
  | "call_status"
  | "chat_message"
  | "result_found";

export interface WSMessage {
  type: WSMessageType;
  [key: string]: unknown;
}
