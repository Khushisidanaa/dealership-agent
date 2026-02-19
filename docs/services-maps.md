# Google Maps API (Dealership Discovery)

We use **Google Geocoding** and **Places API (New)** to discover real car dealerships by zip code and radius. If `GOOGLE_MAPS_API_KEY` is not set, the app falls back to stub data so it still runs.

---

## What We Use

| API | Purpose |
|-----|--------|
| **Geocoding API** | Convert zip code → `(lat, lng)` so we can search “nearby”. |
| **Places API (New)** | `POST /v1/places:searchNearby` with `includedTypes: ["car_dealer"]` and a circle (center + radius in meters). Returns up to 20 places per request with name, address, phone, website, location, rating. |

Flow: **zip + radius** → geocode zip → call `searchNearby` with that center and radius (capped at 50 km) → parse results → upsert into `dealerships` collection.

---

## Where It Fits

- **`GET /api/dealerships?zip_code=...&radius_miles=...`** – discovers dealers (Maps or stub), upserts into DB, returns list.
- **`GET /api/users/{user_id}/search/cars`** – uses user requirements (e.g. zip), discovers dealers in area, then runs car search over those dealers.

**Code:**

- **`backend/app/services/dealership_service.py`** – `_geocode_zip()`, `_places_search_nearby()`, `discover_dealerships()` (uses APIs when key is set, else stub).
- **`backend/app/config.py`** – `google_maps_api_key` from `GOOGLE_MAPS_API_KEY`.

---

## Config

In `.env` or environment:

- **`GOOGLE_MAPS_API_KEY`** – API key with Geocoding and Places (New) enabled. Leave empty to use stub dealers.

---

## How to Set Up the Maps API

1. **Create a Google Cloud project** (or use an existing one): [Google Cloud Console](https://console.cloud.google.com/).
2. **Enable APIs**:
   - [Geocoding API](https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com)
   - [Places API (New)](https://console.cloud.google.com/apis/library/places-backend.googleapis.com)
3. **Create an API key**:
   - APIs & Services → Credentials → Create credentials → API key.
   - Restrict the key (recommended): under “API restrictions” choose “Restrict key” and select only **Geocoding API** and **Places API**.
4. **Set the key** in `backend/.env`:
   ```bash
   GOOGLE_MAPS_API_KEY=your-api-key-here
   ```
5. Restart the backend. Dealership discovery will use real Google results (up to 20 per request within the max radius of 50 km).

---

## Billing Notes

- Google Maps APIs are billable; they often include a free tier. Check [Maps pricing](https://developers.google.com/maps/billing-and-pricing).
- **Places (New)** field mask affects cost: we request only `places.id`, `places.displayName`, `places.formattedAddress`, `places.internationalPhoneNumber`, `places.nationalPhoneNumber`, `places.websiteUri`, `places.location`, `places.rating`, `places.types` to limit usage.

---

## Testing

With a valid key:

```bash
curl "http://127.0.0.1:5000/api/dealerships?zip_code=84101&radius_miles=25"
```

You should see real dealerships (name, address, phone, website) when the key is set, or stub entries when it is not.
