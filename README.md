# DSS (Distributed Storage System)

DSS is a distributed storage platform that encrypts, splits, and spreads your files across multiple machines. Even if some machines go offline, your files can still be recovered. All data is encrypted end-to-end — only the original uploader can decrypt it.

---

## Getting Started (No Technical Knowledge Required)

### What You Need

- A computer running Windows, macOS, or Linux
- Python 3.9 or later — download free from [python.org](https://python.org)
  - **Windows:** tick "Add Python to PATH" during install
- Node.js 18 or later (for the web UI) — download from [nodejs.org](https://nodejs.org)

### Step 1 — Start the UI

```bash
cd ui
npm install
npm run dev
```

Leave that terminal running. Open your browser to http://localhost:3000.

### Step 2 — Launch DSS

**Option A — Use the Electron app (recommended)**

Open the DSS app. It will:
- Check Python is installed
- Install all Python dependencies automatically
- Ask whether you want to start a Coordinator or join as a Peer Node

**Option B — Run manually**

Start the Coordinator:
```bash
cd dss
pip install -r requirements.txt
python -m dss.server.app.main
```

Start a Peer Node (in a new terminal):
```bash
python -m dss.client.app.main
```

---

## How It Works

### Coordinator (Admin)

The Coordinator is the brain of the network. It:
- Keeps track of all Peer Nodes
- Stores file metadata (not the actual files)
- Tells nodes where to send each file shard

### Peer Node (User)

A Peer Node joins the network and:
- Stores encrypted file shards from other users
- Uploads your files through the full pipeline
- Downloads and reconstructs files on demand

### Upload Pipeline

```
Your file → Split into chunks → Compress → Encrypt (AES-256) → Reed-Solomon encode → Distribute to nodes
```

### Download Pipeline

```
Fetch shards from nodes → Reed-Solomon reconstruct → Decrypt → Decompress → Your file
```

---

## Architecture

```
dss/
├── server/        # DSS Coordinator — peer registry, metadata, health monitoring
├── client/        # DSS Peer Node — upload/download pipelines, shard storage
├── shared/        # Shared code — cryptography, Reed-Solomon, Pydantic schemas
├── electron/      # DSS desktop app — one-click launcher
├── ui/            # React/Next.js dashboards
└── tests/         # Full test suite (55 tests)
```

---

## Security Model

| Property        | Mechanism                                                   |
|-----------------|-------------------------------------------------------------|
| Confidentiality | AES-256-GCM per file; key wrapped with your RSA-2048 key   |
| Integrity       | SHA-256 per shard + plaintext verification after download   |
| Availability    | Reed-Solomon (4-of-6): tolerates 2 simultaneous node failures |

Your private key never leaves your machine.

---

## Troubleshooting

**"Python not found"**
Install Python from python.org. On Windows, check "Add Python to PATH".

**"Cannot reach coordinator"**
Make sure the Coordinator is running. Check the IP address and port. Try `http://localhost:8000` if running on the same machine.

**"Not enough shards"**
At least 4 of 6 nodes must be online to reconstruct a file. Bring more nodes online.

**Upload fails halfway**
Check that all target peer nodes are online. The dashboard shows which nodes are connected.

**Port already in use**
DSS auto-selects free ports. If a conflict occurs, restart the application.

---

## Running Tests

```bash
cd dss
pip install -r requirements.txt pytest pytest-asyncio
python -m pytest tests/ -v
```

---

## Contribution Guide

1. Fork and branch from `main`.
2. Use `dss` (lowercase) for all code identifiers; `DSS` for all user-facing strings.
3. Every file must start with a module-level docstring (purpose, responsibilities, dependencies).
4. No inline comments — docstrings only.
5. Add pytest tests for any new pipeline stage or cryptographic operation.
6. Open a pull request referencing the changed component.
