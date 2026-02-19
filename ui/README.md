# Dealership Agent UI

React frontend for the Dealership Agent: chat-driven requirements, then a dashboard of dealerships and cars with test-drive booking.

## Stack

- **React 18** + **TypeScript**
- **Vite** for build and dev server
- No UI framework (plain CSS with CSS variables)

## Development

```bash
cd ui
npm install
npm run dev
```

Runs at `http://localhost:5173`. The Vite config proxies `/api` to `http://localhost:8000`, so run the backend on port 8000.

## Build

```bash
npm run build
```

Output is in `dist/` (static files). Preview locally:

```bash
npm run preview
```

## Deploying on Linode

1. **Build the app**
   ```bash
   cd ui && npm ci && npm run build
   ```

2. **Serve the `dist` folder**
   - **Option A – Same server as API (recommended):** Use FastAPI to serve the built files so one domain serves both API and UI.
     - In your FastAPI app (e.g. in `main.py`), mount the static files:
       ```python
       from fastapi.staticfiles import StaticFiles
       app.mount("/", StaticFiles(directory="ui/dist", html=True), name="static")
       ```
     - Build the UI, then run the backend; the root URL serves the SPA and `/api/*` hits the API.
   - **Option B – Nginx:** Point a server block at `ui/dist` and set `try_files $uri $uri/ /index.html` for the SPA. Configure a reverse proxy for `/api` to your FastAPI backend.
   - **Option C – Object Storage + CDN:** Upload `dist` to Linode Object Storage and use the CDN URL as the frontend origin; keep the API on a separate subdomain or path.

3. **API base URL**
   - Dev uses the Vite proxy, so no config needed.
   - For production, if the UI is on the same origin as the API, keep `API_BASE = ""` in `src/api/client.ts`. If the API is on another origin, set `API_BASE` to the full API URL (e.g. `https://api.yourdomain.com`) or use a relative path like `/api` and ensure the server proxies `/api` to the backend.

## Features

- **Chat:** Conversational AI to gather requirements; responses can update the requirements panel.
- **Requirements (top-right):** Collapsible modal showing gathered requirements; click values to edit. “Mark requirements complete” saves to the backend and enables the dashboard flow.
- **Dashboard:** Table of dealerships (name, address, distance); expand a row to see cars (price, mileage, condition). Click a car for full details; “Schedule test drive” opens a form (date, time, name, phone). Bookings and contact status (e.g. text/call) are shown on the dashboard.
