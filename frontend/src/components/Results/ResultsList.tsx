import type { Vehicle, PriceStats } from "../../types";
import VehicleCard from "./VehicleCard";

interface ResultsListProps {
  vehicles: Vehicle[];
  priceStats: PriceStats | null;
  selectedIds: string[];
  onToggleSelect: (vehicleId: string) => void;
  onShortlist: () => void;
  isLoading: boolean;
}

const ResultsList = ({
  vehicles,
  priceStats,
  selectedIds,
  onToggleSelect,
  onShortlist,
  isLoading,
}: ResultsListProps) => {
  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <h2 style={{ margin: 0 }}>Search Results ({vehicles.length} found)</h2>
        <button
          onClick={onShortlist}
          disabled={selectedIds.length === 0 || isLoading}
          style={{
            padding: "10px 24px",
            backgroundColor: selectedIds.length > 0 ? "#1a1a2e" : "#d1d5db",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            cursor: selectedIds.length > 0 ? "pointer" : "not-allowed",
          }}
        >
          Shortlist {selectedIds.length} vehicles
        </button>
      </div>

      {priceStats && (
        <div
          style={{
            display: "flex",
            gap: 24,
            marginBottom: 20,
            fontSize: "0.875rem",
            color: "#4b5563",
          }}
        >
          <span>Avg: ${priceStats.avg_market_price.toLocaleString()}</span>
          <span>Low: ${priceStats.lowest_price.toLocaleString()}</span>
          <span>High: ${priceStats.highest_price.toLocaleString()}</span>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {vehicles.map((v) => (
          <VehicleCard
            key={v.vehicle_id}
            vehicle={v}
            isSelected={selectedIds.includes(v.vehicle_id)}
            onToggleSelect={onToggleSelect}
          />
        ))}
      </div>
    </div>
  );
};

export default ResultsList;
