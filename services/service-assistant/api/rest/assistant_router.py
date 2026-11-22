from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from application.use_cases.ask_assistant_use_case import AskAssistantUseCase
from application.use_cases.generate_report_use_case import GenerateReportUseCase
from domain.exceptions.domain_exceptions import UnsafeQuestionException, UnsafeResponseException
from shared.security.auth import require


class AskRequest(BaseModel):
    machine_id: str
    question: str


class ReportRequest(BaseModel):
    hours: int = Field(24, ge=1, le=24 * 31)


def get_router(ask_use_case: AskAssistantUseCase, report_use_case: GenerateReportUseCase, reports) -> APIRouter:
    router = APIRouter(prefix="/assistant", tags=["assistant"])

    @router.post("/ask", dependencies=[Depends(require("llm:use"))])
    async def ask(req: AskRequest):
        """Poser une question sur une machine."""
        try:
            return {"answer": await ask_use_case.execute(req.machine_id, req.question)}
        except (UnsafeQuestionException, UnsafeResponseException) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/report")
    async def report(req: ReportRequest = ReportRequest(), user: dict = Depends(require("reports:export"))):
        """Générer un rapport maintenant ; il est aussi enregistré dans l'historique."""
        content = await report_use_case.execute(hours=req.hours)
        saved = reports.save(content, req.hours, user.get("username") or user.get("email", "inconnu"))
        return {"report": content, **saved}

    @router.get("/reports", dependencies=[Depends(require("reports:export"))])
    def list_reports(limit: int = Query(30, ge=1, le=200)):
        """Historique des rapports (automatiques et manuels)."""
        return reports.list(limit)

    return router
