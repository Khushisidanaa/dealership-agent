import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { ListingResult } from "../types";
import "./Dashboard.css";

interface DashboardProps {
  sessionId: string;
  onBackToChat: () => void;
}

export function Dashboard({ sessionId, onBackToChat }: DashboardProps) {
  const [listings, setListings] = useState<ListingResult[]>([]);
  const [totalFound, setTotalFound] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setError(null);
    try {
      const data = await api.listings.forSession(sessionId);
      setListings(data.results);
      setTotalFound(data.total_found);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setListings([]);
      setTotalFound(0);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return (
      <div className="dashboard dashboard--loading">
        <div className="dashboard-loading-spinner" />
        <p>Loading listings…</p>
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

      {listings.length === 0 && !error && (
        <div className="dashboard-empty">
          <p>No listings yet.</p>
          <p>Complete your requirements in the chat (budget, make/model, zip) and open the Dashboard again.</p>
          <button type="button" onClick={onBackToChat}>Back to Chat</button>
        </div>
      )}

      {listings.length > 0 && (
        <>
          <p className="dashboard-summary">
            {totalFound} vehicle{totalFound !== 1 ? "s" : ""} found. Showing {listings.length}.
          </p>
          <div className="dashboard-table-wrap">
            <table className="dashboard-table dashboard-table--listings">
              <thead>
                <tr>
                  <th>Dealership</th>
                  <th>Address</th>
                  <th className="dashboard-cell-distance">Distance</th>
                  <th>Car</th>
                  <th>Price</th>
                  <th>Mileage</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {listings.map((row) => (
                  <tr key={row.vehicle_id} className="dashboard-listing-row">
                    <td>{row.dealer?.name || "—"}</td>
                    <td className="dashboard-cell-address">{row.dealer?.full_address || [row.dealer?.street, row.dealer?.city, row.dealer?.state, row.dealer?.zip].filter(Boolean).join(", ") || "—"}</td>
                    <td className="dashboard-cell-distance">
                      {row.dealer_distance_miles != null ? `${row.dealer_distance_miles.toFixed(1)} mi` : "—"}
                    </td>
                    <td>{row.title || row.heading || "—"}</td>
                    <td>{row.price != null ? `$${row.price.toLocaleString()}` : "—"}</td>
                    <td>{row.miles != null ? row.miles.toLocaleString() : "—"}</td>
                    <td>
                      {row.listing_url ? (
                        <a href={row.listing_url} target="_blank" rel="noopener noreferrer" className="dashboard-link">
                          View
                        </a>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
