"""src/api/main.py — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.api.routes import customers, plans, incidents, tickets, knowledge_base, diagnostics, support

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import logging
import uvicorn

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FlowDesk Support API",
    description="Mock REST API + Agentic Support Orchestrator",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url.path),
        }
    )

# ── Request logging middleware ────────────────────────────────────
class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        latency = round((time.time() - start) * 1000)
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({latency}ms)")
        return response

app.add_middleware(LogRequestsMiddleware)

# ── Register routers ──────────────────────────────────────────────
app.include_router(customers.router)
app.include_router(plans.router)
app.include_router(incidents.router)
app.include_router(tickets.router)
app.include_router(knowledge_base.router)
app.include_router(diagnostics.router)
app.include_router(support.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__=="__main__":
    uvicorn.run(
        "src.api.main:app",
        host="localhost",
        port=8001,
        reload=True
    )