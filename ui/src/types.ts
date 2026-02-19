export interface Session {
  session_id: string;
  user_id: string;
  created_at: string;
}

export interface ChatMessage {
  role: string;
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  reply: string;
  updated_filters?: Record<string, unknown>;
  is_ready_to_search: boolean;
}

export interface VehicleResult {
  vehicle_id: string;
  rank: number;
  title: string;
  price: number;
  mileage?: number;
  condition: string;
  dealer_name: string;
  dealer_phone: string;
  dealer_address: string;
  dealer_distance_miles?: number;
  listing_url: string;
  image_urls: string[];
  features: string[];
  condition_score: number;
  price_score: number;
  overall_score: number;
  known_issues: string[];
  source: string;
}

export interface CommunicationStatusOut {
  vehicle_id: string;
  text_sent: boolean;
  call_made: boolean;
  response?: string;
}

export interface DashboardResponse {
  shortlist: VehicleResult[];
  comparison_chart?: Record<string, unknown>;
  communication_status: CommunicationStatusOut[];
}

export interface TestDriveResponse {
  booking_id: string;
  status: string;
  dealer_name: string;
  vehicle_title: string;
  scheduled_date: string;
  scheduled_time: string;
}

export interface SearchTriggerResponse {
  search_id: string;
  status: string;
  estimated_time_seconds: number;
}

export interface SearchStatusResponse {
  search_id: string;
  status: string;
  progress_percent: number;
  results_count: number;
}

export interface SearchResultsResponse {
  results: VehicleResult[];
  price_stats?: { avg_market_price: number; lowest_price: number; highest_price: number };
}

/** Grouped by dealer for dashboard table */
export interface DealershipGroup {
  dealerName: string;
  address: string;
  distanceMiles?: number;
  vehicles: VehicleResult[];
  communicationStatus: Record<string, CommunicationStatusOut>;
}

/** Test drive booking we track in UI */
export interface TestDriveBooking {
  booking_id: string;
  vehicle_id: string;
  vehicle_title: string;
  dealer_name: string;
  scheduled_date: string;
  scheduled_time: string;
  status: string;
}
