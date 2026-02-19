import { useState, useEffect, useRef, useCallback } from "react";
import { analyzeVehicles } from "../api/client";
import type {
  VehicleResult,
  TopVehicle,
  DealerCallState,
  DealerCallStatus,
  CallSummary,
} from "../types";
import "./AnalyzingView.css";

interface AnalyzingViewProps {
  sessionId: string;
  vehicles: VehicleResult[];
  onComplete: (top3: TopVehicle[], allVehicles: VehicleResult[]) => void;
  onBack: () => void;
}

const STATUS_LABELS: Record<DealerCallStatus, string> = {
  pending: "Waiting...",
  calling: "Dialing...",
  connected: "AI agent talking...",
  done: "Call complete",
  failed: "Call failed",
};

const STATUS_COLORS: Record<DealerCallStatus, string> = {
  pending: "var(--text-muted)",
  calling: "var(--warning)",
  connected: "var(--accent)",
  done: "var(--success)",
  failed: "var(--error)",
};

const PLACEHOLDER_IMG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80' fill='%231e2a3a'%3E%3Crect width='80' height='80'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%236b7a8f' font-size='11' font-family='system-ui'%3ENo Img%3C/text%3E%3C/svg%3E";

export function AnalyzingView({
  sessionId,
  vehicles,
  onComplete,
  onBack,
}: AnalyzingViewProps) {
  const [dealers, setDealers] = useState<DealerCallState[]>([]);
  const [overallMessage, setOverallMessage] = useState(
    "Preparing to call dealers...",
  );
  const [phase, setPhase] = useState<"calling" | "ranking" | "done">("calling");
  const [top3, setTop3] = useState<TopVehicle[]>([]);
  const [expandedTranscript, setExpandedTranscript] = useState<string | null>(
    null,
  );
  const cancelRef = useRef<(() => void) | null>(null);
  const startedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const updateDealer = useCallback(
    (vid: string, patch: Partial<DealerCallState>) => {
      setDealers((prev) =>
        prev.map((d) => (d.vehicle_id === vid ? { ...d, ...patch } : d)),
      );
    },
    [],
  );

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    const { cancel } = analyzeVehicles(sessionId, (eventType, data) => {
      switch (eventType) {
        case "start": {
          const total = (data.total_vehicles as number) || 0;
          setOverallMessage(
            `Calling ${total} dealer${total !== 1 ? "s" : ""}...`,
          );
          break;
        }
        case "calling": {
          const vid = data.vehicle_id as string;
          setDealers((prev) => {
            const hasEntry = prev.some((d) => d.vehicle_id === vid);
            if (hasEntry) {
              return prev.map((d) =>
                d.vehicle_id === vid
                  ? {
                      ...d,
                      status: "calling" as const,
                      message: (data.message as string) || "",
                    }
                  : d,
              );
            }
            return [
              ...prev,
              {
                vehicle_id: vid,
                dealer_name: (data.dealer_name as string) || "",
                title: (data.message as string) || "",
                status: "calling" as const,
                transcript_text: "",
                summary: null,
                message: (data.message as string) || "",
              },
            ];
          });
          setOverallMessage((data.message as string) || "Calling dealer...");
          break;
        }
        case "call_connected": {
          updateDealer(data.vehicle_id as string, {
            status: "connected",
            message: (data.message as string) || "",
          });
          setOverallMessage(
            (data.message as string) || "AI agent is talking...",
          );
          break;
        }
        case "call_complete": {
          updateDealer(data.vehicle_id as string, {
            status: "done",
            transcript_text: (data.transcript_text as string) || "",
            message: (data.message as string) || "",
          });
          break;
        }
        case "call_failed": {
          const errMsg =
            (data.message as string) || (data.error as string) || "Call failed";
          updateDealer(data.vehicle_id as string, {
            status: "failed",
            message: errMsg,
          });
          setOverallMessage(errMsg);
          break;
        }
        case "summary_ready": {
          updateDealer(data.vehicle_id as string, {
            summary: (data.summary as CallSummary) || null,
          });
          setOverallMessage((data.message as string) || "Summary ready.");
          break;
        }
        case "ranking": {
          setPhase("ranking");
          setOverallMessage("Ranking vehicles based on call insights...");
          break;
        }
        case "complete": {
          const results = (data.top3 as TopVehicle[]) || [];
          setTop3(results);
          setPhase("done");
          setOverallMessage((data.message as string) || "Analysis complete!");
          break;
        }
        case "error": {
          setOverallMessage(`Error: ${data.message}`);
          break;
        }
      }
    });
    cancelRef.current = cancel;
    return () => cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const doneCount = dealers.filter(
    (d) => d.status === "done" || d.status === "failed",
  ).length;
  const totalCount = dealers.length || 0;
  const isConnecting = dealers.length === 0 && phase === "calling";
  const progressPct =
    phase === "done"
      ? 100
      : phase === "ranking"
        ? 90
        : totalCount > 0
          ? Math.round((doneCount / totalCount) * 80)
          : 5;

  return (
    <div className="analyzing">
      {/* Progress Header */}
      <div className="analyzing-header">
        <h2>{overallMessage}</h2>
        <div className="analyzing-progress-bar">
          <div
            className="analyzing-progress-fill"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <p className="analyzing-progress-text">
          {phase === "done"
            ? "All done!"
            : phase === "ranking"
              ? "Analyzing call data..."
              : totalCount > 0
                ? `${doneCount} of ${totalCount} calls complete`
                : "Setting up calls..."}
        </p>
      </div>

      {/* Connecting / pre-call loading state */}
      {isConnecting && (
        <div className="analyzing-connecting">
          <div className="connecting-animation">
            <div className="connecting-phone">
              <svg
                width="36"
                height="36"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
            </div>
            <div className="connecting-waves">
              <span className="wave wave-1" />
              <span className="wave wave-2" />
              <span className="wave wave-3" />
            </div>
          </div>
          <div className="connecting-steps">
            <div className="connecting-step connecting-step--active">
              <span className="pulse-dot" />
              <span>Connecting to AI voice agent...</span>
            </div>
            <div className="connecting-step">
              <span className="step-dot" />
              <span>Preparing dealer questions</span>
            </div>
            <div className="connecting-step">
              <span className="step-dot" />
              <span>Starting outbound calls</span>
            </div>
          </div>
          <div className="connecting-skeleton-cards">
            {[0, 1].map((i) => (
              <div key={i} className="skeleton-card">
                <div className="skeleton-thumb shimmer" />
                <div className="skeleton-lines">
                  <div className="skeleton-line skeleton-line--wide shimmer" />
                  <div className="skeleton-line skeleton-line--medium shimmer" />
                  <div className="skeleton-line skeleton-line--narrow shimmer" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dealer Call Cards */}
      {dealers.length > 0 && (
        <div className="analyzing-calls">
          <h3>Dealer Calls</h3>
          <div className="call-cards">
            {dealers.map((d) => {
              const vehicle = vehicles.find(
                (v) => v.vehicle_id === d.vehicle_id,
              );
              const imgSrc = vehicle?.image_urls?.[0] || PLACEHOLDER_IMG;
              const isExpanded = expandedTranscript === d.vehicle_id;

              return (
                <div
                  key={d.vehicle_id}
                  className={`call-card call-card--${d.status}`}
                >
                  <div className="call-card-top">
                    <img
                      src={imgSrc}
                      alt=""
                      className="call-card-thumb"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = PLACEHOLDER_IMG;
                      }}
                    />
                    <div className="call-card-info">
                      <div className="call-card-dealer">{d.dealer_name}</div>
                      <div className="call-card-vehicle">
                        {vehicle?.title || d.vehicle_id}
                      </div>
                      <div
                        className="call-card-status"
                        style={{ color: STATUS_COLORS[d.status] }}
                      >
                        {d.status === "calling" && (
                          <span className="pulse-dot" />
                        )}
                        {d.status === "connected" && (
                          <span className="pulse-dot pulse-dot--active" />
                        )}
                        {STATUS_LABELS[d.status]}
                      </div>
                    </div>
                  </div>

                  {/* Summary snippet */}
                  {d.summary && (
                    <div className="call-card-summary">
                      <div className="call-summary-row">
                        <span className="call-summary-label">Available:</span>
                        <span
                          className={
                            d.summary.is_available ? "tag-yes" : "tag-no"
                          }
                        >
                          {d.summary.is_available ? "Yes" : "No / Sold"}
                        </span>
                      </div>
                      {d.summary.pricing?.best_quoted_price && (
                        <div className="call-summary-row">
                          <span className="call-summary-label">
                            Best price:
                          </span>
                          <span className="call-summary-value">
                            $
                            {d.summary.pricing.best_quoted_price.toLocaleString()}
                          </span>
                        </div>
                      )}
                      {d.summary.pricing?.is_negotiable && (
                        <div className="call-summary-row">
                          <span className="tag-negotiable">Negotiable</span>
                        </div>
                      )}
                      <div className="call-summary-takeaway">
                        {d.summary.key_takeaways}
                      </div>
                      {d.summary.red_flags?.length > 0 && (
                        <div className="call-summary-flags">
                          {d.summary.red_flags.map((f, i) => (
                            <span key={i} className="tag-flag">
                              {f}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Transcript toggle */}
                  {d.transcript_text && (
                    <div className="call-card-transcript-toggle">
                      <button
                        type="button"
                        className="btn-transcript"
                        onClick={() =>
                          setExpandedTranscript(
                            isExpanded ? null : d.vehicle_id,
                          )
                        }
                      >
                        {isExpanded ? "Hide Transcript" : "Show Transcript"}
                      </button>
                      {isExpanded && (
                        <pre className="call-card-transcript">
                          {d.transcript_text}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Top 3 Recommendations */}
      {phase === "done" && top3.length > 0 && (
        <div className="analyzing-recommendations">
          <h3>My Top {top3.length} Recommendations</h3>
          <p className="rec-subtitle">
            Based on search data and dealer conversations
          </p>
          <div className="rec-cards">
            {top3.map((v) => (
              <RecommendationCard key={v.vehicle_id} vehicle={v} />
            ))}
          </div>
          <div className="rec-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => onCompleteRef.current(top3, vehicles)}
            >
              Continue to Dashboard
            </button>
            <button type="button" className="btn-secondary" onClick={onBack}>
              Search Again
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ vehicle }: { vehicle: TopVehicle }) {
  const imgSrc = vehicle.image_urls?.[0] || PLACEHOLDER_IMG;
  const [imgError, setImgError] = useState(false);
  const s = vehicle.call_summary;

  return (
    <div className="rec-card">
      <div className="rec-card-rank">#{vehicle.rank}</div>
      <div className="rec-card-img-wrap">
        <img
          src={imgError ? PLACEHOLDER_IMG : imgSrc}
          alt={vehicle.title}
          className="rec-card-img"
          onError={() => setImgError(true)}
        />
      </div>
      <div className="rec-card-body">
        <h4 className="rec-card-title">{vehicle.title}</h4>
        <div className="rec-card-price">
          ${(vehicle.price || 0).toLocaleString()}
        </div>
        {s?.pricing?.best_quoted_price &&
          s.pricing.best_quoted_price < vehicle.price && (
            <div className="rec-card-deal">
              Dealer quoted ${s.pricing.best_quoted_price.toLocaleString()}{" "}
              <span className="rec-savings">
                (save $
                {(vehicle.price - s.pricing.best_quoted_price).toLocaleString()}
                )
              </span>
            </div>
          )}
        <div className="rec-card-dealer">{vehicle.dealer_name}</div>
        {vehicle.features?.length > 0 && (
          <div className="rec-card-features">
            {vehicle.features.slice(0, 3).map((f) => (
              <span key={f} className="vehicle-card-feature-tag">
                {f}
              </span>
            ))}
          </div>
        )}
        {s && (
          <div className="rec-card-insight">
            <div className="rec-insight-row">
              <span className={s.is_available ? "tag-yes" : "tag-no"}>
                {s.is_available ? "Available" : "Sold"}
              </span>
              {s.pricing?.is_negotiable && (
                <span className="tag-negotiable">Negotiable</span>
              )}
              {s.financing?.available && (
                <span className="tag-finance">Financing</span>
              )}
            </div>
            {s.recommendation && (
              <div
                className={`rec-verdict rec-verdict--${s.recommendation.replace(/\s/g, "-")}`}
              >
                {s.recommendation === "worth visiting"
                  ? "Worth Visiting"
                  : s.recommendation === "skip"
                    ? "Skip"
                    : s.recommendation}
              </div>
            )}
            <p className="rec-takeaway">{s.key_takeaways}</p>
          </div>
        )}
        {vehicle.listing_url && (
          <a
            href={vehicle.listing_url}
            target="_blank"
            rel="noopener noreferrer"
            className="vehicle-card-link"
          >
            View listing
          </a>
        )}
      </div>
    </div>
  );
}
