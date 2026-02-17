import type { Vehicle, CommunicationStatus } from "../../types";

interface DashboardViewProps {
  shortlist: Vehicle[];
  communicationStatus: CommunicationStatus[];
  onSendText: (vehicleId: string) => void;
  onStartCall: (vehicleId: string) => void;
  onBookTestDrive: (vehicleId: string) => void;
}

const DashboardView = ({
  shortlist,
  communicationStatus,
  onSendText,
  onStartCall,
  onBookTestDrive,
}: DashboardViewProps) => {
  const getCommStatus = (vehicleId: string) =>
    communicationStatus.find((c) => c.vehicle_id === vehicleId);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Your Top Picks</h2>
      <p style={{ color: "#6b7280", marginBottom: 24 }}>
        Review your shortlisted vehicles. Text, call, or book a test drive.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 20,
        }}
      >
        {shortlist.map((vehicle) => {
          const comm = getCommStatus(vehicle.vehicle_id);
          return (
            <div
              key={vehicle.vehicle_id}
              style={{
                backgroundColor: "#fff",
                borderRadius: 12,
                padding: 20,
                boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
              }}
            >
              <h3 style={{ margin: "0 0 4px 0", fontSize: "1.1rem" }}>
                {vehicle.title}
              </h3>
              <p style={{ margin: "0 0 8px 0", color: "#6b7280" }}>
                {vehicle.dealer_name}
              </p>
              <p
                style={{
                  margin: "0 0 16px 0",
                  fontSize: "1.25rem",
                  fontWeight: 700,
                }}
              >
                ${vehicle.price.toLocaleString()}
              </p>

              <div
                style={{
                  fontSize: "0.8rem",
                  color: "#6b7280",
                  marginBottom: 12,
                }}
              >
                Score: {vehicle.overall_score} | Mileage:{" "}
                {vehicle.mileage?.toLocaleString() ?? "N/A"}
              </div>

              {comm && (
                <div
                  style={{
                    fontSize: "0.8rem",
                    marginBottom: 12,
                    padding: 8,
                    backgroundColor: "#f9fafb",
                    borderRadius: 6,
                  }}
                >
                  {comm.text_sent && <div>SMS sent</div>}
                  {comm.call_made && <div>Call completed</div>}
                  {comm.response && <div>Response: {comm.response}</div>}
                </div>
              )}

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => onSendText(vehicle.vehicle_id)}
                  style={actionBtnStyle("#2563eb")}
                >
                  Text Dealer
                </button>
                <button
                  onClick={() => onStartCall(vehicle.vehicle_id)}
                  style={actionBtnStyle("#7c3aed")}
                >
                  Call Dealer
                </button>
                <button
                  onClick={() => onBookTestDrive(vehicle.vehicle_id)}
                  style={actionBtnStyle("#16a34a")}
                >
                  Book Test Drive
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const actionBtnStyle = (bg: string): React.CSSProperties => ({
  padding: "6px 14px",
  backgroundColor: bg,
  color: "#fff",
  border: "none",
  borderRadius: 6,
  fontSize: "0.8rem",
  cursor: "pointer",
});

export default DashboardView;
