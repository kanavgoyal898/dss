# DSS Server (Coordinator)

## Purpose

The DSS Coordinator is the control plane. It tracks peers, file metadata, and shard placement. It does **not** store actual file data — only the metadata needed to locate and reconstruct files.

## Starting the Coordinator

```bash
# Via Electron app (recommended — no terminal needed)
Open the DSS app → choose "Start Coordinator"

# Manual
cd dss
python -m dss.server.app.main
```

The coordinator starts on port 8000 by default (auto-assigned if occupied when launched via Electron).

## Key Modules

```
server/app/
├── main.py                  # FastAPI factory + lifespan manager
├── core/
│   ├── config.py            # Settings (env vars / defaults)
│   ├── auth.py              # JWT issue and validation
│   └── dependencies.py      # FastAPI dependency providers
├── api/routes/
│   ├── peers.py             # /peers — registration, heartbeat, listing
│   ├── files.py             # /files — upload session, metadata, download info
│   └── admin.py             # /admin — health, network policy, shard stats
└── services/
    ├── peer_registry.py     # In-memory peer store with liveness tracking
    ├── metadata_store.py    # File metadata + shard assignment records
    ├── shard_mapper.py      # Capacity-aware placement selection
    ├── health_monitor.py    # Background peer eviction loop
    └── network_policy.py    # global / lan / allowlist enforcement
```

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/peers/register | Register a peer node, receive JWT |
| POST | /api/v1/peers/heartbeat | Update peer liveness |
| GET  | /api/v1/peers | List all registered peers |
| POST | /api/v1/files/init | Open upload session |
| POST | /api/v1/files/complete | Finalise upload |
| GET  | /api/v1/files | List all file metadata |
| GET  | /api/v1/files/{id}/download | Get shard locations for download |
| GET  | /api/v1/admin/health | System health summary |
| GET  | /api/v1/admin/network | Current network policy |
| POST | /api/v1/admin/network/mode | Change network mode |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DSS_SERVER_HOST` | `0.0.0.0` | Bind address |
| `DSS_SERVER_PORT` | `8000` | Port (auto-assigned by Electron) |
| `DSS_JWT_SECRET` | *(random)* | JWT signing secret (set by Electron) |
| `DSS_NETWORK_MODE` | `global` | `global` / `lan` / `allowlist` |
| `DSS_HEARTBEAT_TIMEOUT` | `30` | Seconds before marking peer offline |

## Troubleshooting

**Port 8000 already in use** — The Electron app auto-assigns a free port. If running manually, set `DSS_SERVER_PORT=8001`.

**Peers show as offline** — They may have stopped sending heartbeats. Restart the peer node.
