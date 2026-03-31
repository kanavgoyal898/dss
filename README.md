# DSS (Distributed Storage System)

DSS is a distributed storage platform that encrypts, splits, and distributes files across multiple machines. It is designed for fault tolerance, privacy, and decentralised data availability.

Even if multiple nodes go offline, files can still be reconstructed. All data is encrypted end-to-end, and only the original uploader can decrypt it.

## Features

* End-to-end encryption (AES-256 + RSA key wrapping)
* Fault tolerance using Reed–Solomon encoding (k=4, n=6)
* Distributed shard storage across peer nodes
* Coordinator-based metadata and network management
* Real-time upload and download pipelines
* Web-based dashboards for administration and node monitoring
* Fully self-hostable

## Architecture Overview

```
dss/
├── server/        # Coordinator (control plane)
├── client/        # Peer node (data plane)
├── shared/        # Shared crypto, encoding, schemas
├── ui/            # Next.js dashboards
└── tests/         # Test suite
```

### Components

**Coordinator (Server)**

* Tracks peer nodes
* Stores file metadata
* Assigns shard distribution
* Monitors network health

**Peer Node (Client)**

* Stores encrypted shards
* Handles upload and download pipelines
* Communicates with coordinator

**Web UI**

* Admin dashboard (network, peers, files)
* Node dashboard (storage, uploads, downloads)

## How It Works

### Upload Pipeline

```
File → Compress → Encrypt → Encode → Distribute
```

1. File is compressed (zlib)
2. Encrypted using AES-256-GCM
3. AES key encrypted with RSA public key
4. Split using Reed–Solomon (4-of-6)
5. Distributed across peer nodes

### Download Pipeline

```
Fetch → Reconstruct → Decrypt → Decompress
```

1. Retrieve any 4 of 6 shards
2. Reconstruct original ciphertext
3. Decrypt using RSA + AES
4. Decompress to original file

## Getting Started

### Requirements

* Python 3.11+
* Node.js 18+

### 1. Clone the Repository

```bash
git clone https://github.com/kanavgoyal898/dss
cd dss
```

### 2. Setup Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

### 3. Run the Coordinator

```bash
python run_coordinator.py
```

Runs on:

```
http://localhost:8000
```

### 4. Start Peer Nodes

Run multiple nodes in separate terminals:

```bash
python run_node.py --port 8101
python run_node.py --port 8102
python run_node.py --port 8103
python run_node.py --port 8104
python run_node.py --port 8105
python run_node.py --port 8106
```

At least **6 nodes** are required for default redundancy.

### 5. Start the Web UI

```bash
cd ui
npm install
npm run dev
```

Open:

```
http://localhost:3000
```

## Usage

### Upload a File

```bash
curl -X POST http://localhost:8101/api/v1/node/upload \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/absolute/path/to/file"}'
```

### Download a File

```bash
curl -X POST http://localhost:8101/api/v1/node/download \
  -H "Content-Type: application/json" \
  -d '{"file_id": "YOUR_FILE_ID"}'
```

## Configuration

| Variable            | Default               | Description            |
| ------------------- | --------------------- | ---------------------- |
| DSS_NODE_PORT       | 8100                  | Peer node port         |
| DSS_COORDINATOR_URL | http://localhost:8000 | Coordinator URL        |
| DSS_STORAGE_DIR     | ~/.dss/shards         | Shard storage location |
| DSS_IDENTITY_DIR    | ~/.dss/identity       | Key storage            |
| DSS_CAPACITY        | 10 GB                 | Node storage capacity  |

## Fault Tolerance

DSS uses Reed–Solomon encoding:

* Total shards: 6
* Required shards: 4
* Fault tolerance: up to 2 node failures

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Security Model

| Property        | Mechanism               |
| --------------- | ----------------------- |
| Confidentiality | AES-256-GCM encryption  |
| Key Security    | RSA-2048 key wrapping   |
| Integrity       | SHA-256 verification    |
| Availability    | Reed–Solomon redundancy |

Private keys never leave the node.

## Troubleshooting

**Coordinator not reachable**

* Ensure it is running on port 8000

**Upload fails**

* At least 6 nodes must be online

**Download fails**

* Minimum 4 shards required

**Port conflicts**

* Use different `--port` values for nodes


## Development Notes

* No inline comments; use docstrings
* Follow modular architecture (server/client/shared)
* Add tests for all new features


## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for changes
4. Submit a pull request
