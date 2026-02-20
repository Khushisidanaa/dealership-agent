import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type {
  VehicleResult,
  CommunicationStatusOut,
  CallSummary,
  TestDriveBooking,
  TopVehicle,
} from "../types";
import { TestDriveModal } from "./TestDriveModal";
import "./Dashboard.css";

interface DashboardProps {
  sessionId: string;
  onBackToChat: () => void;
  top3?: TopVehicle[];
}

const PLACEHOLDER_IMG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='200' fill='%231e2a3a'%3E%3Crect width='320' height='200'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%236b7a8f' font-size='14' font-family='system-ui'%3ENo Image%3C/text%3E%3C/svg%3E";

export function Dashboard({
  sessionId,
  onBackToChat,
  top3: propsTop3,
}: DashboardProps) {
  const [vehicles, setVehicles] = useState<VehicleResult[]>([]);
  const [comms, setComms] = useState<Map<string, CommunicationStatusOut>>(
    new Map(),
  );
  const [loading, setLoading] = useState(true);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCar, setSelectedCar] = useState<VehicleResult | null>(null);
  const [testDriveVehicle, setTestDriveVehicle] =
    useState<VehicleResult | null>(null);
  const [bookings, setBookings] = useState<TestDriveBooking[]>([]);
  const [imgErrors, setImgErrors] = useState<Set<string>>(new Set());

  const handleImgError = useCallback((id: string) => {
    setImgErrors((prev) => new Set(prev).add(id));
  }, []);

  const loadDashboard = useCallback(async () => {
    setError(null);
    try {
      const data = await api.dashboard.get(sessionId);
      setVehicles(data.shortlist);
      const commMap = new Map<string, CommunicationStatusOut>();
      data.communication_status.forEach((c) => commMap.set(c.vehicle_id, c));
      setComms(commMap);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("404") || msg.includes("No shortlist")) {
        try {
          const searchRes = await api.search.cars(sessionId);
          const ids = searchRes.results.slice(0, 30).map((v) => v.vehicle_id);
          if (ids.length > 0) {
            await api.shortlist.create(sessionId, ids, false);
            const data = await api.dashboard.get(sessionId);
            setVehicles(data.shortlist);
            const commMap = new Map<string, CommunicationStatusOut>();
            data.communication_status.forEach((c) =>
              commMap.set(c.vehicle_id, c),
            );
            setComms(commMap);
          } else {
            setVehicles([]);
          }
        } catch (e2: unknown) {
          setError(e2 instanceof Error ? e2.message : String(e2));
          setVehicles([]);
        }
      } else {
        setError(msg);
        setVehicles([]);
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const addBooking = useCallback(
    (res: {
      booking_id: string;
      vehicle_id: string;
      vehicle_title: string;
      dealer_name: string;
      scheduled_date: string;
      scheduled_time: string;
      status: string;
    }) => {
      setBookings((prev) => [...prev, res]);
    },
    [],
  );

  if (loading) {
    return (
      <div className="dashboard dashboard--loading">
        <div className="dashboard-loading-spinner" />
        <p>Loading dashboard...</p>
      </div>
    );
  }

  const contactedVehicles = vehicles.filter((v) => {
    const c = comms.get(v.vehicle_id);
    return c && (c.call_made || c.text_sent);
  });

  const otherVehicles = vehicles.filter((v) => {
    const c = comms.get(v.vehicle_id);
    return !c || (!c.call_made && !c.text_sent);
  });

  const imgSrc = (v: VehicleResult) =>
    imgErrors.has(v.vehicle_id)
      ? PLACEHOLDER_IMG
      : v.image_urls?.[0] || PLACEHOLDER_IMG;

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <button
          type="button"
          className="dashboard-back"
          onClick={onBackToChat}
          title="Go back to search results"
        >
          Back to Results
        </button>
        <div className="dashboard-stats">
          <span className="dashboard-stat">
            {vehicles.length} vehicle{vehicles.length !== 1 ? "s" : ""}
          </span>
          {contactedVehicles.length > 0 && (
            <>
              <span className="dashboard-stat-sep" />
              <span className="dashboard-stat">
                {contactedVehicles.length} contacted
              </span>
            </>
          )}
        </div>
        <button
          type="button"
          className="dashboard-refresh"
          onClick={async () => {
            setExportingPdf(true);
            try {
              const blob = await api.dashboard.exportPdf(sessionId);
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `dashboard_report_${sessionId.slice(0, 8)}.pdf`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e));
            } finally {
              setExportingPdf(false);
            }
          }}
          disabled={exportingPdf || vehicles.length === 0}
          title="Export dashboard as PDF"
        >
          {exportingPdf ? "Exporting…" : "Export PDF"}
        </button>
        <button
          type="button"
          className="dashboard-refresh"
          onClick={() => {
            setLoading(true);
            loadDashboard();
          }}
        >
          Refresh
        </button>
      </div>

      {error && <div className="dashboard-error">{error}</div>}

      {vehicles.length === 0 && !error && (
        <div className="dashboard-empty">
          <p>No vehicles found yet.</p>
          <p>Go back to results to select vehicles for your dashboard.</p>
          <button type="button" onClick={onBackToChat}>
            Back to Results
          </button>
        </div>
      )}

      {contactedVehicles.length > 0 && (
        <section className="db-section">
          <div className="db-section-header">
            <h2 className="db-section-title">
              <span className="db-section-icon db-section-icon--call">
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
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
              </span>
              Dealer Call Results
            </h2>
            <span className="db-section-count">
              {contactedVehicles.length} call
              {contactedVehicles.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="db-call-grid">
            {contactedVehicles.map((v) => {
              const c = comms.get(v.vehicle_id);
              const details = c?.call_details;
              const booking = bookings.find(
                (b) => b.vehicle_id === v.vehicle_id,
              );
              return (
                <CallResultCard
                  key={v.vehicle_id}
                  vehicle={v}
                  details={details ?? null}
                  summary={c?.response ?? null}
                  imgSrc={imgSrc(v)}
                  onImgError={() => handleImgError(v.vehicle_id)}
                  booking={booking ?? null}
                  onSchedule={() => setTestDriveVehicle(v)}
                  onViewDetail={() => setSelectedCar(v)}
                />
              );
            })}
          </div>
        </section>
      )}

      {propsTop3 && propsTop3.length > 0 && (
        <section className="db-section">
          <div className="db-section-header">
            <h2 className="db-section-title">
              <span className="db-section-icon db-section-icon--star">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  stroke="none"
                >
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </span>
              AI Top Recommendations
            </h2>
          </div>
          <div className="db-top-grid">
            {propsTop3.map((t, i) => (
              <TopPickCard
                key={t.vehicle_id}
                pick={t}
                rank={i + 1}
                onSchedule={() => {
                  const match = vehicles.find(
                    (v) => v.vehicle_id === t.vehicle_id,
                  );
                  if (match) setTestDriveVehicle(match);
                }}
              />
            ))}
          </div>
        </section>
      )}

      {otherVehicles.length > 0 && (
        <section className="db-section">
          <div className="db-section-header">
            <h2 className="db-section-title">All Vehicles</h2>
            <span className="db-section-count">
              {otherVehicles.length} vehicle
              {otherVehicles.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="dashboard-card-grid">
            {otherVehicles.map((v) => {
              const booking = bookings.find(
                (b) => b.vehicle_id === v.vehicle_id,
              );
              return (
                <div
                  key={v.vehicle_id}
                  className="dashboard-card"
                  onClick={() => setSelectedCar(v)}
                >
                  <div className="dashboard-card-img-wrap">
                    <img
                      src={imgSrc(v)}
                      alt={v.title}
                      className="dashboard-card-img"
                      onError={() => handleImgError(v.vehicle_id)}
                    />
                    {booking && (
                      <span className="dashboard-card-badge dashboard-card-badge--booked">
                        Test Drive Booked
                      </span>
                    )}
                  </div>
                  <div className="dashboard-card-body">
                    <h4 className="dashboard-card-title">{v.title}</h4>
                    <div className="dashboard-card-price">
                      ${v.price.toLocaleString()}
                    </div>
                    <div className="dashboard-card-details">
                      {v.mileage != null && (
                        <span>{v.mileage.toLocaleString()} mi</span>
                      )}
                      {v.dealer_name && <span>{v.dealer_name}</span>}
                    </div>
                    <div className="dashboard-card-actions">
                      {booking ? (
                        <span className="dashboard-card-booked-info">
                          {booking.scheduled_date} at {booking.scheduled_time}
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="dashboard-card-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setTestDriveVehicle(v);
                          }}
                        >
                          Schedule Test Drive
                        </button>
                      )}
                      {v.listing_url && (
                        <a
                          href={v.listing_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="dashboard-card-link"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View Listing
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {selectedCar && (
        <div className="dashboard-overlay" onClick={() => setSelectedCar(null)}>
          <div
            className="dashboard-detail-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="dashboard-detail-close"
              onClick={() => setSelectedCar(null)}
            >
              x
            </button>
            <div className="dashboard-detail-img-wrap">
              <img
                src={imgSrc(selectedCar)}
                alt={selectedCar.title}
                className="dashboard-detail-img"
                onError={() => handleImgError(selectedCar.vehicle_id)}
              />
            </div>
            <div className="dashboard-detail-body">
              <h2>{selectedCar.title}</h2>
              <div className="dashboard-detail-price">
                ${selectedCar.price.toLocaleString()}
              </div>
              <div className="dashboard-detail-meta">
                <span>Dealer: {selectedCar.dealer_name}</span>
                {selectedCar.dealer_address && (
                  <span>{selectedCar.dealer_address}</span>
                )}
                {selectedCar.mileage != null && (
                  <span>{selectedCar.mileage.toLocaleString()} miles</span>
                )}
                <span>Condition: {selectedCar.condition}</span>
              </div>
              {selectedCar.features && selectedCar.features.length > 0 && (
                <div className="dashboard-detail-features">
                  {selectedCar.features.map((f) => (
                    <span key={f} className="dashboard-card-tag">
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {comms.has(selectedCar.vehicle_id) && (
                <DetailCallSection comm={comms.get(selectedCar.vehicle_id)!} />
              )}

              <div className="dashboard-detail-actions">
                <button
                  type="button"
                  className="dashboard-card-btn"
                  onClick={() => {
                    setSelectedCar(null);
                    setTestDriveVehicle(selectedCar);
                  }}
                >
                  Schedule Test Drive
                </button>
                {selectedCar.listing_url && (
                  <a
                    href={selectedCar.listing_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="dashboard-card-link"
                  >
                    View Listing
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {testDriveVehicle && (
        <TestDriveModal
          sessionId={sessionId}
          vehicle={testDriveVehicle}
          onClose={() => setTestDriveVehicle(null)}
          onBooked={addBooking}
        />
      )}
    </div>
  );
}

function AvailabilityBadge({ value }: { value: boolean | null | undefined }) {
  if (value === true)
    return <span className="db-badge db-badge--yes">Available</span>;
  if (value === false)
    return <span className="db-badge db-badge--no">Sold / Unavailable</span>;
  return <span className="db-badge db-badge--unknown">Unknown</span>;
}

function RecommendationBadge({ value }: { value: string | undefined }) {
  if (!value) return null;
  const cls =
    value === "worth visiting"
      ? "db-badge--yes"
      : value === "skip"
        ? "db-badge--no"
        : "db-badge--unknown";
  return <span className={`db-badge ${cls}`}>{value}</span>;
}

function CallResultCard({
  vehicle,
  details,
  summary,
  imgSrc,
  onImgError,
  booking,
  onSchedule,
  onViewDetail,
}: {
  vehicle: VehicleResult;
  details: CallSummary | null;
  summary: string | null;
  imgSrc: string;
  onImgError: () => void;
  booking: TestDriveBooking | null;
  onSchedule: () => void;
  onViewDetail: () => void;
}) {
  return (
    <div className="db-call-card" onClick={onViewDetail}>
      <div className="db-call-card-left">
        <div className="db-call-card-img-wrap">
          <img src={imgSrc} alt={vehicle.title} onError={onImgError} />
        </div>
        <div className="db-call-card-vehicle">
          <h4>{vehicle.title}</h4>
          <div className="db-call-card-price">
            ${vehicle.price.toLocaleString()}
          </div>
          <div className="db-call-card-dealer">{vehicle.dealer_name}</div>
        </div>
      </div>
      <div className="db-call-card-right">
        {details ? (
          <div className="db-call-details">
            <div className="db-call-row">
              <span className="db-call-label">Availability</span>
              <AvailabilityBadge value={details.is_available} />
            </div>
            {details.pricing?.best_quoted_price != null && (
              <div className="db-call-row">
                <span className="db-call-label">Best Quoted</span>
                <span className="db-call-value db-call-value--accent">
                  ${details.pricing.best_quoted_price.toLocaleString()}
                </span>
              </div>
            )}
            {details.pricing?.is_negotiable && (
              <div className="db-call-row">
                <span className="db-call-label">Negotiable</span>
                <span className="db-badge db-badge--yes">Yes</span>
              </div>
            )}
            {details.financing?.available && (
              <div className="db-call-row">
                <span className="db-call-label">Financing</span>
                <span className="db-badge db-badge--yes">
                  Available
                  {details.financing.apr_range
                    ? ` (${details.financing.apr_range})`
                    : ""}
                </span>
              </div>
            )}
            {details.dealer_impression?.responsiveness && (
              <div className="db-call-row">
                <span className="db-call-label">Dealer</span>
                <span className="db-call-value">
                  {details.dealer_impression.responsiveness}
                </span>
              </div>
            )}
            {details.red_flags && details.red_flags.length > 0 && (
              <div className="db-call-row db-call-row--flags">
                <span className="db-call-label">Red Flags</span>
                <span className="db-call-value db-call-value--warn">
                  {details.red_flags.join(", ")}
                </span>
              </div>
            )}
            <div className="db-call-row">
              <span className="db-call-label">Verdict</span>
              <RecommendationBadge value={details.recommendation} />
            </div>
            {details.key_takeaways && (
              <p className="db-call-takeaway">{details.key_takeaways}</p>
            )}
          </div>
        ) : (
          <div className="db-call-details">
            {summary && <p className="db-call-takeaway">{summary}</p>}
            {!summary && (
              <p className="db-call-takeaway db-call-takeaway--muted">
                No call details available.
              </p>
            )}
          </div>
        )}
        <div className="db-call-card-actions">
          {booking ? (
            <span className="dashboard-card-booked-info">
              Test drive: {booking.scheduled_date} at {booking.scheduled_time}
            </span>
          ) : (
            <button
              type="button"
              className="dashboard-card-btn"
              onClick={(e) => {
                e.stopPropagation();
                onSchedule();
              }}
            >
              Schedule Test Drive
            </button>
          )}
          {vehicle.listing_url && (
            <a
              href={vehicle.listing_url}
              target="_blank"
              rel="noopener noreferrer"
              className="dashboard-card-link"
              onClick={(e) => e.stopPropagation()}
            >
              View Listing
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function TopPickCard({
  pick,
  rank,
  onSchedule,
}: {
  pick: TopVehicle;
  rank: number;
  onSchedule: () => void;
}) {
  const [imgErr, setImgErr] = useState(false);
  const src = imgErr
    ? PLACEHOLDER_IMG
    : pick.image_urls?.[0] || PLACEHOLDER_IMG;
  const s = pick.call_summary;

  return (
    <div className="db-top-card">
      <div className="db-top-card-img-wrap">
        <img src={src} alt={pick.title} onError={() => setImgErr(true)} />
        <span className="db-top-rank">#{rank}</span>
      </div>
      <div className="db-top-card-body">
        <h4>{pick.title}</h4>
        <span className="db-top-price">${pick.price.toLocaleString()}</span>
        <span className="db-top-dealer">{pick.dealer_name}</span>
        {s && (
          <div className="db-top-summary">
            <AvailabilityBadge value={s.is_available} />
            {s.pricing?.best_quoted_price != null && (
              <span className="db-top-quoted">
                Quoted: ${s.pricing.best_quoted_price.toLocaleString()}
              </span>
            )}
            <RecommendationBadge value={s.recommendation} />
          </div>
        )}
        <button
          type="button"
          className="dashboard-card-btn db-top-btn"
          onClick={onSchedule}
        >
          Schedule Test Drive
        </button>
      </div>
    </div>
  );
}

function DetailCallSection({ comm }: { comm: CommunicationStatusOut }) {
  const d = comm.call_details;
  if (!d && !comm.response) return null;

  return (
    <div className="db-detail-call">
      <h3>Call Results</h3>
      {d ? (
        <div className="db-call-details">
          <div className="db-call-row">
            <span className="db-call-label">Availability</span>
            <AvailabilityBadge value={d.is_available} />
          </div>
          {d.pricing?.best_quoted_price != null && (
            <div className="db-call-row">
              <span className="db-call-label">Best Quoted</span>
              <span className="db-call-value db-call-value--accent">
                ${d.pricing.best_quoted_price.toLocaleString()}
              </span>
            </div>
          )}
          {d.key_takeaways && (
            <p className="db-call-takeaway">{d.key_takeaways}</p>
          )}
        </div>
      ) : (
        <p className="db-call-takeaway">{comm.response}</p>
      )}
    </div>
  );
}
