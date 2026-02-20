import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { VehicleResult } from "../types";
import "./RecommendationsView.css";

interface RecommendationsViewProps {
  sessionId: string;
  onStartCalling: (vehicles: VehicleResult[]) => void;
  onBack: () => void;
  onChangeRequirements?: () => void;
}

const PLACEHOLDER_IMG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='260' fill='%231e2a3a'%3E%3Crect width='400' height='260'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%236b7a8f' font-size='16' font-family='system-ui'%3ENo Image%3C/text%3E%3C/svg%3E";

const TOP_COUNT = 5;

export function RecommendationsView({
  sessionId,
  onStartCalling,
  onBack,
  onChangeRequirements,
}: RecommendationsViewProps) {
  const [vehicles, setVehicles] = useState<VehicleResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [aiPicking, setAiPicking] = useState(false);

  const fetchResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.search.cars(sessionId);
      const results =
        data.results ??
        (data as unknown as { vehicles: VehicleResult[] }).vehicles ??
        [];
      setVehicles(results);
      const topIds = results
        .slice(0, Math.min(2, results.length))
        .map((v) => v.vehicle_id);
      setSelected(new Set(topIds));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch results");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const autoSelectTop = () => {
    const topIds = vehicles
      .slice(0, Math.min(2, vehicles.length))
      .map((v) => v.vehicle_id);
    setSelected(new Set(topIds));
  };

  const handleAiPickBestTwo = async () => {
    setAiPicking(true);
    setError(null);
    try {
      const { vehicle_ids } = await api.recommendations.pickBestTwo(sessionId);
      if (vehicle_ids.length === 0) return;
      const idSet = new Set(vehicle_ids);
      const byId = new Map(vehicles.map((v) => [v.vehicle_id, v]));
      const picked = vehicle_ids.map((id) => byId.get(id)).filter(Boolean) as VehicleResult[];
      const rest = vehicles.filter((v) => !idSet.has(v.vehicle_id));
      setVehicles([...picked, ...rest]);
      setSelected(new Set(vehicle_ids));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "AI pick failed");
    } finally {
      setAiPicking(false);
    }
  };

  const handleCall = () => {
    const selectedVehicles = vehicles.filter((v) => selected.has(v.vehicle_id));
    if (selectedVehicles.length === 0) return;
    onStartCalling(selectedVehicles);
  };

  if (loading) {
    return (
      <div className="rec-view-loading">
        <div className="rec-view-spinner" />
        <h2>Searching for vehicles...</h2>
        <p>Scanning thousands of listings near you</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rec-view-loading">
        <p className="rec-view-error">{error}</p>
        <button
          type="button"
          className="rv-btn rv-btn--primary"
          onClick={fetchResults}
        >
          Retry
        </button>
      </div>
    );
  }

  if (vehicles.length === 0) {
    return (
      <div className="rec-view-loading">
        <h2>No vehicles found</h2>
        <p>Try adjusting your preferences in the chat or form</p>
        <button
          type="button"
          className="rv-btn rv-btn--secondary"
          onClick={onChangeRequirements ?? onBack}
        >
          Change requirements
        </button>
      </div>
    );
  }

  const topVehicles = vehicles.slice(0, TOP_COUNT);
  const restVehicles = vehicles.slice(TOP_COUNT);

  return (
    <div className="rec-view">
      <div className="rec-view-header">
        <div>
          <h2>Our Recommendations</h2>
          <p>
            {vehicles.length} vehicles found -- top{" "}
            {Math.min(TOP_COUNT, vehicles.length)} highlighted for you
          </p>
        </div>
        <div className="rec-view-header-actions">
          {onChangeRequirements && (
            <button
              type="button"
              className="rv-btn rv-btn--ghost"
              onClick={onChangeRequirements}
              title="Edit requirements in the form or chat with AI"
            >
              Change requirements
            </button>
          )}
          <button
            type="button"
            className="rv-btn rv-btn--ghost"
            onClick={handleAiPickBestTwo}
            disabled={aiPicking || vehicles.length < 2}
            title="Use AI to pick the best 2 cars from your requirements and chat"
          >
            {aiPicking ? "Picking…" : "AI picks best 2"}
          </button>
          <button
            type="button"
            className="rv-btn rv-btn--ghost"
            onClick={autoSelectTop}
          >
            Auto-select Top 2
          </button>
          <button
            type="button"
            className="rv-btn rv-btn--primary rv-btn--call"
            onClick={handleCall}
            disabled={selected.size === 0}
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
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
            Call {selected.size} Dealer{selected.size !== 1 ? "s" : ""}
          </button>
        </div>
      </div>

      <section className="rec-top-section">
        <h3 className="rec-section-title">
          <span className="rec-section-badge">Top Picks</span>
        </h3>
        <div className="rec-top-grid">
          {topVehicles.map((v, i) => (
            <VehicleCard
              key={v.vehicle_id}
              vehicle={v}
              rank={i + 1}
              isSelected={selected.has(v.vehicle_id)}
              onToggle={() => toggleSelect(v.vehicle_id)}
              onCallDealer={() => onStartCalling([v])}
              isFeatured
            />
          ))}
        </div>
      </section>

      {restVehicles.length > 0 && (
        <section className="rec-rest-section">
          <h3 className="rec-section-title">More Options</h3>
          <div className="rec-rest-grid">
            {restVehicles.map((v, i) => (
              <VehicleCard
                key={v.vehicle_id}
                vehicle={v}
                rank={TOP_COUNT + i + 1}
                isSelected={selected.has(v.vehicle_id)}
                onToggle={() => toggleSelect(v.vehicle_id)}
                onCallDealer={() => onStartCalling([v])}
                isFeatured={false}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function VehicleCard({
  vehicle,
  rank,
  isSelected,
  onToggle,
  onCallDealer,
  isFeatured,
}: {
  vehicle: VehicleResult;
  rank: number;
  isSelected: boolean;
  onToggle: () => void;
  onCallDealer: () => void;
  isFeatured: boolean;
}) {
  const [imgError, setImgError] = useState(false);
  const imgSrc = imgError
    ? PLACEHOLDER_IMG
    : vehicle.image_urls?.[0] || PLACEHOLDER_IMG;

  return (
    <div
      className={`rv-card ${isFeatured ? "rv-card--featured" : ""} ${isSelected ? "rv-card--selected" : ""}`}
    >
      <div className="rv-card-img-wrap">
        <img
          src={imgSrc}
          alt={vehicle.title}
          className="rv-card-img"
          onError={() => setImgError(true)}
          loading="lazy"
        />
        <span className="rv-card-rank">#{rank}</span>
        <button
          type="button"
          className={`rv-card-select ${isSelected ? "rv-card-select--on" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          title={isSelected ? "Deselect" : "Select for calling"}
        >
          {isSelected ? (
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
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
          )}
        </button>
        {vehicle.condition && (
          <span className="rv-card-condition">{vehicle.condition}</span>
        )}
      </div>
      <div className="rv-card-body">
        <h4 className="rv-card-title">{vehicle.title}</h4>
        <div className="rv-card-price">
          ${(vehicle.price || 0).toLocaleString()}
        </div>
        <div className="rv-card-meta">
          {vehicle.mileage != null && (
            <span>{vehicle.mileage.toLocaleString()} mi</span>
          )}
          {vehicle.dealer_name && <span>{vehicle.dealer_name}</span>}
          {vehicle.dealer_distance_miles != null && (
            <span>{vehicle.dealer_distance_miles.toFixed(1)} mi away</span>
          )}
        </div>
        {vehicle.features && vehicle.features.length > 0 && (
          <div className="rv-card-tags">
            {vehicle.features.slice(0, 3).map((f) => (
              <span key={f} className="rv-tag">
                {f}
              </span>
            ))}
          </div>
        )}
        <button
          type="button"
          className="rv-card-call-btn"
          onClick={(e) => {
            e.stopPropagation();
            onCallDealer();
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
          </svg>
          Call Dealer
        </button>
      </div>
    </div>
  );
}
