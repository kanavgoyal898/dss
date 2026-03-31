# DSS UI

## Purpose

The React/Next.js dashboard for DSS. Provides two views: **DSS Admin** (coordinator management) and **DSS Node** (peer node management with file upload/download).

## Running

```bash
cd ui
npm install
npm run dev       # opens http://localhost:3000
```

## Pages

| Route | Description |
|---|---|
| `/` | Mode selector — links to Admin and Node dashboards |
| `/admin` | DSS Admin Dashboard |
| `/node` | DSS Node Dashboard |

## Key Features

- **Connection badge** — shows coordinator / node online status at all times
- **Drag-and-drop upload** — drop any file; real-time SSE progress bar while uploading
- **Download progress** — progress bar streams from the download pipeline via SSE
- **Coordinator URL saved** — peer nodes remember the last coordinator address
- **Toast notifications** — success/error messages appear and auto-dismiss
- **Auto-refresh** — dashboards poll for updates every 8–10 seconds

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_COORDINATOR_URL` | `http://localhost:8000` | Set by Electron for Admin |
| `NEXT_PUBLIC_NODE_URL` | `http://localhost:8100` | Set by Electron for Peer |

## Troubleshooting

**Dashboard is blank or shows errors** — Make sure the backend (coordinator or node) is running. Check the URL environment variable matches the actual port.

**File upload freezes at 0%** — The SSE stream needs `Content-Type: text/event-stream` from the node API. Make sure `python-multipart` is installed.

**"Connect to coordinator first"** — In the Node Dashboard, enter the coordinator's address in the connection card and click Connect.
