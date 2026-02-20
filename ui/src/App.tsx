import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "./api/client";
import type { AuthUser, SessionSummary } from "./api/client";
import { WelcomePage } from "./components/WelcomePage";
import { HomePage } from "./components/HomePage";
import { ChatSidebar } from "./components/ChatSidebar";
import { StepIndicator } from "./components/StepIndicator";
import { RecommendationsView } from "./components/RecommendationsView";
import { AnalyzingView } from "./components/AnalyzingView";
import { Dashboard } from "./components/Dashboard";
import { RequirementsForm } from "./components/RequirementsForm";
import { RequirementsModal } from "./components/RequirementsModal";
import {
  getDefaultRequirements,
  mergeWithDefaults,
} from "./components/requirementsFields";
import type { VehicleResult, TopVehicle } from "./types";
import "./App.css";

export type Phase = "chat" | "results" | "calling" | "dashboard";

const STEPS: { key: Phase; label: string }[] = [
  { key: "chat", label: "Requirements" },
  { key: "results", label: "Recommendations" },
  { key: "calling", label: "Dealer Calls" },
  { key: "dashboard", label: "Dashboard" },
];

type AppView = "home" | "session";
type StartTab = "chat" | "form";

function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [view, setView] = useState<AppView>("home");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("chat");
  const [completedPhases, setCompletedPhases] = useState<Set<Phase>>(new Set());
  const [isRequirementsComplete, setIsRequirementsComplete] = useState(false);
  const [searchVehicles, setSearchVehicles] = useState<VehicleResult[]>([]);
  const [top3, setTop3] = useState<TopVehicle[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [startTab, setStartTab] = useState<StartTab>("chat");
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [requirements, setRequirements] = useState<Record<string, unknown>>(
    getDefaultRequirements,
  );

  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [isSessionDropdownOpen, setIsSessionDropdownOpen] = useState(false);

  const sessionCreatedRef = useRef(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const markPhaseCompleted = useCallback((p: Phase) => {
    setCompletedPhases((prev) => {
      if (prev.has(p)) return prev;
      const next = new Set(prev);
      next.add(p);
      return next;
    });
  }, []);

  const fetchRecentSessions = useCallback(async (userId: string) => {
    try {
      const data = await api.sessions.listForUser(userId);
      setRecentSessions(data.sessions.slice(0, 5));
    } catch {
      setRecentSessions([]);
    }
  }, []);

  const createNewSession = useCallback(async (userId: string) => {
    sessionCreatedRef.current = true;
    setSessionLoading(true);
    setSessionError(null);
    try {
      const s = await api.sessions.create(userId);
      setSessionId(s.session_id);
      setPhase("chat");
      setCompletedPhases(new Set());
      setIsRequirementsComplete(false);
      setSearchVehicles([]);
      setTop3([]);
      setRefreshKey(0);
      setRequirements(getDefaultRequirements());
      setView("session");
    } catch {
      sessionCreatedRef.current = false;
      setSessionError("Could not connect to the backend.");
    } finally {
      setSessionLoading(false);
    }
  }, []);

  const resumeSession = useCallback(async (sid: string) => {
    setSessionLoading(true);
    setSessionError(null);
    try {
      const state = await api.sessions.getState(sid);
      setSessionId(sid);

      const targetPhase = (state.phase || "chat") as Phase;
      setPhase(targetPhase);

      const completed = new Set<Phase>();
      const phaseOrder: Phase[] = ["chat", "results", "calling", "dashboard"];
      const targetIdx = phaseOrder.indexOf(targetPhase);
      for (let i = 0; i <= targetIdx; i++) {
        completed.add(phaseOrder[i]);
      }
      setCompletedPhases(completed);

      setIsRequirementsComplete(state.has_search_results || targetIdx >= 1);
      setSearchVehicles([]);
      setTop3([]);
      setRefreshKey(0);
      setRequirements(
        mergeWithDefaults((state.preferences as Record<string, unknown>) || {}),
      );
      setView("session");
    } catch {
      setSessionError("Failed to resume session.");
    } finally {
      setSessionLoading(false);
    }
  }, []);

  const handleAuth = useCallback((user: AuthUser) => {
    setAuthUser(user);
    sessionStorage.setItem("da_auth", JSON.stringify(user));
  }, []);

  useEffect(() => {
    const saved = sessionStorage.getItem("da_auth");
    if (!saved) return;
    try {
      const user = JSON.parse(saved) as AuthUser;
      setAuthUser(user);
    } catch {
      sessionStorage.removeItem("da_auth");
    }
  }, []);

  useEffect(() => {
    if (!authUser) return;
    fetchRecentSessions(authUser.user_id);
  }, [authUser, fetchRecentSessions]);

  const handleLogout = useCallback(() => {
    sessionStorage.removeItem("da_auth");
    sessionCreatedRef.current = false;
    setAuthUser(null);
    setSessionId(null);
    setView("home");
    setPhase("chat");
    setCompletedPhases(new Set());
    setIsRequirementsComplete(false);
    setSearchVehicles([]);
    setTop3([]);
    setRecentSessions([]);
    setRequirements(getDefaultRequirements());
  }, []);

  const handleChatReply = useCallback(
    (updatedFilters?: Record<string, unknown>, readyToSearch?: boolean) => {
      const hasFilters =
        updatedFilters != null &&
        typeof updatedFilters === "object" &&
        !Array.isArray(updatedFilters) &&
        Object.keys(updatedFilters).length > 0;

      if (hasFilters) {
        setRequirements((prev) =>
          mergeWithDefaults({ ...prev, ...updatedFilters }),
        );
      }
      if (readyToSearch) setIsRequirementsComplete(true);
      // Only sync from server when we didn't get updated_filters (e.g. to backfill).
      // When we did get updated_filters, the response is the source of truth; getState
      // can return before the backend has persisted and would overwrite with stale/empty.
      if (sessionId && !hasFilters) {
        api.sessions
          .getState(sessionId)
          .then((state) => {
            const prefs = (state.preferences as Record<string, unknown>) || {};
            setRequirements(mergeWithDefaults(prefs));
          })
          .catch(() => {});
      }
    },
    [sessionId],
  );

  const handleGoToResults = useCallback(() => {
    if (phase === "results") {
      setRefreshKey((k) => k + 1);
      return;
    }
    markPhaseCompleted("chat");
    setPhase("results");
  }, [phase, markPhaseCompleted]);

  const handleBackToRequirements = useCallback(() => {
    setIsRequirementsComplete(false);
    setPhase("chat");
  }, []);

  const handleFormSearchDone = useCallback(() => {
    setIsRequirementsComplete(true);
    markPhaseCompleted("chat");
    setPhase("results");
  }, [markPhaseCompleted]);

  const handleStartCalling = useCallback(
    (vehicles: VehicleResult[]) => {
      setSearchVehicles(vehicles);
      markPhaseCompleted("results");
      setPhase("calling");
    },
    [markPhaseCompleted],
  );

  const handleAnalysisComplete = useCallback(
    (topResults: TopVehicle[], allVehicles: VehicleResult[]) => {
      setTop3(topResults);
      setSearchVehicles(allVehicles);
      markPhaseCompleted("calling");
      markPhaseCompleted("dashboard");
      setPhase("dashboard");
    },
    [markPhaseCompleted],
  );

  const handleStepClick = useCallback(
    (key: Phase) => {
      if (completedPhases.has(key) || key === phase) {
        setPhase(key);
      }
    },
    [completedPhases, phase],
  );

  const handleBackFromDashboard = useCallback(() => {
    setPhase("results");
  }, []);

  const handleGoHome = useCallback(() => {
    if (authUser) fetchRecentSessions(authUser.user_id);
    sessionCreatedRef.current = false;
    setSessionId(null);
    setView("home");
    setPhase("chat");
    setCompletedPhases(new Set());
    setIsRequirementsComplete(false);
    setSearchVehicles([]);
    setTop3([]);
    setRequirements(getDefaultRequirements());
  }, [authUser, fetchRecentSessions]);

  const toggleChat = useCallback(() => setIsChatOpen((o) => !o), []);

  useEffect(() => {
    if (!isSessionDropdownOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setIsSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isSessionDropdownOpen]);

  if (!authUser) {
    return <WelcomePage onAuth={handleAuth} />;
  }

  if (view === "home" && !sessionId) {
    return (
      <div className="app-shell">
        <header className="app-topbar">
          <div className="app-brand">
            <span className="app-brand-icon">
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="1" y="3" width="15" height="13" rx="2" ry="2" />
                <polygon
                  points="16 8 20 12 20 18 16 18 16 8"
                  style={{ fill: "none" }}
                />
                <circle cx="5.5" cy="18.5" r="2.5" />
                <circle cx="18.5" cy="18.5" r="2.5" />
              </svg>
            </span>
            <span className="app-brand-text">Dealership Agent</span>
          </div>
          <div className="app-topbar-user">
            <span className="app-user-avatar">
              {authUser.name[0]?.toUpperCase() || "U"}
            </span>
            <span className="app-user-name">{authUser.name}</span>
            <button
              type="button"
              className="app-logout-btn"
              onClick={handleLogout}
              title="Log out"
            >
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
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </header>
        <div className="app-body">
          <main className="app-content">
            <HomePage
              userId={authUser.user_id}
              userName={authUser.name}
              onNewSearch={() => createNewSession(authUser.user_id)}
              onResumeSession={resumeSession}
            />
          </main>
        </div>
      </div>
    );
  }

  if (sessionLoading) {
    return (
      <div className="app-loader">
        <div className="app-loader-spinner" />
        <p>Setting up your session...</p>
      </div>
    );
  }

  if (sessionError || !sessionId) {
    return (
      <div className="app-loader">
        <p className="app-loader-error">{sessionError || "No session"}</p>
        <button
          type="button"
          className="app-loader-retry"
          onClick={() => {
            if (authUser) createNewSession(authUser.user_id);
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const isDashboard = phase === "dashboard";
  const showSidebar = !isDashboard;

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="app-brand">
          {showSidebar && (
            <button
              type="button"
              className="app-chat-toggle"
              onClick={toggleChat}
              title={isChatOpen ? "Hide chat" : "Show chat"}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                {isChatOpen ? (
                  <>
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M9 3v18" />
                  </>
                ) : (
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                )}
              </svg>
            </button>
          )}
          <button
            type="button"
            className="app-brand-home"
            onClick={handleGoHome}
            title="Back to home"
          >
            <span className="app-brand-icon">
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="1" y="3" width="15" height="13" rx="2" ry="2" />
                <polygon
                  points="16 8 20 12 20 18 16 18 16 8"
                  style={{ fill: "none" }}
                />
                <circle cx="5.5" cy="18.5" r="2.5" />
                <circle cx="18.5" cy="18.5" r="2.5" />
              </svg>
            </span>
            <span className="app-brand-text">Dealership Agent</span>
          </button>

          <div className="app-session-switcher" ref={dropdownRef}>
            <button
              type="button"
              className="app-session-switcher-btn"
              onClick={() => {
                if (!isSessionDropdownOpen && authUser) {
                  fetchRecentSessions(authUser.user_id);
                }
                setIsSessionDropdownOpen((o) => !o);
              }}
              title="Switch session"
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {isSessionDropdownOpen && (
              <div className="app-session-dropdown">
                <button
                  type="button"
                  className="app-session-dropdown-item app-session-dropdown-new"
                  onClick={() => {
                    setIsSessionDropdownOpen(false);
                    if (authUser) {
                      sessionCreatedRef.current = false;
                      createNewSession(authUser.user_id);
                    }
                  }}
                >
                  + New Search
                </button>
                {recentSessions
                  .filter((s) => s.session_id !== sessionId)
                  .map((s) => (
                    <button
                      key={s.session_id}
                      type="button"
                      className="app-session-dropdown-item"
                      onClick={() => {
                        setIsSessionDropdownOpen(false);
                        resumeSession(s.session_id);
                      }}
                    >
                      <span className="app-session-dropdown-label">
                        {s.label}
                      </span>
                      <span className="app-session-dropdown-phase">
                        {s.phase}
                      </span>
                    </button>
                  ))}
                <button
                  type="button"
                  className="app-session-dropdown-item app-session-dropdown-home"
                  onClick={() => {
                    setIsSessionDropdownOpen(false);
                    handleGoHome();
                  }}
                >
                  View all sessions
                </button>
              </div>
            )}
          </div>
        </div>

        <StepIndicator
          steps={STEPS}
          current={phase}
          completedPhases={completedPhases}
          onStepClick={handleStepClick}
        />

        <div className="app-topbar-user">
          {completedPhases.has("dashboard") && phase !== "dashboard" && (
            <button
              type="button"
              className="app-dashboard-shortcut"
              onClick={() => setPhase("dashboard")}
              title="Go to Dashboard"
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
              </svg>
              Dashboard
            </button>
          )}
          <span className="app-user-avatar">
            {authUser.name[0]?.toUpperCase() || "U"}
          </span>
          <span className="app-user-name">{authUser.name}</span>
          <button
            type="button"
            className="app-logout-btn"
            onClick={handleLogout}
            title="Log out"
          >
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
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </header>

      <div className={`app-body ${isDashboard ? "app-body--full" : ""}`}>
        {showSidebar && (
          <ChatSidebar
            sessionId={sessionId}
            userName={authUser.name}
            onChatReply={handleChatReply}
            requirementsComplete={isRequirementsComplete}
            onGoToResults={handleGoToResults}
            currentPhase={phase}
            isOpen={isChatOpen}
            onToggle={toggleChat}
          />
        )}

        <main
          className={`app-content ${isDashboard ? "app-content--full" : ""}`}
        >
          {phase === "chat" && (
            <div className="app-start-area">
              <div className="app-start-tabs">
                <button
                  type="button"
                  className={`app-start-tab ${startTab === "chat" ? "app-start-tab--active" : ""}`}
                  onClick={() => setStartTab("chat")}
                >
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
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  Chat with AI
                </button>
                <button
                  type="button"
                  className={`app-start-tab ${startTab === "form" ? "app-start-tab--active" : ""}`}
                  onClick={() => setStartTab("form")}
                >
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
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M9 3v18" />
                    <path d="M13 8h4" />
                    <path d="M13 12h4" />
                    <path d="M13 16h4" />
                  </svg>
                  Quick Form
                </button>
              </div>

              {startTab === "chat" ? (
                <div className="app-content-center app-content-center--column">
                  <div className="app-welcome-card">
                    <h2>Welcome, {authUser.name}</h2>
                    <p>
                      Start by telling me what kind of car you are looking for
                      in the chat. I will gather your preferences and find the
                      best matches.
                    </p>
                    <div className="app-welcome-hints">
                      <span className="hint-chip">Budget range</span>
                      <span className="hint-chip">Preferred brand</span>
                      <span className="hint-chip">Body type</span>
                      <span className="hint-chip">Location / ZIP</span>
                      <span className="hint-chip">Max mileage</span>
                      <span className="hint-chip">Must-have features</span>
                    </div>
                  </div>
                  <RequirementsModal
                    requirements={requirements}
                    onRequirementsChange={setRequirements}
                    sessionId={sessionId}
                    onMarkComplete={handleGoToResults}
                  />
                </div>
              ) : (
                <RequirementsForm
                  sessionId={sessionId}
                  requirements={requirements}
                  onRequirementsChange={setRequirements}
                  onSearchDone={handleFormSearchDone}
                />
              )}
            </div>
          )}

          {phase === "results" && (
            <RecommendationsView
              sessionId={sessionId}
              onStartCalling={handleStartCalling}
              onBack={() => setPhase("chat")}
              onChangeRequirements={handleBackToRequirements}
              refreshKey={refreshKey}
            />
          )}

          {phase === "calling" && (
            <AnalyzingView
              sessionId={sessionId}
              vehicles={searchVehicles}
              onComplete={handleAnalysisComplete}
              onBack={() => setPhase("results")}
              onChangeRequirements={handleBackToRequirements}
            />
          )}

          {phase === "dashboard" && (
            <Dashboard
              sessionId={sessionId}
              onBackToChat={handleBackFromDashboard}
              top3={top3}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
