import { useState } from "react";
import type { Preferences } from "../../types";

interface QuestionnaireProps {
  onSubmit: (preferences: Preferences) => void;
  isLoading: boolean;
}

const DEFAULT_PREFERENCES: Preferences = {
  make: "",
  model: "",
  year_min: 2018,
  year_max: 2026,
  price_min: 0,
  price_max: 50000,
  condition: "any",
  zip_code: "",
  radius_miles: 50,
  max_mileage: null,
};

const Questionnaire = ({ onSubmit, isLoading }: QuestionnaireProps) => {
  const [form, setForm] = useState<Preferences>(DEFAULT_PREFERENCES);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "number" ? (value === "" ? null : Number(value)) : value,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(form);
  };

  const fieldStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  };

  const inputStyle: React.CSSProperties = {
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid #ccc",
    fontSize: "1rem",
  };

  return (
    <div
      style={{
        backgroundColor: "#fff",
        borderRadius: 12,
        padding: 32,
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      <h2 style={{ marginTop: 0 }}>What are you looking for?</h2>
      <form
        onSubmit={handleSubmit}
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}
      >
        <div style={fieldStyle}>
          <label>Make</label>
          <input
            name="make"
            value={form.make}
            onChange={handleChange}
            placeholder="e.g. Toyota"
            style={inputStyle}
            required
          />
        </div>

        <div style={fieldStyle}>
          <label>Model</label>
          <input
            name="model"
            value={form.model}
            onChange={handleChange}
            placeholder="e.g. Camry"
            style={inputStyle}
            required
          />
        </div>

        <div style={fieldStyle}>
          <label>Year (Min)</label>
          <input
            name="year_min"
            type="number"
            value={form.year_min}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={fieldStyle}>
          <label>Year (Max)</label>
          <input
            name="year_max"
            type="number"
            value={form.year_max}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={fieldStyle}>
          <label>Price Min ($)</label>
          <input
            name="price_min"
            type="number"
            value={form.price_min}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={fieldStyle}>
          <label>Price Max ($)</label>
          <input
            name="price_max"
            type="number"
            value={form.price_max}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={fieldStyle}>
          <label>Condition</label>
          <select
            name="condition"
            value={form.condition}
            onChange={handleChange}
            style={inputStyle}
          >
            <option value="any">Any</option>
            <option value="new">New</option>
            <option value="used">Used</option>
          </select>
        </div>

        <div style={fieldStyle}>
          <label>Zip Code</label>
          <input
            name="zip_code"
            value={form.zip_code}
            onChange={handleChange}
            placeholder="e.g. 90210"
            style={inputStyle}
            required
          />
        </div>

        <div style={fieldStyle}>
          <label>Search Radius (miles)</label>
          <input
            name="radius_miles"
            type="number"
            value={form.radius_miles}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={fieldStyle}>
          <label>Max Mileage</label>
          <input
            name="max_mileage"
            type="number"
            value={form.max_mileage ?? ""}
            onChange={handleChange}
            placeholder="Leave blank for any"
            style={inputStyle}
          />
        </div>

        <div style={{ gridColumn: "1 / -1", textAlign: "right" }}>
          <button
            type="submit"
            disabled={isLoading}
            style={{
              padding: "12px 32px",
              backgroundColor: "#1a1a2e",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              fontSize: "1rem",
              cursor: isLoading ? "not-allowed" : "pointer",
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            {isLoading ? "Saving..." : "Next: Refine with AI"}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Questionnaire;
