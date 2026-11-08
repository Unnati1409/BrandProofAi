from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.logging import request_id_ctx


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[dict[str, Any]] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    """Base application exception with typed error codes and HTTP statuses."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} '{identifier}' was not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required or invalid credentials."):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class CreatorSelfApprovalError(ForbiddenError):
    """Security rule: Content creators are strictly barred from approving their own content."""

    def __init__(self):
        super().__init__(
            message="Content creators cannot approve their own submissions. A separate reviewer or manager must approve."
        )
        self.code = "CREATOR_CANNOT_APPROVE_OWN_CONTENT"


class RateLimitExceededError(AppError):
    """Raised when an IP, user, or workspace exceeds configured request frequency limits."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please slow down and retry shortly.",
        retry_after: int = 60,
        details: list[dict[str, Any]] | None = None,
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details or [{"retry_after": retry_after}],
        )
        self.retry_after = retry_after


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = request_id_ctx.get() or request.headers.get("X-Request-ID")
    response_headers: dict[str, str] = {}
    if isinstance(exc, RateLimitExceededError):
        response_headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                "details": exc.details,
            }
        },
        headers=response_headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = request_id_ctx.get() or request.headers.get("X-Request-ID")
    formatted_errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "The request body or query parameters failed schema validation.",
                "request_id": request_id,
                "details": formatted_errors,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_ctx.get() or request.headers.get("X-Request-ID")
    # Never leak internal traceback to client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact system support with the request ID.",
                "request_id": request_id,
            }
        },
    )
