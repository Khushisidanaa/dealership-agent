import { useState } from "react";
import type { TestDriveRequest } from "../../types";

interface TestDriveFormProps {
  vehicleId: string;
  onSubmit: (data: TestDriveRequest) => void;
  onCancel: () => void;
  isLoading: boolean;
}

const TestDriveForm = ({
  vehicleId,
  onSubmit,
  onCancel,
  isLoading,
}: TestDriveFormProps) => {
  const [form, setForm] = useState({
    preferred_date: "",
    preferred_time: "",
    user_name: "",
    user_phone: "",
    user_email: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      vehicle_id: vehicleId,
      ...form,
      confirm: true,
    });
  };

  const inputStyle: React.CSSProperties = {
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    fontSize: "0.95rem",
    width: "100%",
    boxSizing: "border-box",
  };

  return (
    <div
      style={{
        backgroundColor: "#fff",
        borderRadius: 12,
        padding: 24,
        boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
        maxWidth: 480,
        margin: "0 auto",
      }}
    >
      <h3 style={{ marginTop: 0 }}>Book a Test Drive</h3>
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: 14 }}
      >
        <input
          name="user_name"
          placeholder="Your name"
          value={form.user_name}
          onChange={handleChange}
          style={inputStyle}
          required
        />
        <input
          name="user_phone"
          placeholder="Phone number"
          value={form.user_phone}
          onChange={handleChange}
          style={inputStyle}
          required
        />
        <input
          name="user_email"
          placeholder="Email (optional)"
          value={form.user_email}
          onChange={handleChange}
          style={inputStyle}
        />
        <input
          name="preferred_date"
          type="date"
          value={form.preferred_date}
          onChange={handleChange}
          style={inputStyle}
          required
        />
        <input
          name="preferred_time"
          type="time"
          value={form.preferred_time}
          onChange={handleChange}
          style={inputStyle}
          required
        />

        <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
          <button
            type="submit"
            disabled={isLoading}
            style={{
              flex: 1,
              padding: "10px 0",
              backgroundColor: "#16a34a",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              cursor: isLoading ? "not-allowed" : "pointer",
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            {isLoading ? "Booking..." : "Confirm Booking"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: "10px 20px",
              backgroundColor: "#e5e7eb",
              color: "#374151",
              border: "none",
              borderRadius: 8,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};

export default TestDriveForm;
