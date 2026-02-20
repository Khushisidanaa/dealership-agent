import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "./api/client";
import type { AuthUser } from "./api/client";
import { WelcomePage } from "./components/WelcomePage";
import { ChatSidebar } from "./components/ChatSidebar";
import { StepIndicator } from "./components/StepIndicator";
import { RecommendationsView } from "./components/RecommendationsView";
import { AnalyzingView } from "./components/AnalyzingView";
import { Dashboard } from "./components/Dashboard";
import { RequirementsForm } from "./components/RequirementsForm";
import type { VehicleResult, TopVehicle } from "./types";
import "./App.css";

export type Phase = "chat" | "results" | "calling" | "dashboard";

const STEPS: { key: Phase; label: string }[] = [
  { key: "chat", label: "Requirements" },
  { key: "results", label: "Recommendations" },
  { key: "calling", label: "Dealer Calls" },
  { key: "dashboard", label: "Dashboard" },
];

type StartTab = "chat" | "form";

function App() {
  const hasSavedAuth = !!sessionStorage.getItem("da_auth");

  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("chat");
  const [isRequirementsComplete, setIsRequirementsComplete] = useState(false);
  const [searchVehicles, setSearchVehicles] = useState<VehicleResult[]>([]);
  const [top3, setTop3] = useState<TopVehicle[]>([]);
  const [sessionLoading, setSessionLoading] = useState(hasSavedAuth);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [startTab, setStartTab] = useState<StartTab>("chat");
  const [isChatOpen, setIsChatOpen] = useState(true);

  const sessionCreatedRef = useRef(false);

  const createSession = useCallback(async () => {
    if (sessionCreatedRef.current) return;
    sessionCreatedRef.current = true;
    setSessionLoading(true);
    setSessionError(null);
    try {
      const s = await api.sessions.create();
      setSessionId(s.session_id);
    } catch {
      sessionCreatedRef.current = false;
      setSessionError("Could not connect to the backend.");
    } finally {
      setSessionLoading(false);
    }
  }, []);

  const handleAuth = useCallback(
    (user: AuthUser) => {
      setAuthUser(user);
      sessionStorage.setItem("da_auth", JSON.stringify(user));
      createSession();
    },
    [createSession],
  );

  useEffect(() => {
    const saved = sessionStorage.getItem("da_auth");
    if (!saved) return;
    try {
      const user = JSON.parse(saved) as AuthUser;
      setAuthUser(user);
      createSession();
    } catch {
      sessionStorage.removeItem("da_auth");
      setSessionLoading(false);
    }
  }, [createSession]);

  const handleLogout = useCallback(() => {
    sessionStorage.removeItem("da_auth");
    sessionCreatedRef.current = false;
    setAuthUser(null);
    setSessionId(null);
    setPhase("chat");
    setIsRequirementsComplete(false);
    setSearchVehicles([]);
    setTop3([]);
  }, []);

  const handleChatReply = useCallback(
    (_filters?: Record<string, unknown>, readyToSearch?: boolean) => {
      if (readyToSearch) setIsRequirementsComplete(true);
    },
    [],
  );

  const handleGoToResults = useCallback(() => {
    setPhase("results");
  }, []);

  const handleBackToRequirements = useCallback(() => {
    setIsRequirementsComplete(false);
    setPhase("chat");
  }, []);

  const handleFormSearchDone = useCallback(() => {
    setIsRequirementsComplete(true);
    setPhase("results");
  }, []);

  const handleStartCalling = useCallback((vehicles: VehicleResult[]) => {
    setSearchVehicles(vehicles);
    setPhase("calling");
  }, []);

  const handleAnalysisComplete = useCallback(
    (topResults: TopVehicle[], allVehicles: VehicleResult[]) => {
      setTop3(topResults);
      setSearchVehicles(allVehicles);
      setPhase("dashboard");
    },
    [],
  );

  const toggleChat = useCallback(() => setIsChatOpen((o) => !o), []);

  if (!authUser) {
    return <WelcomePage onAuth={handleAuth} />;
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
          onClick={createSession}
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
        <StepIndicator steps={STEPS} current={phase} />
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
                <div className="app-content-center">
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
                </div>
              ) : (
                <RequirementsForm
                  sessionId={sessionId}
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
              onBackToChat={handleBackToRequirements}
              top3={top3}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
