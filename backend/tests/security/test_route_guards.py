from fastapi.routing import APIRoute

from app.main import app

PUBLIC_ENDPOINTS = {
    "/api/v1/health",
    "/api/v1/health/liveness",
    "/api/v1/health/readiness",
    "/api/v1/auth/register",  # 410 GONE deprecation stub
    "/api/v1/auth/login",  # 410 GONE deprecation stub
}


def test_all_routes_have_declared_security_guards():
    """
    Security Audit: Iterates over every registered route in the FastAPI application.
    Fails if any non-public route lacks authentication or role dependencies.
    """
    unprotected_routes = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            # Check only API v1 routes
            if path.startswith("/api/v1") and path not in PUBLIC_ENDPOINTS:
                # Check route-level and parameter-level dependencies
                all_calls = []

                if hasattr(route, "dependencies") and route.dependencies:
                    for d in route.dependencies:
                        all_calls.append(getattr(d, "dependency", d))

                if hasattr(route, "dependant") and route.dependant.dependencies:
                    for d in route.dependant.dependencies:
                        all_calls.append(getattr(d, "call", d))

                dep_names = [getattr(c, "__name__", str(c)).lower() for c in all_calls]

                has_auth = any(
                    "user" in name or "member" in name or "role" in name or "approve" in name
                    for name in dep_names
                )

                if not has_auth:
                    unprotected_routes.append(f"{route.methods} {path}")

    assert not unprotected_routes, (
        f"Security Failure: The following routes lack declared authentication or role guards: {unprotected_routes}"
    )
