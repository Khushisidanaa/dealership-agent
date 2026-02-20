import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { SessionSummary } from "../api/client";
import "./HomePage.css";

interface HomePageProps {
  userId: string;
  userName: string;
  onNewSearch: () => void;
  onResumeSession: (sessionId: string) => void;
}

const PHASE_LABELS: Record<string, string> = {
  chat: "Gathering preferences",
  results: "Viewing results",
  calling: "Calling dealers",
  dashboard: "Dashboard ready",
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function HomePage({
  userId,
  userName,
  onNewSearch,
  onResumeSession,
}: HomePageProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchSessions = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.sessions.listForUser(userId);
      setSessions(data.sessions);
    } catch {
      setSessions([]);
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  return (
    <div className="home-page">
      <div className="home-hero">
        <h1>Welcome back, {userName}</h1>
        <p>Start a new car search or pick up where you left off.</p>
        <button type="button" className="home-new-btn" onClick={onNewSearch}>
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Search
        </button>
      </div>

      {isLoading && (
        <div className="home-loading">
          <div className="home-spinner" />
          <span>Loading your sessions...</span>
        </div>
      )}

      {!isLoading && sessions.length > 0 && (
        <section className="home-sessions">
          <h2>Your Searches</h2>
          <div className="home-grid">
            {sessions.map((s) => (
              <button
                key={s.session_id}
                type="button"
                className="home-card"
                onClick={() => onResumeSession(s.session_id)}
              >
                <div className="home-card-top">
                  <span className="home-card-label">{s.label}</span>
                  <span className="home-card-time">
                    {timeAgo(s.created_at)}
                  </span>
                </div>
                <div className="home-card-meta">
                  <span className={`home-phase-badge home-phase--${s.phase}`}>
                    {PHASE_LABELS[s.phase] || s.phase}
                  </span>
                  {s.vehicle_count > 0 && (
                    <span className="home-card-stat">
                      {s.vehicle_count} vehicle
                      {s.vehicle_count !== 1 ? "s" : ""}
                    </span>
                  )}
                  {s.has_calls && (
                    <span className="home-card-stat home-card-stat--call">
                      Calls made
                    </span>
                  )}
                </div>
                <span className="home-card-arrow">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {!isLoading && sessions.length === 0 && (
        <div className="home-empty">
          <p>No past searches yet. Start your first one above!</p>
        </div>
      )}
    </div>
  );
}
