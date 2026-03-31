"""
Purpose: DSS Peer Node launcher — run this script to start a peer node.
Responsibilities:
    - Add the parent directory to sys.path so the dss package is importable
      without requiring installation or environment variable changes.
    - Accept an optional --port argument (default 8100) so multiple nodes
      can be started on the same machine without editing any config files.
    - Start the DSS Peer Node via uvicorn on the specified port.
Dependencies: uvicorn, dss.client.app.main
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSS Peer Node launcher")
    parser.add_argument(
        "--port",
        type=int,
        default=8100,
        help="Port to listen on (default: 8100). Use different ports for multiple nodes.",
    )
    parser.add_argument(
        "--coordinator",
        type=str,
        default="http://localhost:8000",
        help="Coordinator base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    os.environ["DSS_NODE_PORT"] = str(args.port)
    os.environ["DSS_COORDINATOR_URL"] = args.coordinator

    uvicorn.run(
        "dss.client.app.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level="info",
    )
