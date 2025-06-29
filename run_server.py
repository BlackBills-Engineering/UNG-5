#!/usr/bin/env python3
"""
MKR5 Pump Control API Server
Run this script to start the FastAPI server for pump control
"""

import uvicorn
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Run the FastAPI application
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )
