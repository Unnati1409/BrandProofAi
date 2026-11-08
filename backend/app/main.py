import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    RateLimitExceededError,
    app_error_handler,
    generic_exception_handler,
    validation_error_handler,
)
from app.core.logging import request_id_ctx, setup_logging
from app.core.rate_limit import get_client_ip, rate_limiter
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for application startup and shutdown events."""
    settings = get_settings()
    logger = setup_logging(settings.LOG_LEVEL)
    logger.info("BrandProof AI Backend starting up", extra={"environment": settings.ENVIRONMENT})
    # Ensure database schema is initialized
    init_db()
    yield
    logger.info("BrandProof AI Backend shutting down")


def create_application() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="BrandProof AI API",
        description="An Intelligent Guardian for Every Brand — Pre-publication brand governance platform",
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS configuration — strictly limited to configured frontend origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Request ID and Structured Access Logging Middleware
    @app.middleware("http")
    async def request_id_and_logging_middleware(request: Request, call_next) -> Response:
        # Resolve or generate standard request ID
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        token = request_id_ctx.set(req_id)
        start_time = time.perf_counter()

        logger = setup_logging(settings.LOG_LEVEL)

        # Check General IP Rate Limit (120 req/min/IP), excluding system endpoints
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json", "/api/v1/health")):
            client_ip = get_client_ip(request)
            try:
                rate_limiter.check_rate_limit(
                    key=f"rl:general:{client_ip}",
                    max_requests=120,
                    window_seconds=60,
                )
            except RateLimitExceededError as exc:
                return await app_error_handler(request, exc)

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Never log body content or auth headers
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} ({duration_ms}ms)",
                extra={
                    "request_id": req_id,
                    "extra_data": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                },
            )

            response.headers["X-Request-ID"] = req_id
            return response
        except AppError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(
                f"AppError in {request.method} {request.url.path}: {exc.code} - {exc.message} ({duration_ms}ms)",
                extra={"request_id": req_id},
            )
            res = await app_error_handler(request, exc)
            res.headers["X-Request-ID"] = req_id
            return res
        except RequestValidationError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(
                f"Validation error in {request.method} {request.url.path} ({duration_ms}ms)",
                extra={"request_id": req_id},
            )
            res = await validation_error_handler(request, exc)
            res.headers["X-Request-ID"] = req_id
            return res
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled error in {request.method} {request.url.path}: {str(exc)} ({duration_ms}ms)",
                extra={"request_id": req_id},
                exc_info=True,
            )
            res = await generic_exception_handler(request, exc)
            res.headers["X-Request-ID"] = req_id
            return res
        finally:
            request_id_ctx.reset(token)

    # Register typed error envelope handlers as fallback
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Mount API routers
    app.include_router(api_v1_router)

    return app


app = create_application()
