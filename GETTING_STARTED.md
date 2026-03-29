# DSS — Getting Started Guide

This guide walks a first-time user through every step to go from the downloaded archive to a fully running DSS network — coordinator, multiple peer nodes, and both dashboards — using nothing but a terminal and a browser.

**Requirements:** Python 3.11 or later · Node.js 18 or later (for the UI only)

---

## 1. Extract the Archive

```bash
tar -xzf dss.tar.gz
cd dss
```

Your working directory is now `dss/`. All commands below run from here unless stated otherwise.

---

## 2. Create a Python Virtual Environment

```bash
python3 -m venv .venv
```

Activate it. You must do this in **every new terminal window** you open:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

You will see `(.venv)` at the start of your prompt when it is active.

---

## 3. Install the DSS Python Package

```bash
pip install -e .
```

This installs DSS and all of its Python dependencies (FastAPI, cryptography, etc.) into the venv. The `-e` flag means "editable" — the source files are used directly so any changes take effect immediately.

Verify the install:

```bash
python -c "from dss.shared.encoding.reed_solomon import encode_shards; print('DSS installed OK')"
```

---

## 4. Run the Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

All **55 tests** should pass. If any fail, your Python version or OS may have a compatibility issue — open an issue and include the output.

---

## 5. Start the DSS Coordinator (Admin / Server)

Open a **new terminal**, activate the venv, and run:

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m dss.server.app.main
```

You will see output like:

```
INFO:     DSS health monitor started
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The coordinator is now live. **Leave this terminal open.**

You can verify it is working:

```bash
curl http://localhost:8000/api/v1/peers
# → []   (empty list, no peers yet)
```

---

## 6. Start DSS Peer Nodes

Each peer node is a separate process. For a local test you can run two or more on different ports. Open a **new terminal** for each node.

### Node A (port 8101)

```bash
source .venv/bin/activate
DSS_NODE_PORT=8101 DSS_ADVERTISED_HOST=127.0.0.1 python -m dss.client.app.main
```

### Node B (port 8102)

```bash
source .venv/bin/activate
DSS_NODE_PORT=8102 DSS_ADVERTISED_HOST=127.0.0.1 python -m dss.client.app.main
```

Repeat for nodes C (8103), D (8104), E (8105), F (8106). DSS requires **at least 6 online peers** by default (Reed-Solomon uses k=4, n=6).

> **Tip — running fewer peers for quick testing:**  
> If you only want to test with fewer terminals, launch exactly 6 nodes on ports 8101–8106.  
> All six must be running before you upload a file.

Each node prints its node_id on startup:

```
INFO     dss.node: DSS Node started: node_id=3f7a2c...
```

Node identity (RSA key pair) is generated on first launch and saved to `~/.dss/identity/`. On subsequent runs the same identity is reused automatically.

---

## 7. Upload a File

With the coordinator and 6 peer nodes running, use any of the node HTTP APIs to upload. Here we use the Node A API at port 8101.

**Step 1 — Register and get a token**

The node registers automatically on startup. To upload via curl you need its token. The node API proxies this for you — just call its `/node/upload` endpoint:

```bash
curl -s -X POST http://localhost:8101/api/v1/node/upload \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/absolute/path/to/yourfile.pdf"}'
```

Replace `/absolute/path/to/yourfile.pdf` with any file on your system.

On success you receive:

```json
{
  "file_id": "a1b2c3d4e5f6...",
  "filename": "yourfile.pdf",
  "status": "available"
}
```

Save the `file_id` — you need it to download.

---

## 8. Download a File

From any node (it does not have to be the uploader):

```bash
curl -s -X POST http://localhost:8101/api/v1/node/download \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "a1b2c3d4e5f6...",
    "output_path": "/tmp/recovered_yourfile.pdf"
  }'
```

Response:

```json
{"file_id": "a1b2c3d4e5f6...", "saved_to": "/tmp/recovered_yourfile.pdf"}
```

The file at `/tmp/recovered_yourfile.pdf` is byte-for-byte identical to the original.

---

## 9. Start the DSS Dashboards (UI)

The dashboards require Node.js. Open a **new terminal**:

```bash
cd ui
npm install
npm run dev
```

Open your browser at **http://localhost:3000**

You will see the DSS mode selector. Choose:

- **Open Admin Dashboard** → coordinator overview, peer list, file metadata, shard distribution chart, network policy controls
- **Open Node Dashboard** → node identity, disk usage, shard inventory, upload/download forms

> The Admin Dashboard reads from `http://localhost:8000` by default.  
> The Node Dashboard reads from `http://localhost:8100` by default.  
> If your node runs on a different port (e.g. 8101), set `NEXT_PUBLIC_NODE_URL=http://localhost:8101` before `npm run dev`.

---

## 10. Test Fault Tolerance

DSS tolerates losing any 2 of 6 nodes simultaneously (r = n − k = 6 − 4 = 2).

1. Upload a file while all 6 nodes are running.
2. Stop any 2 node processes (Ctrl-C in their terminals).
3. Download the same file — it reconstructs cleanly from the remaining 4 shards.
4. Stopping a 3rd node makes the file unrecoverable (fewer than k=4 shards available).

---

## Quick Reference — All Endpoints

### Coordinator (default: http://localhost:8000)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/peers/register` | Register a peer node |
| `POST` | `/api/v1/peers/heartbeat` | Liveness update |
| `GET`  | `/api/v1/peers` | List all peers |
| `POST` | `/api/v1/files/init` | Start an upload session |
| `POST` | `/api/v1/files/complete` | Finalise upload |
| `GET`  | `/api/v1/files` | List all files |
| `GET`  | `/api/v1/files/{file_id}/download` | Get shard locations for download |
| `GET`  | `/api/v1/admin/health` | System health summary |
| `GET`  | `/api/v1/admin/network` | Current network policy |
| `POST` | `/api/v1/admin/network/mode` | Change network mode |
| `POST` | `/api/v1/admin/network/allowed-ips` | Update IP allowlist |
| `GET`  | `/api/v1/admin/shards` | Per-node shard counts |

### Peer Node (example: http://localhost:8101)

| Method | Path | Description |
|--------|------|-------------|
| `PUT`  | `/api/v1/shards/{shard_id}` | Receive a shard (called by upload pipeline) |
| `GET`  | `/api/v1/shards/{shard_id}` | Serve a shard (called by download pipeline) |
| `GET`  | `/api/v1/shards` | List all stored shards |
| `GET`  | `/api/v1/node/info` | Node identity, disk usage, connectivity |
| `GET`  | `/api/v1/node/files` | Files owned by this node |
| `POST` | `/api/v1/node/upload` | Trigger upload pipeline |
| `POST` | `/api/v1/node/download` | Trigger download pipeline |

---

## Configuration Reference

All settings have sensible defaults. You only need to set the values below if you want to override them — most users won't need to touch anything.

| Variable | Default | When to change |
|---|---|---|
| `DSS_NODE_PORT` | `8100` | Running multiple nodes on the same machine |
| `DSS_ADVERTISED_HOST` | `127.0.0.1` | Nodes on separate machines — set to LAN/public IP |
| `DSS_COORDINATOR_URL` | `http://localhost:8000` | Coordinator is on a different machine |
| `DSS_SERVER_PORT` | `8000` | Coordinator port conflicts with another service |
| `DSS_JWT_SECRET` | (dev default) | **Always change in production** |
| `DSS_NETWORK_MODE` | `global` | Restrict to `lan` or `allowlist` via Admin Dashboard |
| `DSS_IDENTITY_DIR` | `~/.dss/identity` | Change per-node key storage location |
| `DSS_STORAGE_DIR` | `~/.dss/shards` | Change shard storage location |
| `DSS_CAPACITY` | `10 GB` | Advertised storage capacity in bytes |

---

## Troubleshooting

**"RuntimeError: DSS: need 6 online peers for shard distribution, only N available"**  
Not enough peer nodes are running. Start more nodes until you have 6 online. The coordinator health monitor marks nodes offline after 30 seconds without a heartbeat.

**"ModuleNotFoundError: No module named 'dss'"**  
The venv is not activated, or `pip install -e .` was not run. Activate the venv and reinstall.

**Node Dashboard shows a coordinator error**  
The node at the URL shown in the dashboard is not reachable. Check that the peer node process is running and the port matches `NEXT_PUBLIC_NODE_URL`.

**File download fails after nodes go offline**  
More than 2 nodes (for the default k=4, n=6 scheme) are unreachable. Bring nodes back online or accept that the file is in a degraded/unrecoverable state.

**Shard integrity conflict (HTTP 409)**  
A stored shard's SHA-256 does not match its metadata — the shard file was corrupted on disk. Delete it via `DELETE /api/v1/shards/{shard_id}` and the system will attempt lazy recovery on the next download attempt.
