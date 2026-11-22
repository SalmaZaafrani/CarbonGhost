from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from container import container
from api.rest.assistant_router import get_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Service Assistant intelligent du systeme de monitoring carbone.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    container.start()


app.include_router(get_router(container.ask_use_case, container.report_use_case, container.reports))


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "llm": "groq" if container.llm.available else "désactivé (réponses sans IA)",
    }
