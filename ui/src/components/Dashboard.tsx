import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type {
  VehicleResult,
  DashboardResponse,
  DealershipGroup,
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

function groupByDealer(data: DashboardResponse): DealershipGroup[] {
  const byDealer = new Map<string, VehicleResult[]>();
  const commByVehicle = new Map<
    string,
    (typeof data.communication_status)[0]
  >();
  data.communication_status.forEach((c) => commByVehicle.set(c.vehicle_id, c));

  data.shortlist.forEach((v) => {
    const key = v.dealer_name || "Unknown dealer";
    if (!byDealer.has(key)) byDealer.set(key, []);
    byDealer.get(key)!.push(v);
  });

  return Array.from(byDealer.entries()).map(([dealerName, vehicles]) => {
    const first = vehicles[0];
    const communicationStatus: Record<
      string,
      (typeof data.communication_status)[0]
    > = {};
    vehicles.forEach((ve) => {
      const c = commByVehicle.get(ve.vehicle_id);
      if (c) communicationStatus[ve.vehicle_id] = c;
    });
    return {
      dealerName,
      address: first.dealer_address || "",
      distanceMiles: first.dealer_distance_miles,
      vehicles,
      communicationStatus,
    };
  });
}

export function Dashboard({
  sessionId,
  onBackToChat,
  top3: _top3,
}: DashboardProps) {
  const [groups, setGroups] = useState<DealershipGroup[]>([]);
  const [loading, setLoading] = useState(true);
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
      setGroups(groupByDealer(data));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("404") || msg.includes("No shortlist")) {
        try {
          const searchRes = await api.search.cars(sessionId);
          const ids = searchRes.results.slice(0, 30).map((v) => v.vehicle_id);
          if (ids.length > 0) {
            await api.shortlist.create(sessionId, ids, false);
            const data = await api.dashboard.get(sessionId);
            setGroups(groupByDealer(data));
          } else {
            setGroups([]);
          }
        } catch (e2: unknown) {
          setError(e2 instanceof Error ? e2.message : String(e2));
          setGroups([]);
        }
      } else {
        setError(msg);
        setGroups([]);
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

  const totalVehicles = groups.reduce((n, g) => n + g.vehicles.length, 0);

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <button type="button" className="dashboard-back" onClick={onBackToChat}>
          Back to Chat
        </button>
        <div className="dashboard-stats">
          <span className="dashboard-stat">
            {groups.length} dealer{groups.length !== 1 ? "s" : ""}
          </span>
          <span className="dashboard-stat-sep" />
          <span className="dashboard-stat">
            {totalVehicles} vehicle{totalVehicles !== 1 ? "s" : ""}
          </span>
        </div>
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

      {groups.length === 0 && !error && (
        <div className="dashboard-empty">
          <p>No vehicles found yet.</p>
          <p>Complete your requirements in the chat first.</p>
          <button type="button" onClick={onBackToChat}>
            Back to Chat
          </button>
        </div>
      )}

      <div className="dashboard-sections">
        {groups.map((g) => (
          <section key={g.dealerName} className="dashboard-section">
            <div className="dashboard-section-header">
              <div className="dashboard-section-title">
                <h3>{g.dealerName}</h3>
                {g.address && (
                  <span className="dashboard-section-addr">{g.address}</span>
                )}
              </div>
              <div className="dashboard-section-meta">
                {g.distanceMiles != null && (
                  <span className="dashboard-section-dist">
                    {g.distanceMiles.toFixed(1)} mi
                  </span>
                )}
                <span className="dashboard-section-count">
                  {g.vehicles.length} car{g.vehicles.length !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
            <div className="dashboard-card-grid">
              {g.vehicles.map((v) => {
                const imgSrc = imgErrors.has(v.vehicle_id)
                  ? PLACEHOLDER_IMG
                  : v.image_urls?.[0] || PLACEHOLDER_IMG;
                const booking = bookings.find(
                  (b) => b.vehicle_id === v.vehicle_id,
                );
                const comm = g.communicationStatus[v.vehicle_id];
                const hasContact = comm?.text_sent || comm?.call_made;

                return (
                  <div
                    key={v.vehicle_id}
                    className="dashboard-card"
                    onClick={() => setSelectedCar(v)}
                  >
                    <div className="dashboard-card-img-wrap">
                      <img
                        src={imgSrc}
                        alt={v.title}
                        className="dashboard-card-img"
                        onError={() => handleImgError(v.vehicle_id)}
                      />
                      {booking && (
                        <span className="dashboard-card-badge dashboard-card-badge--booked">
                          Test Drive Booked
                        </span>
                      )}
                      {hasContact && !booking && (
                        <span className="dashboard-card-badge dashboard-card-badge--contacted">
                          Contacted
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
                        {v.condition && <span>{v.condition}</span>}
                      </div>
                      {v.features && v.features.length > 0 && (
                        <div className="dashboard-card-features">
                          {v.features.slice(0, 4).map((f) => (
                            <span key={f} className="dashboard-card-tag">
                              {f}
                            </span>
                          ))}
                        </div>
                      )}
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
        ))}
      </div>

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
                src={
                  imgErrors.has(selectedCar.vehicle_id)
                    ? PLACEHOLDER_IMG
                    : selectedCar.image_urls?.[0] || PLACEHOLDER_IMG
                }
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
              {selectedCar.known_issues &&
                selectedCar.known_issues.length > 0 && (
                  <div className="dashboard-detail-issues">
                    <strong>Known issues:</strong>{" "}
                    {selectedCar.known_issues.join(", ")}
                  </div>
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
