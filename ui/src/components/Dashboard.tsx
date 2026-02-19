import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type {
  VehicleResult,
  DashboardResponse,
  DealershipGroup,
  TestDriveBooking,
} from "../types";
import { TestDriveModal } from "./TestDriveModal";
import "./Dashboard.css";

interface DashboardProps {
  sessionId: string;
  onBackToChat: () => void;
}

function groupByDealer(data: DashboardResponse): DealershipGroup[] {
  const byDealer = new Map<string, VehicleResult[]>();
  const commByVehicle = new Map<string, (typeof data.communication_status)[0]>();
  data.communication_status.forEach((c) => commByVehicle.set(c.vehicle_id, c));

  data.shortlist.forEach((v) => {
    const key = v.dealer_name || "Unknown dealer";
    if (!byDealer.has(key)) byDealer.set(key, []);
    byDealer.get(key)!.push(v);
  });

  return Array.from(byDealer.entries()).map(([dealerName, vehicles]) => {
    const first = vehicles[0];
    const communicationStatus: Record<string, (typeof data.communication_status)[0]> = {};
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

export function Dashboard({ sessionId, onBackToChat }: DashboardProps) {
  const [groups, setGroups] = useState<DealershipGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDealer, setExpandedDealer] = useState<string | null>(null);
  const [selectedCar, setSelectedCar] = useState<VehicleResult | null>(null);
  const [testDriveVehicle, setTestDriveVehicle] = useState<VehicleResult | null>(null);
  const [bookings, setBookings] = useState<TestDriveBooking[]>([]);

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

  const toggleDealer = (name: string) => {
    setExpandedDealer((prev) => (prev === name ? null : name));
  };

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
    []
  );

  if (loading) {
    return (
      <div className="dashboard dashboard--loading">
        <div className="dashboard-loading-spinner" />
        <p>Loading dashboard…</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <button type="button" className="dashboard-back" onClick={onBackToChat}>
          ← Back to Chat
        </button>
        <button type="button" className="dashboard-refresh" onClick={() => { setLoading(true); loadDashboard(); }}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="dashboard-error">
          {error}
        </div>
      )}

      {groups.length === 0 && !error && (
        <div className="dashboard-empty">
          <p>No dealerships or cars yet.</p>
          <p>Complete your requirements in the chat and use “View Dashboard” after the AI is ready to search.</p>
          <button type="button" onClick={onBackToChat}>Back to Chat</button>
        </div>
      )}

      {groups.length > 0 && (
        <div className="dashboard-table-wrap">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th style={{ width: 32 }} />
                <th>Dealership</th>
                <th>Address</th>
                <th className="dashboard-cell-distance">Distance</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <DealerRow
                  key={g.dealerName}
                  group={g}
                  expanded={expandedDealer === g.dealerName}
                  onToggle={() => toggleDealer(g.dealerName)}
                  onSelectCar={setSelectedCar}
                  onScheduleTestDrive={setTestDriveVehicle}
                  bookings={bookings}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedCar && (
        <div className="dashboard-overlay" onClick={() => setSelectedCar(null)}>
          <div className="dashboard-detail-panel" onClick={(e) => e.stopPropagation()}>
            <div className="dashboard-detail-header">
              <h2>{selectedCar.title}</h2>
              <button type="button" className="dashboard-detail-close" onClick={() => setSelectedCar(null)}>×</button>
            </div>
            <div className="dashboard-detail-body">
              <p><strong>Dealer:</strong> {selectedCar.dealer_name}</p>
              <p><strong>Address:</strong> {selectedCar.dealer_address || "—"}</p>
              <p><strong>Price:</strong> ${selectedCar.price.toLocaleString()}</p>
              {selectedCar.mileage != null && <p><strong>Mileage:</strong> {selectedCar.mileage.toLocaleString()} mi</p>}
              <p><strong>Condition:</strong> {selectedCar.condition}</p>
              {selectedCar.features?.length > 0 && (
                <p><strong>Features:</strong> {selectedCar.features.join(", ")}</p>
              )}
              {selectedCar.known_issues?.length > 0 && (
                <p><strong>Known issues:</strong> {selectedCar.known_issues.join(", ")}</p>
              )}
              {selectedCar.listing_url && (
                <p><a href={selectedCar.listing_url} target="_blank" rel="noopener noreferrer">View listing</a></p>
              )}
              <button
                type="button"
                className="dashboard-btn-test-drive"
                onClick={() => {
                  setSelectedCar(null);
                  setTestDriveVehicle(selectedCar);
                }}
              >
                Schedule test drive
              </button>
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

function DealerRow({
  group,
  expanded,
  onToggle,
  onSelectCar,
  onScheduleTestDrive,
  bookings,
}: {
  group: DealershipGroup;
  expanded: boolean;
  onToggle: () => void;
  onSelectCar: (v: VehicleResult) => void;
  onScheduleTestDrive: (v: VehicleResult) => void;
  bookings: TestDriveBooking[];
}) {
  const hasAppointment = group.vehicles.some((v) =>
    bookings.some((b) => b.vehicle_id === v.vehicle_id)
  );
  const commStatus = group.vehicles.some(
    (v) => group.communicationStatus[v.vehicle_id]?.text_sent || group.communicationStatus[v.vehicle_id]?.call_made
  );

  return (
    <>
      <tr
        className="dashboard-dealer-row"
        onClick={onToggle}
      >
        <td className="dashboard-cell-expand">
          <span className={`dashboard-expand-icon ${expanded ? "expanded" : ""}`}>▸</span>
        </td>
        <td>
          <span className="dashboard-dealer-name">{group.dealerName}</span>
          {hasAppointment && <span className="dashboard-badge dashboard-badge--appointment">Appointment</span>}
          {commStatus && <span className="dashboard-badge dashboard-badge--contact">Contacted</span>}
        </td>
        <td className="dashboard-cell-address">{group.address || "—"}</td>
        <td className="dashboard-cell-distance">
          {group.distanceMiles != null ? `${group.distanceMiles.toFixed(1)} mi` : "—"}
        </td>
      </tr>
      {expanded && (
        <tr className="dashboard-cars-row">
          <td colSpan={4}>
            <div className="dashboard-cars-inner">
              <table className="dashboard-cars-table">
                <thead>
                  <tr>
                    <th>Car</th>
                    <th>Price</th>
                    <th>Mileage</th>
                    <th>Condition</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {group.vehicles.map((v) => {
                    const booking = bookings.find((b) => b.vehicle_id === v.vehicle_id);
                    const comm = group.communicationStatus[v.vehicle_id];
                    return (
                      <tr
                        key={v.vehicle_id}
                        className="dashboard-car-row"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectCar(v);
                        }}
                      >
                        <td>{v.title}</td>
                        <td>${v.price.toLocaleString()}</td>
                        <td>{v.mileage != null ? v.mileage.toLocaleString() : "—"}</td>
                        <td>{v.condition}</td>
                        <td className="dashboard-car-actions">
                          {comm?.text_sent && <span className="dashboard-badge small">Text sent</span>}
                          {comm?.call_made && <span className="dashboard-badge small">Called</span>}
                          {booking ? (
                            <span className="dashboard-badge dashboard-badge--appointment small">
                              Test drive: {booking.scheduled_date} {booking.scheduled_time}
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="dashboard-car-btn-test"
                              onClick={(e) => {
                                e.stopPropagation();
                                onScheduleTestDrive(v);
                              }}
                            >
                              Schedule test drive
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
