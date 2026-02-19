import { useState, useEffect, useCallback } from "react";
import { api } from "./api/client";
import { mergeWithDefaults } from "./components/requirementsFields";
import { ChatWindow } from "./components/ChatWindow";
import { RequirementsModal } from "./components/RequirementsModal";
import { SearchResults } from "./components/SearchResults";
import { AnalyzingView } from "./components/AnalyzingView";
import { Dashboard } from "./components/Dashboard";
import type { VehicleResult, TopVehicle } from "./types";
import "./App.css";

type View = "chat" | "results" | "analyzing" | "dashboard";

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [view, setView] = useState<View>("chat");
  const [requirements, setRequirements] = useState<Record<string, unknown>>({});
  const [isRequirementsComplete, setIsRequirementsComplete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [searchVehicles, setSearchVehicles] = useState<VehicleResult[]>([]);
  const [, setTop3Vehicles] = useState<TopVehicle[]>([]);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    setSessionError(null);
    try {
      const s = await api.sessions.create();
      setSessionId(s.session_id);
      setUserId(s.user_id);
      return s.session_id;
    } catch (e) {
      setSessionError(
        e instanceof Error ? e.message : "Could not connect to backend",
      );
      return null;
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    ensureSession();
  }, [ensureSession]);

  const handleChatReply = useCallback(
    (updatedFilters?: Record<string, unknown>, readyToSearch?: boolean) => {
      if (updatedFilters) {
        setRequirements((prev) => ({ ...prev, ...updatedFilters }));
      }
      if (readyToSearch) {
        setIsRequirementsComplete(true);
      }
    },
    [],
  );

  const handleRequirementsChange = useCallback(
    (next: Record<string, unknown>) => {
      setRequirements(next);
    },
    [],
  );

  const handleMarkComplete = useCallback(async () => {
    const fullReq = mergeWithDefaults(requirements);
    if (sessionId) {
      const prefsBody: Record<string, unknown> = {
        make: Array.isArray(fullReq.brand_preference)
          ? (fullReq.brand_preference as string[])[0]
          : "",
        model: Array.isArray(fullReq.model_preference)
          ? (fullReq.model_preference as string[])[0]
          : "",
        year_min: fullReq.year_min ?? 2015,
        year_max: fullReq.year_max ?? 2026,
        price_min: fullReq.price_min ?? 0,
        price_max: fullReq.price_max ?? 100_000,
        condition: fullReq.condition ?? "any",
        zip_code: fullReq.zip_code ?? "",
        radius_miles: fullReq.radius_miles ?? fullReq.max_distance_miles ?? 50,
        max_mileage: fullReq.max_mileage ?? undefined,
      };
      try {
        await api.preferences.submit(sessionId, prefsBody);
      } catch {
        // non-blocking
      }
    }
    if (userId) {
      try {
        await api.users.updateRequirements(userId, fullReq);
      } catch {
        // non-blocking
      }
    }
    setIsRequirementsComplete(true);
  }, [sessionId, userId, requirements]);

  const handleGoToResults = useCallback(() => {
    setView("results");
  }, []);

  const handleBackToChat = useCallback(() => {
    setView("chat");
  }, []);

  const handleStartCalling = useCallback((vehicles: VehicleResult[]) => {
    setSearchVehicles(vehicles);
    setView("analyzing");
  }, []);

  const handleAnalysisComplete = useCallback(
    (top3: TopVehicle[], allVehicles: VehicleResult[]) => {
      setTop3Vehicles(top3);
      setSearchVehicles(allVehicles);
      setView("dashboard");
    },
    [],
  );

  if (loading) {
    return (
      <div className="app-loading">
        <div className="app-loading-spinner" />
        <p>Starting session...</p>
      </div>
    );
  }

  if (sessionError && !sessionId) {
    return (
      <div className="app-loading">
        <p className="app-loading-error">Could not connect to the backend.</p>
        <p className="app-loading-hint">
          Make sure the API is running at <code>http://127.0.0.1:8000</code>
        </p>
        <button
          type="button"
          className="app-loading-retry"
          onClick={() => {
            setLoading(true);
            ensureSession();
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-logo">Dealership Agent</h1>
        <nav className="app-nav">
          <button
            type="button"
            className={view === "chat" ? "active" : ""}
            onClick={() => setView("chat")}
          >
            Chat
          </button>
          <button
            type="button"
            className={
              view === "results" || view === "analyzing" ? "active" : ""
            }
            onClick={() => setView("results")}
            disabled={!isRequirementsComplete}
          >
            Results
          </button>
          <button
            type="button"
            className={view === "dashboard" ? "active" : ""}
            onClick={() => setView("dashboard")}
            disabled={!sessionId}
          >
            Dashboard
          </button>
        </nav>
      </header>

      <RequirementsModal
        requirements={requirements}
        onRequirementsChange={handleRequirementsChange}
        sessionId={sessionId}
        onMarkComplete={handleMarkComplete}
      />

      <main className="app-main">
        {view === "chat" && sessionId && (
          <ChatWindow
            sessionId={sessionId}
            onChatReply={handleChatReply}
            requirementsComplete={isRequirementsComplete}
            onGoToDashboard={handleGoToResults}
          />
        )}

        {view === "results" && sessionId && (
          <SearchResults
            sessionId={sessionId}
            onStartCalling={handleStartCalling}
            onBack={handleBackToChat}
          />
        )}

        {view === "analyzing" && sessionId && (
          <AnalyzingView
            sessionId={sessionId}
            vehicles={searchVehicles}
            onComplete={handleAnalysisComplete}
            onBack={() => setView("results")}
          />
        )}

        {view === "dashboard" && sessionId && (
          <Dashboard sessionId={sessionId} onBackToChat={handleBackToChat} />
        )}

        {view === "dashboard" && !sessionId && (
          <div className="app-loading">
            <div className="app-loading-spinner" />
            <p>Preparing dashboard...</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
