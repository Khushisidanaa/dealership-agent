import { useState } from "react";
import { api } from "../api/client";
import "./RequirementsForm.css";

interface RequirementsFormProps {
  sessionId: string;
  onSearchDone: () => void;
}

const POPULAR_MAKES = [
  "",
  "Toyota",
  "Honda",
  "Ford",
  "Chevrolet",
  "BMW",
  "Mercedes-Benz",
  "Audi",
  "Nissan",
  "Hyundai",
  "Kia",
  "Tesla",
  "Subaru",
  "Mazda",
  "Volkswagen",
  "Lexus",
  "Jeep",
  "Ram",
  "GMC",
  "Dodge",
  "Acura",
];

const BODY_TYPES = [
  "",
  "sedan",
  "suv",
  "truck",
  "coupe",
  "hatchback",
  "wagon",
  "convertible",
  "van",
];
const CONDITIONS = ["", "used", "new", "certified"];
const FUEL_TYPES = ["", "gasoline", "diesel", "hybrid", "electric"];

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = Array.from(
  { length: CURRENT_YEAR - 2000 + 2 },
  (_, i) => CURRENT_YEAR + 1 - i,
);

export function RequirementsForm({
  sessionId,
  onSearchDone,
}: RequirementsFormProps) {
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [yearMax, setYearMax] = useState("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [condition, setCondition] = useState("");
  const [zipCode, setZipCode] = useState("84070");
  const [radius, setRadius] = useState("50");
  const [maxMileage, setMaxMileage] = useState("");
  const [bodyType, setBodyType] = useState("");
  const [fuelType, setFuelType] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!zipCode.trim()) {
      setError("ZIP code is required to search nearby dealers.");
      return;
    }

    setLoading(true);
    try {
      const prefs: Record<string, unknown> = {
        make: make || "",
        model: model || "",
        zip_code: zipCode.trim(),
        radius_miles: parseInt(radius, 10) || 50,
        condition: condition || "used",
      };

      if (yearMin) prefs.year_min = parseInt(yearMin, 10);
      if (yearMax) prefs.year_max = parseInt(yearMax, 10);
      if (priceMin) prefs.price_min = parseInt(priceMin, 10);
      if (priceMax) prefs.price_max = parseInt(priceMax, 10);
      if (maxMileage) prefs.max_mileage = parseInt(maxMileage, 10);
      if (bodyType) prefs.body_type = bodyType;
      if (fuelType) prefs.fuel_type = fuelType;

      await api.preferences.submit(sessionId, prefs);
      onSearchDone();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save preferences.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="req-form-wrap">
      <form className="req-form" onSubmit={handleSubmit}>
        <div className="req-form-header">
          <h2>Quick Search</h2>
          <p>
            Fill in what you know -- leave the rest blank for broader results.
          </p>
        </div>

        <div className="req-form-grid">
          <div className="req-field">
            <label htmlFor="rf-make">Make</label>
            <select
              id="rf-make"
              value={make}
              onChange={(e) => setMake(e.target.value)}
            >
              {POPULAR_MAKES.map((m) => (
                <option key={m} value={m}>
                  {m || "Any"}
                </option>
              ))}
            </select>
          </div>

          <div className="req-field">
            <label htmlFor="rf-model">Model</label>
            <input
              id="rf-model"
              type="text"
              placeholder="e.g. Camry, Civic"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-body">Body Type</label>
            <select
              id="rf-body"
              value={bodyType}
              onChange={(e) => setBodyType(e.target.value)}
            >
              {BODY_TYPES.map((b) => (
                <option key={b} value={b}>
                  {b ? b.charAt(0).toUpperCase() + b.slice(1) : "Any"}
                </option>
              ))}
            </select>
          </div>

          <div className="req-field">
            <label htmlFor="rf-condition">Condition</label>
            <select
              id="rf-condition"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
            >
              {CONDITIONS.map((c) => (
                <option key={c} value={c}>
                  {c ? c.charAt(0).toUpperCase() + c.slice(1) : "Any"}
                </option>
              ))}
            </select>
          </div>

          <div className="req-field">
            <label htmlFor="rf-year-min">Year (from)</label>
            <select
              id="rf-year-min"
              value={yearMin}
              onChange={(e) => setYearMin(e.target.value)}
            >
              <option value="">Any</option>
              {YEAR_OPTIONS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          <div className="req-field">
            <label htmlFor="rf-year-max">Year (to)</label>
            <select
              id="rf-year-max"
              value={yearMax}
              onChange={(e) => setYearMax(e.target.value)}
            >
              <option value="">Any</option>
              {YEAR_OPTIONS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          <div className="req-field">
            <label htmlFor="rf-price-min">Min Price ($)</label>
            <input
              id="rf-price-min"
              type="number"
              placeholder="0"
              value={priceMin}
              onChange={(e) => setPriceMin(e.target.value)}
              min="0"
              step="1000"
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-price-max">Max Price ($)</label>
            <input
              id="rf-price-max"
              type="number"
              placeholder="100000"
              value={priceMax}
              onChange={(e) => setPriceMax(e.target.value)}
              min="0"
              step="1000"
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-mileage">Max Mileage</label>
            <input
              id="rf-mileage"
              type="number"
              placeholder="e.g. 50000"
              value={maxMileage}
              onChange={(e) => setMaxMileage(e.target.value)}
              min="0"
              step="5000"
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-fuel">Fuel Type</label>
            <select
              id="rf-fuel"
              value={fuelType}
              onChange={(e) => setFuelType(e.target.value)}
            >
              {FUEL_TYPES.map((f) => (
                <option key={f} value={f}>
                  {f ? f.charAt(0).toUpperCase() + f.slice(1) : "Any"}
                </option>
              ))}
            </select>
          </div>

          <div className="req-field req-field--wide">
            <label htmlFor="rf-zip">
              ZIP Code <span className="req-required">*</span>
            </label>
            <input
              id="rf-zip"
              type="text"
              placeholder="e.g. 90210"
              value={zipCode}
              onChange={(e) => setZipCode(e.target.value)}
              maxLength={5}
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-radius">Search Radius: {radius} mi</label>
            <input
              id="rf-radius"
              type="range"
              min="10"
              max="200"
              step="10"
              value={radius}
              onChange={(e) => setRadius(e.target.value)}
              className="req-slider"
            />
            <div className="req-slider-labels">
              <span>10 mi</span>
              <span>200 mi</span>
            </div>
          </div>
        </div>

        {error && <p className="req-form-error">{error}</p>}

        <button type="submit" className="req-form-submit" disabled={loading}>
          {loading ? (
            <>
              <span className="req-form-spinner" />
              Searching...
            </>
          ) : (
            <>
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              Search Vehicles
            </>
          )}
        </button>
      </form>
    </div>
  );
}
