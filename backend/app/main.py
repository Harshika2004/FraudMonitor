import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root and backend dir to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_transactions import router as transactions_router
from backend.app.api.routes_alerts import router as alerts_router
from backend.app.api.routes_rules import router as rules_router
from backend.app.api.routes_analytics import router as analytics_router
from backend.app.api.routes_customers import router as customers_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fraud_monitoring")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} starting up in {settings.APP_ENV} mode.")
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Deterministic rule-based banking transaction monitoring and explainable risk analysis system.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS Middleware with narrow local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global safe exception handler: never leak raw SQL errors or internal credentials
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    error_msg = str(exc) if settings.DEBUG else (
        "An internal server error occurred while processing the transaction monitoring request. "
        "Check system logs for audit details."
    )
    return JSONResponse(
        status_code=500,
        content={"detail": error_msg}
    )

# Include API Routers under /api
api_prefix = "/api"
app.include_router(health_router, prefix=api_prefix)
app.include_router(transactions_router, prefix=api_prefix)
app.include_router(alerts_router, prefix=api_prefix)
app.include_router(rules_router, prefix=api_prefix)
app.include_router(analytics_router, prefix=api_prefix)
app.include_router(customers_router, prefix=api_prefix)

# Mount frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    # Serve HTML views
    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/transactions", include_in_schema=False)
    def serve_transactions():
        return FileResponse(FRONTEND_DIR / "transactions.html")

    @app.get("/alerts", include_in_schema=False)
    def serve_alerts():
        return FileResponse(FRONTEND_DIR / "alerts.html")

    @app.get("/rules", include_in_schema=False)
    def serve_rules():
        return FileResponse(FRONTEND_DIR / "rules.html")

    @app.get("/customers", include_in_schema=False)
    def serve_customers():
        return FileResponse(FRONTEND_DIR / "customers.html")
