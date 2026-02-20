import { useState, useMemo, useCallback } from "react";
import { api } from "../api/client";
import { mergeWithDefaults } from "./requirementsFields";
import "./RequirementsForm.css";

interface RequirementsFormProps {
  sessionId: string;
  requirements: Record<string, unknown>;
  onRequirementsChange: (next: Record<string, unknown>) => void;
  onSearchDone: () => void;
}

/** Map app requirements (backend/chat shape) to Quick Form field values. */
function requirementsToFormValues(req: Record<string, unknown>) {
  const r = mergeWithDefaults(req);
  const arr = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : []);
  const first = (v: string[]) => (v.length ? v[0] : "");
  const num = (v: unknown): string =>
    v !== undefined && v !== null && v !== "" ? String(v) : "";
  return {
    make: first(arr(r.brand_preference)),
    model: first(arr(r.model_preference)),
    bodyType: first(arr(r.car_type)),
    condition: typeof r.condition === "string" ? r.condition : "any",
    yearMin: num(r.year_min),
    yearMax: num(r.year_max),
    priceMin: num(r.price_min),
    priceMax: num(r.price_max),
    maxMileage: num(r.max_mileage),
    fuelType: first(arr(r.power_type)),
    zipCode: typeof r.zip_code === "string" && r.zip_code ? r.zip_code : "84070",
    radius: String(
      r.max_distance_miles ?? r.radius_miles ?? 50,
    ),
  };
}

/** Apply a single form field change to requirements and return the new object. */
function formChangeToRequirements(
  req: Record<string, unknown>,
  field: keyof ReturnType<typeof requirementsToFormValues>,
  value: string | number,
): Record<string, unknown> {
  const next = { ...mergeWithDefaults(req) };
  const str = value === "" ? "" : String(value).trim();
  const num = (v: string) => (v === "" ? undefined : parseInt(v, 10));
  switch (field) {
    case "make":
      next.brand_preference = str ? [str] : [];
      break;
    case "model":
      next.model_preference = str ? [str] : [];
      break;
    case "bodyType":
      next.car_type = str ? [str] : [];
      break;
    case "condition":
      next.condition = str || "any";
      break;
    case "yearMin": {
      const s = String(value).trim();
      next.year_min = s === "" ? 2015 : parseInt(s, 10);
      break;
    }
    case "yearMax": {
      const s = String(value).trim();
      next.year_max = s === "" ? 2026 : parseInt(s, 10);
      break;
    }
    case "priceMin":
      next.price_min = value === "" ? 0 : Number(value);
      break;
    case "priceMax":
      next.price_max = value === "" ? 100_000 : Number(value);
      break;
    case "maxMileage":
      next.max_mileage = value === "" ? undefined : Number(value);
      break;
    case "fuelType":
      next.power_type = str ? [str] : [];
      break;
    case "zipCode":
      next.zip_code = str || "";
      break;
    case "radius":
      next.max_distance_miles = value === "" ? 50 : Number(value);
      next.radius_miles = value === "" ? 50 : Number(value);
      break;
    default:
      break;
  }
  return next;
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
  requirements,
  onRequirementsChange,
  onSearchDone,
}: RequirementsFormProps) {
  const formValues = useMemo(
    () => requirementsToFormValues(requirements),
    [requirements],
  );

  const updateField = useCallback(
    (field: keyof typeof formValues, value: string) => {
      const next = formChangeToRequirements(requirements, field, value);
      onRequirementsChange(next);
    },
    [requirements, onRequirementsChange],
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formValues.zipCode.trim()) {
      setError("ZIP code is required to search nearby dealers.");
      return;
    }

    setLoading(true);
    try {
      const prefs: Record<string, unknown> = {
        make: formValues.make || "",
        model: formValues.model || "",
        zip_code: formValues.zipCode.trim(),
        radius_miles: parseInt(formValues.radius, 10) || 50,
        condition: formValues.condition || "used",
      };

      if (formValues.yearMin) prefs.year_min = parseInt(formValues.yearMin, 10);
      if (formValues.yearMax) prefs.year_max = parseInt(formValues.yearMax, 10);
      if (formValues.priceMin) prefs.price_min = parseInt(formValues.priceMin, 10);
      if (formValues.priceMax) prefs.price_max = parseInt(formValues.priceMax, 10);
      if (formValues.maxMileage) prefs.max_mileage = parseInt(formValues.maxMileage, 10);
      if (formValues.bodyType) prefs.body_type = formValues.bodyType;
      if (formValues.fuelType) prefs.fuel_type = formValues.fuelType;

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
              value={formValues.make}
              onChange={(e) => updateField("make", e.target.value)}
            >
              {[
                ...(formValues.make && !POPULAR_MAKES.includes(formValues.make)
                  ? [formValues.make]
                  : []),
                ...POPULAR_MAKES,
              ].map((m) => (
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
              value={formValues.model}
              onChange={(e) => updateField("model", e.target.value)}
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-body">Body Type</label>
            <select
              id="rf-body"
              value={formValues.bodyType}
              onChange={(e) => updateField("bodyType", e.target.value)}
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
              value={formValues.condition}
              onChange={(e) => updateField("condition", e.target.value)}
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
              value={formValues.yearMin}
              onChange={(e) => updateField("yearMin", e.target.value)}
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
              value={formValues.yearMax}
              onChange={(e) => updateField("yearMax", e.target.value)}
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
              value={formValues.priceMin}
              onChange={(e) => updateField("priceMin", e.target.value)}
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
              value={formValues.priceMax}
              onChange={(e) => updateField("priceMax", e.target.value)}
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
              value={formValues.maxMileage}
              onChange={(e) => updateField("maxMileage", e.target.value)}
              min="0"
              step="5000"
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-fuel">Fuel Type</label>
            <select
              id="rf-fuel"
              value={formValues.fuelType}
              onChange={(e) => updateField("fuelType", e.target.value)}
            >
              {[
                ...(formValues.fuelType && !FUEL_TYPES.includes(formValues.fuelType)
                  ? [formValues.fuelType]
                  : []),
                ...FUEL_TYPES,
              ].map((f) => (
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
              value={formValues.zipCode}
              onChange={(e) => updateField("zipCode", e.target.value)}
              maxLength={5}
            />
          </div>

          <div className="req-field">
            <label htmlFor="rf-radius">Search Radius: {formValues.radius} mi</label>
            <input
              id="rf-radius"
              type="range"
              min="10"
              max="200"
              step="10"
              value={formValues.radius}
              onChange={(e) => updateField("radius", e.target.value)}
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
