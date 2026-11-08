from starlette.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Verify health endpoint returns 200, valid status, timestamp, and request ID."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "testing"
    assert "version" in data
    assert "timestamp" in data

    # Check request ID header
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"].startswith("req_")


def test_cors_headers(client: TestClient):
    """Verify CORS headers respond to configured origins."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
