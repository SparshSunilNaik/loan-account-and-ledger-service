import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ledgercore.api.financial import router as financial_router
from ledgercore.api.routes import router

app = FastAPI(
    title="LedgerCore",
    version="0.3.0",
    description="Local development demo only. X-Demo-User is NOT production authentication.",
)


@app.middleware("http")
async def correlation(request: Request, call_next):
    value = request.headers.get("X-Correlation-ID") or str(uuid4())
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value):
        return JSONResponse(
            status_code=400, content={"detail": "Invalid correlation ID"}
        )
    request.state.correlation_id = value
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = value
    return response


app.include_router(router)
app.include_router(financial_router)
