import os
import uvicorn

from container import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("RELOAD", "0") == "1",  # RELOAD=1 en développement
    )
