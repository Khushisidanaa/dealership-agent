/**
 * Requirement field definitions matching backend UserRequirements schema.
 * Order and groups for display in the requirements modal.
 */

export type FieldType = "string" | "number" | "optionalNumber" | "array" | "optionalString";

export interface RequirementField {
  key: string;
  label: string;
  type: FieldType;
  placeholder?: string;
  /** For enum fields: single select (string) or multi-select (array). */
  options?: string[];
}

export interface RequirementGroup {
  title: string;
  fields: RequirementField[];
}

export const REQUIREMENTS_GROUPS: RequirementGroup[] = [
  {
    title: "Price & budget",
    fields: [
      { key: "price_min", label: "Min price (USD)", type: "number", placeholder: "0" },
      { key: "price_max", label: "Max price (USD)", type: "number", placeholder: "100000" },
      { key: "monthly_budget", label: "Max monthly (USD)", type: "optionalNumber", placeholder: "—" },
      { key: "down_payment", label: "Down payment (USD)", type: "optionalNumber", placeholder: "—" },
    ],
  },
  {
    title: "Location",
    fields: [
      { key: "zip_code", label: "ZIP code", type: "string", placeholder: "e.g. 90210" },
      { key: "max_distance_miles", label: "Max distance (mi)", type: "number", placeholder: "50" },
    ],
  },
  {
    title: "Brand & model",
    fields: [
      { key: "brand_preference", label: "Makes", type: "array", placeholder: "Toyota, Honda" },
      { key: "model_preference", label: "Models", type: "array", placeholder: "Camry, Accord" },
      { key: "excluded_brands", label: "Exclude makes", type: "array", placeholder: "—" },
      { key: "excluded_models", label: "Exclude models", type: "array", placeholder: "—" },
    ],
  },
  {
    title: "Vehicle type & power",
    fields: [
      {
        key: "car_type",
        label: "Body types",
        type: "array",
        options: ["suv", "sedan", "hatchback", "coupe", "truck", "van", "wagon", "convertible", "other"],
      },
      {
        key: "power_type",
        label: "Fuel / power",
        type: "array",
        options: ["gasoline", "diesel", "hybrid", "plugin_hybrid", "electric", "erev", "flex", "other"],
      },
    ],
  },
  {
    title: "Year, condition & mileage",
    fields: [
      { key: "year_min", label: "Year from", type: "number", placeholder: "2015" },
      { key: "year_max", label: "Year to", type: "number", placeholder: "2026" },
      {
        key: "condition",
        label: "Condition",
        type: "string",
        options: ["any", "new", "used", "certified"],
      },
      { key: "max_mileage", label: "Max mileage", type: "optionalNumber", placeholder: "—" },
    ],
  },
  {
    title: "Transmission & features",
    fields: [
      {
        key: "transmission",
        label: "Transmission",
        type: "string",
        options: ["any", "auto", "manual"],
      },
      { key: "features", label: "Must-have features", type: "array", placeholder: "AWD, sunroof, leather" },
      { key: "color_preference", label: "Colors", type: "array", placeholder: "—" },
    ],
  },
  {
    title: "Finance & use",
    fields: [
      {
        key: "finance",
        label: "Finance",
        type: "string",
        options: ["undecided", "cash", "finance", "lease"],
      },
      { key: "credit_score", label: "Credit score", type: "optionalNumber", placeholder: "—" },
      {
        key: "requirements",
        label: "Use case",
        type: "array",
        options: ["sporty", "outdoor", "family", "student", "commute", "luxury", "offroad", "towing", "economy", "other"],
      },
    ],
  },
  {
    title: "Other",
    fields: [
      { key: "trade_in", label: "Trade-in", type: "optionalString", placeholder: "—" },
      { key: "other_notes", label: "Notes", type: "string", placeholder: "Any other requirements" },
    ],
  },
];

const defaultValues: Record<string, unknown> = {
  price_min: 0,
  price_max: 100_000,
  monthly_budget: undefined,
  down_payment: undefined,
  zip_code: "",
  max_distance_miles: 50,
  brand_preference: [],
  model_preference: [],
  excluded_brands: [],
  excluded_models: [],
  car_type: [],
  power_type: [],
  year_min: 2015,
  year_max: 2026,
  condition: "any",
  max_mileage: undefined,
  transmission: "any",
  features: [],
  color_preference: [],
  finance: "undecided",
  credit_score: undefined,
  requirements: [],
  trade_in: undefined,
  other_notes: "",
};

export function getDefaultRequirements(): Record<string, unknown> {
  return { ...defaultValues };
}

/** Merge incoming (from chat) with defaults so we always have every key. */
export function mergeWithDefaults(incoming: Record<string, unknown>): Record<string, unknown> {
  const normalized = { ...incoming };
  if (normalized.radius_miles !== undefined && normalized.max_distance_miles === undefined) {
    normalized.max_distance_miles = normalized.radius_miles;
  }
  return { ...defaultValues, ...normalized };
}

export function countFilled(requirements: Record<string, unknown>): number {
  let n = 0;
  for (const [, value] of Object.entries(requirements)) {
    if (value === undefined || value === null) continue;
    if (typeof value === "string" && value.trim() === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    n++;
  }
  return n;
}
