import pytest
from fastapi import APIRouter
from starlette.testclient import TestClient

from app.core.errors import (
    ConflictError,
    CreatorSelfApprovalError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.main import create_application

# Test router to trigger specific error scenarios
error_test_router = APIRouter(prefix="/test-errors")


@error_test_router.get("/not-found")
def trigger_not_found():
    raise NotFoundError(resource="Guideline", identifier="guideline_123")


@error_test_router.get("/forbidden")
def trigger_forbidden():
    raise ForbiddenError("Admin permission required")


@error_test_router.get("/creator-approval")
def trigger_creator_approval():
    raise CreatorSelfApprovalError()


@error_test_router.get("/unauthorized")
def trigger_unauthorized():
    raise UnauthorizedError("Invalid token")


@error_test_router.get("/conflict")
def trigger_conflict():
    raise ConflictError("Rule name already exists")


@error_test_router.get("/unhandled-server-error")
def trigger_unhandled():
    raise RuntimeError("Sensitive internal database connection failed: secret_db_pwd_123")


@pytest.fixture
def error_client():
    test_application = create_application()
    test_application.include_router(error_test_router)
    with TestClient(test_application, raise_server_exceptions=False) as c:
        yield c


def test_not_found_error_envelope(error_client: TestClient):
    response = error_client.get("/test-errors/not-found")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "guideline_123" in body["error"]["message"]
    assert "request_id" in body["error"]
    assert body["error"]["request_id"] is not None


def test_creator_cannot_approve_own_content_error(error_client: TestClient):
    response = error_client.get("/test-errors/creator-approval")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "CREATOR_CANNOT_APPROVE_OWN_CONTENT"
    assert "creators cannot approve" in body["error"]["message"].lower()


def test_generic_exception_does_not_leak_stack_trace_or_secrets(error_client: TestClient):
    response = error_client.get("/test-errors/unhandled-server-error")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    # Crucial security check: sensitive text must NEVER leak in response body
    assert "secret_db_pwd_123" not in response.text
    assert "RuntimeError" not in response.text
    assert "traceback" not in response.text.lower()
    assert body["error"]["request_id"] is not None
