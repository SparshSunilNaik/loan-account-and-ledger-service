from fastapi import FastAPI

from ledgercore.api.routes import router

app = FastAPI(
    title="LedgerCore",
    version="0.1.0",
    description="Phase 1: loan origination and schedules. Local development only; authentication pending.",
)
app.include_router(router)
