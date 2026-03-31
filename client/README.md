# DSS Client (Peer Node)

## Purpose

The DSS Peer Node is the data plane. It stores encrypted file shards, serves them to other nodes, and runs the upload/download pipelines on behalf of the user.

## Starting a Peer Node

```bash
# Via Electron app (recommended — no terminal needed)
Open the DSS app → choose "Join as Peer Node" → enter coordinator address

# Manual
cd dss
python -m dss.client.app.main
```

## Key Modules

```
client/app/
├── main.py                         # FastAPI factory, identity init, service wiring
├── core/
│   ├── config.py                   # Settings (env vars / defaults)
│   └── identity.py                 # RSA-2048 key pair persistence, node_id derivation
├── api/routes/
│   ├── shards.py                   # PUT/GET/DELETE /shards — store and serve shards
│   └── node.py                     # /node/info, connect, upload-bytes (SSE), download (SSE)
└── services/
    ├── coordinator_client.py       # HTTP client with retry logic
    ├── upload_pipeline.py          # compress → encrypt → RS encode → distribute
    ├── download_pipeline.py        # fetch → RS decode → decrypt → decompress
    └── heartbeat_service.py        # Background heartbeat + auto re-registration
```

## Upload Flow

```
User drops file → upload-bytes API → UploadPipeline:
  zlib compress → AES-256-GCM encrypt → RS encode (4-of-6) → HTTP PUT to 6 peer nodes
  → coordinator.complete_upload() → file available
```

## Download Flow

```
User clicks Download → download API → DownloadPipeline:
  coordinator.get_download_info() → fetch shards from peers (any 4 of 6)
  → RS decode → AES-256-GCM decrypt → zlib decompress → write to Downloads/
```

## Progress Streaming

Upload and download endpoints use **Server-Sent Events (SSE)** to stream real-time progress back to the UI. Each event is a JSON object:

```json
{"type": "progress", "pct": 45}
{"type": "done", "file_id": "abc123", "filename": "photo.jpg", "status": "available"}
{"type": "error", "detail": "Cannot reach coordinator"}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DSS_NODE_HOST` | `0.0.0.0` | Bind address |
| `DSS_NODE_PORT` | `8100` | Port (auto-assigned by Electron) |
| `DSS_COORDINATOR_URL` | `http://localhost:8000` | Coordinator address |
| `DSS_IDENTITY_DIR` | `~/.dss/identity` | RSA key storage |
| `DSS_STORAGE_DIR` | `~/.dss/shards` | Shard data directory |
| `DSS_ADVERTISED_HOST` | `127.0.0.1` | IP announced to coordinator |
| `DSS_CAPACITY` | `10 GB` | Advertised storage capacity |

## Troubleshooting

**"Not connected to coordinator"** — Use the Connect button in the dashboard. Enter the coordinator's IP and port.

**Upload fails** — Make sure at least 6 peer nodes are online (or fewer if you changed the shard count). All target nodes must be reachable.

**Download fails with "not enough shards"** — At least 4 of 6 peer nodes storing the file must be online.

**Private key location** — Your RSA key is at `~/.dss/identity/private_key.pem`. Keep it safe — without it, you cannot decrypt your files.
