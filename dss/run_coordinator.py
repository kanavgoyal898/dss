"""
Purpose: DSS Coordinator launcher — run this script to start the coordinator.
Responsibilities:
    - Add the parent directory to sys.path so the dss package is importable
      without requiring installation or environment variable changes.
    - Start the DSS Coordinator via uvicorn on 0.0.0.0:8000.
Dependencies: uvicorn, dss.server.app.main
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "dss.server.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
