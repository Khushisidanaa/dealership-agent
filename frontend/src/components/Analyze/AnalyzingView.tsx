import { useState, useEffect, useRef } from "react";
import { analyzeVehicles } from "../../services/api";
import type { TopVehicle, CallSummary } from "../../types";

interface DealerStatus {
  vehicle_id: string;
  dealer_name: string;
  status:
    | "waiting"
    | "calling"
    | "connected"
    | "summarizing"
    | "done"
    | "failed";
  message: string;
  summary?: CallSummary;
}

interface AnalyzingViewProps {
  sessionId: string;
  totalVehicles: number;
  onComplete: (top3: TopVehicle[]) => void;
}

const statusEmoji: Record<DealerStatus["status"], string> = {
  waiting: "",
  calling: "",
  connected: "",
  summarizing: "",
  done: "",
  failed: "",
};

const statusLabel: Record<DealerStatus["status"], string> = {
  waiting: "Waiting",
  calling: "Dialing...",
  connected: "AI talking to dealer",
  summarizing: "Summarizing call",
  done: "Complete",
  failed: "Failed",
};

const AnalyzingView = ({
  sessionId,
  totalVehicles,
  onComplete,
}: AnalyzingViewProps) => {
  const [dealers, setDealers] = useState<DealerStatus[]>([]);
  const [overallMessage, setOverallMessage] = useState(
    "Preparing to call dealers...",
  );
  const [isComplete, setIsComplete] = useState(false);
  const [top3, setTop3] = useState<TopVehicle[]>([]);
  const cancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const { cancel } = analyzeVehicles(sessionId, (eventType, data) => {
      const msg = (data.message as string) || "";

      switch (eventType) {
        case "start":
          setOverallMessage(msg);
          break;

        case "calling":
          setDealers((prev) => {
            const existing = prev.find((d) => d.vehicle_id === data.vehicle_id);
            if (existing) {
              return prev.map((d) =>
                d.vehicle_id === data.vehicle_id
                  ? { ...d, status: "calling", message: msg }
                  : d,
              );
            }
            return [
              ...prev,
              {
                vehicle_id: data.vehicle_id as string,
                dealer_name: data.dealer_name as string,
                status: "calling",
                message: msg,
              },
            ];
          });
          setOverallMessage(msg);
          break;

        case "call_connected":
          setDealers((prev) =>
            prev.map((d) =>
              d.vehicle_id === data.vehicle_id
                ? { ...d, status: "connected", message: msg }
                : d,
            ),
          );
          setOverallMessage(msg);
          break;

        case "call_complete":
          setDealers((prev) =>
            prev.map((d) =>
              d.vehicle_id === data.vehicle_id
                ? { ...d, status: "summarizing", message: msg }
                : d,
            ),
          );
          setOverallMessage(msg);
          break;

        case "call_failed":
          setDealers((prev) =>
            prev.map((d) =>
              d.vehicle_id === data.vehicle_id
                ? { ...d, status: "failed", message: "Call failed" }
                : d,
            ),
          );
          break;

        case "summary_ready":
          setDealers((prev) =>
            prev.map((d) =>
              d.vehicle_id === data.vehicle_id
                ? {
                    ...d,
                    status: "done",
                    message: msg,
                    summary: data.summary as CallSummary,
                  }
                : d,
            ),
          );
          setOverallMessage(msg);
          break;

        case "ranking":
          setOverallMessage(msg);
          break;

        case "complete": {
          const results = data.top3 as TopVehicle[];
          setTop3(results);
          setIsComplete(true);
          setOverallMessage(data.message as string);
          break;
        }

        case "error":
          setOverallMessage(`Error: ${data.message}`);
          break;
      }
    });

    cancelRef.current = cancel;
    return () => cancel();
  }, [sessionId]);

  const completedCount = dealers.filter(
    (d) => d.status === "done" || d.status === "failed",
  ).length;
  const progress =
    totalVehicles > 0 ? Math.round((completedCount / totalVehicles) * 100) : 0;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 8 }}>Analyzing Dealerships</h2>
      <p style={{ color: "#6b7280", marginBottom: 24 }}>{overallMessage}</p>

      {/* Progress bar */}
      <div
        style={{
          background: "#e5e7eb",
          borderRadius: 8,
          height: 8,
          marginBottom: 32,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: isComplete ? "#10b981" : "#3b82f6",
            height: "100%",
            width: `${isComplete ? 100 : progress}%`,
            transition: "width 0.5s ease",
            borderRadius: 8,
          }}
        />
      </div>

      {/* Dealer status cards */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          marginBottom: 32,
        }}
      >
        {dealers.map((d) => (
          <div
            key={d.vehicle_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "16px 20px",
              background:
                d.status === "done"
                  ? "#f0fdf4"
                  : d.status === "failed"
                    ? "#fef2f2"
                    : "#f9fafb",
              borderRadius: 12,
              border: `1px solid ${d.status === "done" ? "#bbf7d0" : d.status === "failed" ? "#fecaca" : "#e5e7eb"}`,
            }}
          >
            <span style={{ fontSize: 24 }}>{statusEmoji[d.status]}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                {d.dealer_name}
              </div>
              <div style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                {statusLabel[d.status]}
                {d.summary?.key_takeaways && (
                  <span
                    style={{ display: "block", marginTop: 4, color: "#374151" }}
                  >
                    {d.summary.key_takeaways}
                  </span>
                )}
              </div>
            </div>
            {d.summary?.recommendation && (
              <span
                style={{
                  padding: "4px 12px",
                  borderRadius: 20,
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  background:
                    d.summary.recommendation === "worth visiting"
                      ? "#dcfce7"
                      : d.summary.recommendation === "skip"
                        ? "#fee2e2"
                        : "#fef3c7",
                  color:
                    d.summary.recommendation === "worth visiting"
                      ? "#166534"
                      : d.summary.recommendation === "skip"
                        ? "#991b1b"
                        : "#92400e",
                }}
              >
                {d.summary.recommendation}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Top 3 results */}
      {isComplete && top3.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 16 }}>Top 3 Recommendations</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {top3.map((v) => (
              <div
                key={v.vehicle_id}
                style={{
                  padding: 24,
                  background: "#fff",
                  borderRadius: 12,
                  border:
                    v.rank === 1 ? "2px solid #3b82f6" : "1px solid #e5e7eb",
                  boxShadow:
                    v.rank === 1 ? "0 4px 12px rgba(59,130,246,0.15)" : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "start",
                  }}
                >
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          background: v.rank === 1 ? "#3b82f6" : "#6b7280",
                          color: "#fff",
                          borderRadius: "50%",
                          width: 28,
                          height: 28,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "0.85rem",
                          fontWeight: 700,
                        }}
                      >
                        {v.rank}
                      </span>
                      <h4 style={{ margin: 0, fontSize: "1.1rem" }}>
                        {v.title}
                      </h4>
                    </div>
                    <div
                      style={{
                        color: "#6b7280",
                        fontSize: "0.9rem",
                        marginLeft: 36,
                      }}
                    >
                      {v.dealer_name} | {v.mileage?.toLocaleString() || "N/A"}{" "}
                      mi
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                      ${v.price.toLocaleString()}
                    </div>
                    {v.call_summary?.pricing?.best_quoted_price && (
                      <div
                        style={{
                          fontSize: "0.85rem",
                          color: "#10b981",
                          fontWeight: 600,
                        }}
                      >
                        Best: $
                        {v.call_summary.pricing.best_quoted_price.toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>

                {/* Call summary details */}
                {v.call_summary && (
                  <div
                    style={{
                      marginTop: 16,
                      marginLeft: 36,
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: "8px 24px",
                      fontSize: "0.85rem",
                    }}
                  >
                    <div>
                      <span style={{ color: "#6b7280" }}>Available: </span>
                      <strong>
                        {v.call_summary.is_available === false
                          ? "No (Sold)"
                          : "Yes"}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: "#6b7280" }}>Negotiable: </span>
                      <strong>
                        {v.call_summary.pricing?.is_negotiable ? "Yes" : "No"}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: "#6b7280" }}>Financing: </span>
                      <strong>
                        {v.call_summary.financing?.available
                          ? v.call_summary.financing.apr_range || "Yes"
                          : "Not discussed"}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: "#6b7280" }}>Dealer vibe: </span>
                      <strong>
                        {v.call_summary.dealer_impression?.responsiveness ||
                          "N/A"}
                      </strong>
                    </div>
                    {v.call_summary.red_flags?.length > 0 && (
                      <div style={{ gridColumn: "1 / -1", color: "#dc2626" }}>
                        Red flags: {v.call_summary.red_flags.join(", ")}
                      </div>
                    )}
                    <div
                      style={{
                        gridColumn: "1 / -1",
                        marginTop: 4,
                        color: "#374151",
                      }}
                    >
                      {v.call_summary.key_takeaways}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          <button
            onClick={() => onComplete(top3)}
            style={{
              marginTop: 24,
              padding: "12px 32px",
              background: "#1a1a2e",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: "1rem",
              width: "100%",
            }}
          >
            Continue to Dashboard
          </button>
        </div>
      )}
    </div>
  );
};

export default AnalyzingView;
