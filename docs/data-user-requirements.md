# User requirements / preferences – data design

This document describes the data we store for a user’s car-buying requirements (price, location, brand, type, finance, etc.) and where it lives in MongoDB.

---

## Where it’s stored

- **Session document**: `session.preferences` is a dict that conforms to **`UserRequirements`** (see `backend/app/models/schemas.py`). One session = one set of requirements; the chat agent can extend them via `session.additional_filters`.
- **Optional later**: a dedicated `user_requirements` collection keyed by `session_id` if we need versioning or a separate requirements lifecycle.

---

## Fields we store

| Category | Field | Type | Notes |
|----------|--------|------|--------|
| **Price & budget** | `price_min` / `price_max` | float | USD |
| | `monthly_budget` | float? | Max monthly payment (if financing) |
| | `down_payment` | float? | Planned down payment |
| **Location** | `zip_code` | str | For dealer distance |
| | `max_distance_miles` | int | Max distance to dealership (1–500) |
| **Brand & model** | `brand_preference` | list[str] | e.g. Toyota, Honda |
| | `model_preference` | list[str] | e.g. Camry, Accord |
| | `excluded_brands` / `excluded_models` | list[str] | “Don’t show these” |
| **Vehicle type** | `car_type` | list[CarType] | SUV, sedan, truck, van, wagon, etc. |
| | `power_type` | list[PowerType] | Gas, hybrid, electric, EREV, etc. |
| **Year & condition** | `year_min` / `year_max` | int | Model year range |
| | `condition` | str | new \| used \| certified \| any |
| | `max_mileage` | int? | Max odometer (used cars) |
| **Drivetrain & features** | `transmission` | str | auto \| manual \| any |
| | `features` | list[str] | Sunroof, AWD, leather, etc. |
| | `color_preference` | list[str] | Preferred colors |
| **Finance** | `finance` | FinanceOption | cash \| finance \| lease \| undecided |
| | `credit_score` | int? | 300–850 if known |
| **Use case** | `requirements` | list[RequirementTag] | sporty, outdoor, family, student, commute, etc. |
| **Trade-in** | `trade_in` | str? | Description or “none” |
| **Other** | `other_notes` | str | Free-form notes |

---

## Enums

- **CarType**: SUV, SEDAN, HATCHBACK, COUPE, TRUCK, VAN, WAGON, CONVERTIBLE, OTHER  
- **PowerType**: GASOLINE, DIESEL, HYBRID, PLUGIN_HYBRID, ELECTRIC, EREV, FLEX, OTHER  
- **FinanceOption**: CASH, FINANCE, LEASE, UNDECIDED  
- **RequirementTag**: SPORTY, OUTDOOR, FAMILY, STUDENT, COMMUTE, LUXURY, OFFROAD, TOWING, ECONOMY, OTHER  

(Exact values are in `app.models.schemas`; stored in Mongo as strings via `use_enum_values=True`.)

---

## Other things we might add later

- **Seating / doors**: `min_seats`, `num_doors` (e.g. “need 7 seats”, “4 doors only”).
- **Timeline**: `need_by_date` or `timeline` (asap / flexible / by date) for prioritization.
- **Contact**: phone/email for follow-up (could stay in a separate “user” or “lead” object).
- **Down payment %**: in addition to absolute `down_payment`, a target LTV or “max down %”.
- **Loan term**: preferred term in months (e.g. 36, 48, 60) when financing.
- **Insurance / registration**: whether they want ballpark insurance or registration notes (often out of scope for negotiation agent).
- **Language / accessibility**: for UI or comms (optional).

For the first version, the table above plus `UserRequirements` in code is enough; we can extend the schema when we need these.

---

## Usage in code

- **API**: Accept a body that matches `UserRequirements` (or a subset) and save it to `session.preferences` as `body.model_dump()`.
- **Scraper / search**: Read `session.preferences` (and `session.additional_filters`), map into the search backend’s filters (price range, zip, radius, make/model, year, etc.).
- **Agent**: Use the same dict as context when generating replies and when deciding “ready to search” or “need more info”.
- **Negotiation**: Use price range, finance, trade-in, and `other_notes` when building negotiation prompts or dealer messages.
