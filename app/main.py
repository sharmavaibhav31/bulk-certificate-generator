from contextlib import asynccontextmanager
from datetime import datetime, timezone
import http
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.db import init_db, SessionLocal
from app.worker import recover_stuck_certificates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle hook.
    - Startup: Runs create_all, seeds 5 builtin templates, and recovers stuck processing certs.
    """
    logger.info("Initializing database and seeding templates...")
    init_db()

    with SessionLocal() as db:
        recovered = recover_stuck_certificates(db)
        if recovered > 0:
            logger.info("Startup crash recovery re-queued %d stuck certificates.", recovered)

    logger.info("Bulk Certificate Generator is ready to serve requests.")
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="High-performance, fault-tolerant bulk PDF certificate generator API.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for local Vite React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# CONSISTENT ERROR RESPONSE HANDLERS
# ==============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Formats all standard HTTPExceptions into a consistent JSON error schema."""
    try:
        code_name = http.HTTPStatus(exc.status_code).name
    except ValueError:
        code_name = "ERROR"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code_name,
                "message": exc.detail,
                "details": None,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats Pydantic request validation errors into a consistent JSON error schema."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request payload structural validation failed.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches unhandled internal server exceptions."""
    logger.exception("Unhandled server exception: %s", str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": str(exc),
            }
        },
    )


# ==============================================================================
# CORE & HEALTH ROUTES
# ==============================================================================

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for Docker / orchestration liveness probes."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Include API v1 routes
app.include_router(api_router)
