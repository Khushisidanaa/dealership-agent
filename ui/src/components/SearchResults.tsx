import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { VehicleResult } from "../types";
import { VehicleImageSlideshow } from "./VehicleImageSlideshow";
import "./SearchResults.css";

interface SearchResultsProps {
  sessionId: string;
  onStartCalling: (vehicles: VehicleResult[]) => void;
  onBack: () => void;
}

export function SearchResults({
  sessionId,
  onStartCalling,
  onBack,
}: SearchResultsProps) {
  const [vehicles, setVehicles] = useState<VehicleResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch results");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  if (loading) {
    return (
      <div className="search-loading">
        <div className="search-loading-spinner" />
        <h2>Searching for vehicles...</h2>
        <p>Scanning dealerships near you</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="search-loading">
        <p className="search-error">{error}</p>
        <button type="button" className="btn-primary" onClick={fetchResults}>
          Retry
        </button>
      </div>
    );
  }

  if (vehicles.length === 0) {
    return (
      <div className="search-loading">
        <h2>No vehicles found</h2>
        <p>Try adjusting your preferences</p>
        <button type="button" className="btn-secondary" onClick={onBack}>
          Back to Chat
        </button>
      </div>
    );
  }

  return (
    <div className="search-results">
      <div className="search-results-header">
        <div>
          <h2>Found {vehicles.length} vehicles</h2>
          <p>We will call the top dealers to get you the best deal</p>
        </div>
        <div className="search-results-actions">
          <button type="button" className="btn-secondary" onClick={onBack}>
            Back
          </button>
          <button
            type="button"
            className="btn-primary btn-call"
            onClick={() => onStartCalling(vehicles)}
          >
            Call Top Dealers
          </button>
        </div>
      </div>

      <div className="vehicle-grid">
        {vehicles.map((v) => (
          <VehicleCard key={v.vehicle_id} vehicle={v} />
        ))}
      </div>
    </div>
  );
}

function VehicleCard({ vehicle }: { vehicle: VehicleResult }) {
  return (
    <div className="vehicle-card">
      <div className="vehicle-card-img-wrap">
        <VehicleImageSlideshow
          imageUrls={vehicle.image_urls ?? []}
          alt={vehicle.title}
          imgClassName="vehicle-card-img"
        />
        {vehicle.condition && (
          <span className="vehicle-card-badge">{vehicle.condition}</span>
        )}
      </div>
      <div className="vehicle-card-body">
        <h3 className="vehicle-card-title">{vehicle.title}</h3>
        <div className="vehicle-card-price">
          ${(vehicle.price || 0).toLocaleString()}
        </div>
        <div className="vehicle-card-meta">
          {vehicle.mileage != null && (
            <span>{vehicle.mileage.toLocaleString()} mi</span>
          )}
          {vehicle.dealer_name && <span>{vehicle.dealer_name}</span>}
        </div>
        {vehicle.features?.length > 0 && (
          <div className="vehicle-card-features">
            {vehicle.features.slice(0, 4).map((f) => (
              <span key={f} className="vehicle-card-feature-tag">
                {f}
              </span>
            ))}
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
