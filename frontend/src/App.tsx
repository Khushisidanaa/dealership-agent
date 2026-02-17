import { useState, useCallback } from "react";
import AppLayout from "./components/Layout/AppLayout";
import Questionnaire from "./components/Questionnaire/Questionnaire";
import ChatPanel from "./components/Chat/ChatPanel";
import ResultsList from "./components/Results/ResultsList";
import DashboardView from "./components/Dashboard/DashboardView";
import TestDriveForm from "./components/TestDrive/TestDriveForm";
import * as api from "./services/api";
import type {
  Preferences,
  ChatMessage,
  Vehicle,
  PriceStats,
  CommunicationStatus,
} from "./types";

type Step =
  | "questionnaire"
  | "chat"
  | "searching"
  | "results"
  | "dashboard"
  | "testdrive";

const App = () => {
  // ---------------------------------------------------------------------------
  // Global state
  // ---------------------------------------------------------------------------
  const [step, setStep] = useState<Step>("questionnaire");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Chat
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isReadyToSearch, setIsReadyToSearch] = useState(false);

  // Search
  const [searchId, setSearchId] = useState<string | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [priceStats, setPriceStats] = useState<PriceStats | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Dashboard
  const [shortlist, setShortlist] = useState<Vehicle[]>([]);
  const [commStatus, setCommStatus] = useState<CommunicationStatus[]>([]);

  // Test drive
  const [testDriveVehicleId, setTestDriveVehicleId] = useState<string | null>(
    null,
  );

  // ---------------------------------------------------------------------------
  // Step 1: Questionnaire
  // ---------------------------------------------------------------------------
  const handlePreferencesSubmit = useCallback(async (prefs: Preferences) => {
    setIsLoading(true);
    try {
      const session = await api.createSession();
      setSessionId(session.session_id);
      await api.submitPreferences(session.session_id, prefs);
      setStep("chat");
    } catch (err) {
      console.error("Failed to submit preferences:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Step 2: Chat
  // ---------------------------------------------------------------------------
  const handleChatSend = useCallback(
    async (message: string) => {
      if (!sessionId) return;
      setChatMessages((prev) => [
        ...prev,
        { role: "user", content: message, timestamp: new Date().toISOString() },
      ]);
      setIsLoading(true);
      try {
        const res = await api.sendChatMessage(sessionId, message);
        setChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.reply,
            timestamp: new Date().toISOString(),
          },
        ]);
        if (res.is_ready_to_search) {
          setIsReadyToSearch(true);
        }
      } catch (err) {
        console.error("Chat error:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId],
  );

  const handleStartSearch = useCallback(async () => {
    if (!sessionId) return;
    setStep("searching");
    setIsLoading(true);
    try {
      const trigger = await api.triggerSearch(sessionId);
      setSearchId(trigger.search_id);

      // Poll for completion
      const poll = async () => {
        const status = await api.getSearchStatus(sessionId, trigger.search_id);
        if (status.status === "completed") {
          const results = await api.getSearchResults(
            sessionId,
            trigger.search_id,
          );
          setVehicles(results.results);
          setPriceStats(results.price_stats);
          setStep("results");
          setIsLoading(false);
        } else if (status.status === "failed") {
          console.error("Search failed");
          setIsLoading(false);
        } else {
          setTimeout(poll, 2000);
        }
      };
      poll();
    } catch (err) {
      console.error("Search error:", err);
      setIsLoading(false);
    }
  }, [sessionId]);

  // ---------------------------------------------------------------------------
  // Step 3: Results
  // ---------------------------------------------------------------------------
  const handleToggleSelect = useCallback((vehicleId: string) => {
    setSelectedIds((prev) =>
      prev.includes(vehicleId)
        ? prev.filter((id) => id !== vehicleId)
        : prev.length < 4
          ? [...prev, vehicleId]
          : prev,
    );
  }, []);

  const handleShortlist = useCallback(async () => {
    if (!sessionId || selectedIds.length === 0) return;
    setIsLoading(true);
    try {
      await api.createShortlist(sessionId, selectedIds);
      const dashboard = await api.getDashboard(sessionId);
      setShortlist(dashboard.shortlist);
      setCommStatus(dashboard.communication_status);
      setStep("dashboard");
    } catch (err) {
      console.error("Shortlist error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, selectedIds]);

  // ---------------------------------------------------------------------------
  // Step 4: Dashboard actions
  // ---------------------------------------------------------------------------
  const handleSendText = useCallback(
    async (vehicleId: string) => {
      if (!sessionId) return;
      try {
        await api.sendText(sessionId, vehicleId);
        setCommStatus((prev) =>
          prev.map((c) =>
            c.vehicle_id === vehicleId ? { ...c, text_sent: true } : c,
          ),
        );
      } catch (err) {
        console.error("Text error:", err);
      }
    },
    [sessionId],
  );

  const handleStartCall = useCallback(
    async (vehicleId: string) => {
      if (!sessionId) return;
      try {
        await api.startCall(sessionId, vehicleId);
        setCommStatus((prev) =>
          prev.map((c) =>
            c.vehicle_id === vehicleId ? { ...c, call_made: true } : c,
          ),
        );
      } catch (err) {
        console.error("Call error:", err);
      }
    },
    [sessionId],
  );

  const handleBookTestDrive = useCallback((vehicleId: string) => {
    setTestDriveVehicleId(vehicleId);
    setStep("testdrive");
  }, []);

  const handleTestDriveSubmit = useCallback(
    async (data: Parameters<typeof api.bookTestDrive>[1]) => {
      if (!sessionId) return;
      setIsLoading(true);
      try {
        await api.bookTestDrive(sessionId, data);
        setTestDriveVehicleId(null);
        setStep("dashboard");
      } catch (err) {
        console.error("Test drive error:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId],
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <AppLayout>
      {step === "questionnaire" && (
        <Questionnaire
          onSubmit={handlePreferencesSubmit}
          isLoading={isLoading}
        />
      )}

      {step === "chat" && (
        <ChatPanel
          messages={chatMessages}
          onSend={handleChatSend}
          onSearchReady={handleStartSearch}
          isLoading={isLoading}
          isReadyToSearch={isReadyToSearch}
        />
      )}

      {step === "searching" && (
        <div style={{ textAlign: "center", padding: 60 }}>
          <h2>Searching dealerships...</h2>
          <p style={{ color: "#6b7280" }}>
            Scraping listings and comparing prices. This may take a moment.
          </p>
        </div>
      )}

      {step === "results" && (
        <ResultsList
          vehicles={vehicles}
          priceStats={priceStats}
          selectedIds={selectedIds}
          onToggleSelect={handleToggleSelect}
          onShortlist={handleShortlist}
          isLoading={isLoading}
        />
      )}

      {step === "dashboard" && (
        <DashboardView
          shortlist={shortlist}
          communicationStatus={commStatus}
          onSendText={handleSendText}
          onStartCall={handleStartCall}
          onBookTestDrive={handleBookTestDrive}
        />
      )}

      {step === "testdrive" && testDriveVehicleId && (
        <TestDriveForm
          vehicleId={testDriveVehicleId}
          onSubmit={handleTestDriveSubmit}
          onCancel={() => setStep("dashboard")}
          isLoading={isLoading}
        />
      )}
    </AppLayout>
  );
};

export default App;
