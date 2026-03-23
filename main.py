"""Entry point — run with: python main.py"""

import os
import uvicorn

# Re-export the ASGI app for deployment platforms (Railway, etc.)
from backend.app import app  # noqa: F401

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    is_dev = not (os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
        reload=is_dev,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
