import type { Vehicle } from "../../types";

interface VehicleCardProps {
  vehicle: Vehicle;
  isSelected: boolean;
  onToggleSelect: (vehicleId: string) => void;
}

const VehicleCard = ({
  vehicle,
  isSelected,
  onToggleSelect,
}: VehicleCardProps) => {
  return (
    <div
      style={{
        backgroundColor: "#fff",
        borderRadius: 12,
        padding: 20,
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        border: isSelected ? "2px solid #1a1a2e" : "2px solid transparent",
        cursor: "pointer",
        transition: "border-color 0.2s",
      }}
      onClick={() => onToggleSelect(vehicle.vehicle_id)}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <h3 style={{ margin: "0 0 4px 0" }}>{vehicle.title}</h3>
          <p style={{ margin: 0, color: "#6b7280", fontSize: "0.875rem" }}>
            {vehicle.dealer_name} - {vehicle.dealer_distance_miles} mi away
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
            ${vehicle.price.toLocaleString()}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>
            {vehicle.mileage ? `${vehicle.mileage.toLocaleString()} mi` : "N/A"}
          </div>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          gap: 12,
          marginTop: 12,
          fontSize: "0.8rem",
        }}
      >
        <span
          style={{
            backgroundColor: "#f0fdf4",
            color: "#16a34a",
            padding: "2px 8px",
            borderRadius: 4,
          }}
        >
          Score: {vehicle.overall_score}
        </span>
        <span
          style={{
            backgroundColor: "#eff6ff",
            color: "#2563eb",
            padding: "2px 8px",
            borderRadius: 4,
          }}
        >
          Price: {vehicle.price_score}
        </span>
        <span
          style={{
            backgroundColor: "#fefce8",
            color: "#ca8a04",
            padding: "2px 8px",
            borderRadius: 4,
          }}
        >
          Condition: {vehicle.condition_score}
        </span>
      </div>

      {vehicle.features.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 6,
            flexWrap: "wrap",
            marginTop: 10,
          }}
        >
          {vehicle.features.map((f) => (
            <span
              key={f}
              style={{
                fontSize: "0.75rem",
                backgroundColor: "#f3f4f6",
                padding: "2px 8px",
                borderRadius: 4,
              }}
            >
              {f.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default VehicleCard;
