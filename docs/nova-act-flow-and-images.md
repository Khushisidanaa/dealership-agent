# Nova Act Flow and Car Images

This doc explains how the Nova Act car search works and how images are (or aren’t) “pulled in,” so we can plan getting real car images.

---

## 1. High-level flow

```
User / Dashboard / Search API
         │
         ▼
  car_search.search_listings()
         │
         ├── CAR_SEARCH_PROVIDER = "nova_act" (default if configured)
         │         │
         │         ▼
         │   nova_act_service.search_listings_nova_act()
         │         │
         │         ├── [A] NOVA_ACT_WORKFLOW_NAME set?
         │         │         │
         │         │         YES → _run_workflow_and_get_results()
         │         │                   → CreateWorkflowRun → poll GetWorkflowRun
         │         │                   → read JSON from S3 (bucket/prefix/run_id)
         │         │                   → _parse_listings_to_results(data)
         │         │
         │         └── [B] No workflow
         │                   → _bedrock_listings_from_prompt()
         │                   → Bedrock Converse (DeepSeek) with prompt
         │                   → _parse_listings_to_results(LLM JSON)
         │
         └── Else provider = "marketcheck" → marketcheck_service (real listing API with photo_links)
```

- **Listings API**: `GET /api/listings/by-session/{session_id}` and `POST /api/listings/search` both call `search_listings()` and return `VehicleListingResult[]` with `image_urls` and `media.photo_links`.
- **Search API**: `POST /api/sessions/{session_id}/search/trigger` runs the same `search_listings()`, then `persist_search_results()` stores results in MongoDB; the frontend uses `image_urls` (e.g. `vehicle.image_urls?.[0]`) for cards.

So **all car listing flows** that use Nova Act go through `nova_act_service` and then `_parse_listings_to_results()`. Images are whatever that parser gets from the workflow (path A) or the LLM (path B).

---

## 2. Where images come from today (Nova Act)

### Path A: Workflow (Nova Act + S3)

- Backend calls `create_workflow_run(workflowDefinitionName, modelId)` then polls `get_workflow_run()` until status is `SUCCEEDED`.
- Result is read from S3: `list_objects_v2` under `{NOVA_ACT_RESULT_S3_PREFIX}/{run_id}`, then `get_object` on a `.json` file.
- Expected JSON shape: **either** a top-level array of listings **or** an object with a `"listings"` array. Each item is passed to `_parse_listings_to_results()`.

So **images in path A are whatever the workflow writes** into each listing object. If the workflow does not output `image_url` or `image_urls`, we get none from the workflow.

### Path B: Bedrock (no workflow)

- `_bedrock_listings_from_prompt()` sends a single Converse request to Bedrock (e.g. DeepSeek) with a prompt that asks for a JSON array of ~10 listings.
- **Image URLs:** The model has no access to real dealer or listing sites in this single-call setup. If the prompt asks for image URLs, the model **hallucinates** plausible-looking URLs (e.g. `cdn.dealerinspire.com`, `images.cars.com`, etc.). Those URLs do not exist or return 404 → `ERR_NAME_NOT_RESOLVED` or 404 in the browser. The prompt is therefore set to require **empty** `image_url` and `image_urls` so the UI shows placeholders instead of broken images.
- **To get real images:** Use (1) a **Nova Act workflow** that uses browser automation (Data Extraction) to navigate to real listing sites and extract image URLs from the page, or (2) the **MarketCheck** provider (`CAR_SEARCH_PROVIDER=marketcheck`), which returns real `photo_links` from their API.

### Parsing (both paths): `_parse_listings_to_results()`

- For each listing dict:
  - `image_url` (single) or `image_urls` (list) are read and normalized into a list `image_urls`.
  - If that list is empty, we use **one** placeholder: `_placeholder_image_url(title, year, make, model)` → data URI of an SVG (“Vehicle” text).
  - We set:
    - `media = MediaInfo(photo_links=image_urls, photo_links_cached=[])`
    - `image_urls=image_urls` on `VehicleListingResult`.

So today:

- **Workflow path**: Images only if the workflow output includes `image_url` / `image_urls`; otherwise placeholders.
- **Bedrock path**: Images are whatever the LLM returns (often fake URLs or empty) → otherwise placeholders.
- **photo_links_cached** is **never** set for Nova Act (always `[]`). There is no step that “pulls in” image bytes and caches them.

---

## 3. Data shape the backend expects (for images)

From `_parse_listings_to_results()` and `VehicleListingResult`:

- Each listing object may have:
  - `image_url` (string) → used as single main photo.
  - `image_urls` (list of strings) → used as full list; if present, `image_url` can still be used as fallback when parsing.
- Result:
  - `VehicleListingResult.media.photo_links` = same list.
  - `VehicleListingResult.media.photo_links_cached` = currently always `[]` for Nova Act.
  - `VehicleListingResult.image_urls` = same list (this is what the UI uses first, e.g. `vehicle.image_urls?.[0]`).

So “images already pulled in” can mean either:

1. **URLs present**: Ensure listing objects have real (or at least valid) `image_url` / `image_urls` so the UI shows real photos instead of placeholders.
2. **Bytes pulled in**: Actually fetch image bytes (e.g. from those URLs), store them (e.g. S3 or local), and expose cached URLs in `photo_links_cached` (and optionally use them in `image_urls`) so we’re not dependent on external URLs later.

---

## 4. Plan options to get car images

### Option 1: Workflow path – ensure workflow outputs image URLs

- **Goal**: Have real listing image URLs in the data.
- **Where**: In the Nova Act workflow (IDE/Playground), ensure the step that builds the final listings JSON includes `image_url` and/or `image_urls` from the real source (e.g. dealer/listing page or a car-data API the workflow calls).
- **Backend**: No code change required; `_parse_listings_to_results()` already supports `image_url` and `image_urls`. If the workflow starts sending them, they’ll show up in `image_urls` and the UI will use them.
- **Caveat**: Depends on what the workflow can access (e.g. browser scraping, external API). If the workflow doesn’t have real image URLs, this option can’t help by itself.

### Option 2: Bedrock path – improve prompt or add a second step

- **Goal**: Get more realistic or real image URLs when not using a workflow.
- **2a – Prompt**: Tighten the prompt to ask for “only real, working image URLs from public listing sites” and “empty string if no real URL.” Reduces fake URLs but won’t create real ones if the model has no live data.
- **2b – Tool/API**: Give the model a tool that calls a real listing/photo API (e.g. MarketCheck or another provider) and let it fill `image_url` from that. Requires adding a tool and possibly changing to a flow that uses tools (e.g. agent loop) instead of a single Converse call.

### Option 3: Backend image fetch + cache (both paths)

- **Goal**: “Pull in” images by downloading them and serving from our side.
- **Flow**: After `_parse_listings_to_results()` (or in a post-step):
  1. For each result that has `media.photo_links` (or `image_urls`), optionally validate URL (allowlist host, HTTPS).
  2. Download image bytes (with timeout, size limit, and error handling).
  3. Store in object storage (e.g. S3) or local cache and get a stable URL (e.g. presigned or internal `/api/.../image/...`).
  4. Set `media.photo_links_cached` (and optionally replace or prepend `image_urls`) with these cached URLs.
- **Benefits**: Works for both workflow and Bedrock paths; once cached, we’re not dependent on external URLs; we can enforce security (no arbitrary external image URLs in the UI).
- **Considerations**: Need to respect rate limits and legality (right to store/display dealer photos); consider async/background job so search latency doesn’t depend on downloads.

### Option 4: Hybrid (recommended direction)

1. **Short term**:  
   - **Workflow**: Document that the workflow must output `image_url` / `image_urls` and, if possible, update the workflow to pull real image URLs from the source it uses.  
   - **Bedrock-only**: Either accept placeholders or add a small “image URL” tool that calls MarketCheck (or similar) when available, so at least some listings get real URLs.

2. **Medium term**:  
   - Add an optional **image cache** step (Option 3): after getting results, for each listing with `photo_links`, optionally fetch and store images and set `photo_links_cached`. Frontend can prefer `photo_links_cached` when present (or backend can merge them into `image_urls`), so “images are already pulled in” to our system.

---

## 5. Summary

- **How Nova Act works**: Either (A) run a workflow and read listing JSON from S3, or (B) call Bedrock Converse once and parse listing JSON from the model. Both paths use `_parse_listings_to_results()` to build `VehicleListingResult` with `image_urls` and `media.photo_links`. If no URLs, we use an SVG placeholder.
- **Current state**: Workflow path gets images only if the workflow outputs them; Bedrock path often gets fake or empty URLs → placeholders. No backend step currently “pulls in” image bytes; `photo_links_cached` is always empty for Nova Act.
- **To get car images**: Ensure workflow outputs real `image_url`/`image_urls` (Option 1), improve Bedrock path with prompt or tools (Option 2), and/or add a backend fetch-and-cache step (Option 3). Option 4 combines workflow + optional cache for a clear path to having images “already pulled in” on our side.
