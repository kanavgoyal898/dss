# DSS — Distributed Storage System

DSS is a distributed storage system designed to store files securely across multiple independent nodes. Instead of relying on a single server, files are encrypted, split into fragments, and distributed across a network of peers. This approach improves reliability and ensures that data can still be recovered even if some nodes go offline.

The system is built with a focus on practical fault tolerance, predictable behavior, and clear architecture. It is suitable for experimentation, learning about distributed systems, or running small-scale deployments where control over storage and data flow is important.

![P2P Network](./image.jpg)

## Features

DSS combines standard cryptographic techniques with redundancy mechanisms to provide a balanced storage system. Files are encrypted before leaving the client, split into shards using Reed–Solomon encoding, and then distributed across multiple nodes. The coordinator keeps track of where shards are stored but does not have access to plaintext data.

The system also includes basic observability through APIs and a web interface, making it easier to understand how data moves through the network and how nodes behave over time.

## Architecture

```
dss/
├── server/        # Coordinator (control plane)
├── peer/          # Peer node (data plane)
├── shared/        # Crypto, encoding, schemas
├── ui/            # Web dashboard (Next.js)
├── start.sh       # Quick multi-node launcher
└── tests/         # Test suite
```

The architecture is divided into a coordinator and multiple peer nodes. The coordinator is responsible for tracking node availability, maintaining metadata, and deciding how shards are distributed. Peer nodes are responsible for storing encrypted shards and serving them when requested.

This separation keeps responsibilities clear and allows the system to scale horizontally by simply adding more nodes.

## Quick Start

The easiest way to explore DSS is by using the provided `start.sh` script. It launches a coordinator along with several peer nodes on different ports, creating a local distributed environment without requiring manual setup.

```bash
chmod +x start.sh
./start.sh
```

This setup is intended for experimentation and testing. It allows you to observe how files are split, distributed, and reconstructed without needing to configure multiple machines.

## Environment Configuration

DSS is configured through environment variables. A sample configuration is shown below and can be copied into a `.env` file. The default values are suitable for local development, but some of them should be changed when deploying to a hosted environment.

```env
# DSS environment configuration
# All values below reflect production-safe defaults.

# --- Coordinator (server) ---
DSS_ADMIN_PASSWORD=<strong-password>                    # Change for Render deployment
DSS_SERVER_HOST=0.0.0.0
DSS_SERVER_PORT=8000                                    # Not needed for Render deployment
DSS_JWT_SECRET=<long-random-secret>                     # Change for Render deployment
DSS_JWT_EXPIRE_MINUTES=60
DSS_NETWORK_MODE=global
DSS_HEARTBEAT_TIMEOUT=30
DSS_HEALTH_INTERVAL=15

# --- UI ---
NEXT_PUBLIC_COORDINATOR_URL=http://localhost:8000       # Change to Render coordinator URL for Vercel deployment

# --- Peer Node (client) ---
DSS_NODE_HOST=0.0.0.0
DSS_NODE_PORT=8100                                      # Not needed for Render deployment
DSS_COORDINATOR_URL=http://localhost:8000               # Change to Render coordinator URL for Render deployment
DSS_IDENTITY_DIR=~/.dss/identity
DSS_STORAGE_DIR=~/.dss/shards
DSS_HEARTBEAT_INTERVAL=15
DSS_ADVERTISED_HOST=127.0.0.1                           # Not needed for Render deployment
DSS_CHUNK_SIZE=1048576
DSS_CAPACITY=4294967296

# --- UI ---
NEXT_PUBLIC_COORDINATOR_URL=http://localhost:8000       # Change to Render coordinator URL for Vercel deployment
NEXT_PUBLIC_NODE_URL=http://localhost:8100              # Change to Render peer node URL for Vercel deployment

# --- Shared ---
DSS_DATA_SHARDS=4
DSS_TOTAL_SHARDS=6
```

When deploying, you should replace placeholder values such as passwords and secrets, and update the coordinator URL so that peer nodes and the UI can communicate with the correct service.

## Running Tests

The project includes a test suite that can be used to verify basic functionality and catch regressions during development.

```bash
pip install pytest pytest-asyncio
pytest dss/tests -v
```

Running tests locally is recommended before making changes or deploying updates.

## Deployment on Render

DSS can be deployed on Render by running the coordinator and peer nodes as separate services. Each component runs independently, which makes it straightforward to scale the number of nodes or restart individual services without affecting the rest of the system.

### Coordinator Service

The coordinator manages metadata and node coordination. It should be deployed as a single service.

* Environment: Python
* Build Command:

```bash
pip install -e .
```

* Start Command:

```bash
python -m dss.server.app.main
```

### Peer Node Services

Peer nodes handle storage and retrieval of shards. Multiple instances should be deployed to achieve redundancy.

* Environment: Python
* Build Command:

```bash
pip install -e .
```

* Start Command:

```bash
python -m dss.peer.app.main
```

In practice, you should run several peer services so the system can tolerate node failures. The exact number depends on your shard configuration.

### Environment Variables (Render)

In the Render dashboard, configure the required environment variables. At minimum, you should set a strong admin password, a secure JWT secret, and the correct coordinator URL so that nodes can register and communicate properly.

## Security Model

DSS uses a combination of symmetric and asymmetric cryptography to protect data. Files are encrypted using AES-256-GCM before being split, and the encryption keys are protected using RSA. This ensures that even if a node stores a shard, it cannot reconstruct or read the original file on its own.

Integrity is verified using hashing, and availability is achieved through shard redundancy. The system is designed so that only a subset of shards is required to reconstruct the original file.

## Fault Tolerance

The system uses a shard-based redundancy model. For example, with 6 total shards and 4 required shards, the system can tolerate up to 2 node failures without losing data. This trade-off between redundancy and storage overhead can be adjusted depending on requirements.

## Contributing

Contributions are welcome. You can fork the repository, create a new branch for your changes, and open a pull request. Adding tests alongside new features or fixes helps maintain stability.
