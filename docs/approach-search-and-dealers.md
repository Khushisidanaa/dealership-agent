# Approach: Finding Cars and Dealerships

## Chosen flow (current)

1. **Search cars**  
   - APIs: `GET /api/search/cars`, `GET /api/sessions/{session_id}/search/cars`, and `GET /api/users/{user_id}/search/cars`  
   - Return **empty list by default**. No scraper is wired; plug in a scraper in `scraper_service.search_cars` when needed.

2. **Dealership directory (optional)**  
   - API: `GET /api/dealerships?zip=...&radius_miles=...` uses Google Maps (Places) when `GOOGLE_MAPS_API_KEY` is set, or stub data.  
   - Used if you need a list of dealers (e.g. for “dealers we contacted” or future features).

---

## Is this a good approach?

- **Yes.** Having a canonical dealer list (with phone, website, address) is useful for contact and for “which dealer’s site to scrape.” Doing “find dealers first, then search their inventory” is a clear, two-step flow.

- **Caveat:** Many dealer sites use third-party inventory (vAuto, Dealer.com, etc.), so scraping **dealer websites** directly is often brittle. A common alternative is to use **listing aggregators** (Cars.com, AutoTrader, CarGurus): search by zip + filters and get cars with dealer info in one go. You can still **store** those dealers in our directory and link results to them.

---

## Other options that fit

1. **Aggregator-first**  
   - One (or few) aggregator APIs/scrapes by zip + user requirements → get cars + dealer name/phone/URL.  
   - Optionally enrich with Maps (address, etc.) and upsert into our **dealerships** table.  
   - Simpler scraping surface; data already structured.

2. **Hybrid (what we’re doing + aggregator)**  
   - Use Maps to build the **directory** (phone, website, address).  
   - For **matching cars**, prefer an aggregator search by zip/radius/filters; optionally try dealer-site scrape for dealers we care about.  
   - Store directory; attach search results to dealers by matching name/phone/address.

3. **Dealer-site only**  
   - As you described: discover dealers (Maps) → for each dealer, scrape their site.  
   - Works when dealers have a scrapeable inventory page; often needs per-dealer or per-platform logic.

---

## DB and APIs in this repo

- **DealershipDocument** (directory): `dealer_id`, name, address, phone, website, lat, lng, source (google_maps | apple_maps), rating, types, raw.  
- **DealershipContactDocument**: unchanged; per-user, per-dealer, status (text/call/responded), cars we’re negotiating about.

- **GET /api/dealerships?zip=...&radius_miles=...**  
  - Discovers dealers via Maps (stub until keys are set), upserts into **dealerships**, returns list.

- **GET /api/search/cars**  
  - Returns empty list (no scraper wired).

- **GET /api/sessions/{session_id}/search/cars**  
  - Uses session preferences; calls `search_cars`; returns `SearchResultsResponse` (empty list by default).

- **GET /api/users/{user_id}/search/cars**  
  - Same using saved user requirements; empty list by default.

---

## Implementation

- **scraper_service.search_cars**: Returns `[]`; plug in a scraper when needed.
- **dealership_service** / **GET /api/dealerships**: Available for dealer directory (Maps or stub).
