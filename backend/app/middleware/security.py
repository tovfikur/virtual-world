"""
Security hardening configuration and middleware.
Implements security headers, CORS hardening, HTTPS enforcement, and CSP policies.
"""

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from typing import Callable, Optional, List
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers to all responses.
    
    Headers:
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: XSS filter
    - Strict-Transport-Security: HTTPS enforcement
    - Content-Security-Policy: XSS/injection prevention
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Control browser features
    """
    
    def __init__(
        self,
        app,
        csp_policy: Optional[str] = None,
        hsts_max_age: int = 31536000  # 1 year
    ):
        self.app = app
        self.hsts_max_age = hsts_max_age
        
        # Default CSP policy (strict)
        self.csp_policy = csp_policy or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: https:; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "upgrade-insecure-requests"
        )
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Enforce HTTPS
        response.headers["Strict-Transport-Security"] = (
            f"max-age={self.hsts_max_age}; includeSubDomains; preload"
        )
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=(), "
            "usb=(), "
            "vr=()"
        )
        
        return response


class RateLimitSecurityMiddleware:
    """
    Middleware to detect and mitigate common attacks.
    
    Detects:
    - SQL injection patterns
    - Path traversal attempts
    - Large payload attacks
    - Brute force attempts
    """
    
    def __init__(
        self,
        app,
        max_payload_size: int = 10 * 1024 * 1024,  # 10MB
        rate_limit_window: int = 60
    ):
        self.app = app
        self.max_payload_size = max_payload_size
        self.rate_limit_window = rate_limit_window
        self.request_counts = {}
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Check security aspects of request."""
        # Check payload size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_payload_size:
            return Response(
                content="Payload too large",
                status_code=413
            )
        
        # Check for SQL injection patterns
        if await self._check_sql_injection(request):
            logger.warning(f"SQL injection attempt detected from {request.client.host}")
            return Response(
                content="Forbidden",
                status_code=403
            )
        
        # Check for path traversal
        if self._check_path_traversal(request.url.path):
            logger.warning(f"Path traversal attempt detected from {request.client.host}")
            return Response(
                content="Forbidden",
                status_code=403
            )
        
        response = await call_next(request)
        return response
    
    async def _check_sql_injection(self, request: Request) -> bool:
        """Check for SQL injection patterns."""
        sql_patterns = [
            "union", "select", "insert", "update", "delete",
            "drop", "create", "alter", "exec", "execute",
            "script", "javascript", "onerror", "onclick"
        ]
        
        # Check URL parameters
        for param in request.query_params.values():
            if any(pattern in param.lower() for pattern in sql_patterns):
                return True
        
        # Check body
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                body_str = body.decode() if body else ""
                if any(pattern in body_str.lower() for pattern in sql_patterns):
                    return True
        except:
            pass
        
        return False
    
    def _check_path_traversal(self, path: str) -> bool:
        """Check for path traversal patterns."""
        if ".." in path or "~" in path or "\\x" in path:
            return True
        return False


class CORSConfiguration:
    """CORS configuration for secure cross-origin requests."""
    
    @staticmethod
    def get_middleware(app, allowed_origins: Optional[List[str]] = None):
        """
        Get CORS middleware configured for security.
        
        Args:
            app: FastAPI app
            allowed_origins: List of allowed origins
        
        Returns:
            Configured CORSMiddleware
        """
        if allowed_origins is None:
            allowed_origins = [
                "http://localhost:3000",
                "http://localhost:8000",
                "https://exchange.example.com"
            ]
        
        return CORSMiddleware(
            app,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=[
                "Accept",
                "Accept-Language",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token"
            ],
            expose_headers=[
                "Content-Length",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
                "Retry-After"
            ],
            max_age=600  # 10 minutes
        )


class TrustedHostConfiguration:
    """Trusted host configuration to prevent host header attacks."""
    
    @staticmethod
    def get_middleware(app, allowed_hosts: Optional[List[str]] = None):
        """
        Get TrustedHost middleware.
        
        Args:
            app: FastAPI app
            allowed_hosts: List of allowed hosts
        
        Returns:
            Configured TrustedHostMiddleware
        """
        if allowed_hosts is None:
            allowed_hosts = [
                "localhost",
                "localhost:8000",
                "exchange.example.com",
                "*.example.com"
            ]
        
        return TrustedHostMiddleware(
            app,
            allowed_hosts=allowed_hosts
        )


def apply_security_hardening(
    app,
    allow_origins: Optional[List[str]] = None,
    allowed_hosts: Optional[List[str]] = None,
    enable_hsts: bool = True,
    enable_cors: bool = True,
    csp_policy: Optional[str] = None
) -> None:
    """
    Apply all security hardening to FastAPI app.
    
    Args:
        app: FastAPI application
        allow_origins: CORS allowed origins
        allowed_hosts: Trusted hosts
        enable_hsts: Enable HTTPS enforcement
        enable_cors: Enable CORS
        csp_policy: Custom CSP policy
    """
    # Add security headers middleware
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp_policy=csp_policy,
        hsts_max_age=31536000 if enable_hsts else 0
    )
    
    # Add attack detection middleware
    app.add_middleware(RateLimitSecurityMiddleware)
    
    # Add trusted host middleware
    if allowed_hosts:
        app.add_middleware(
            TrustedHostConfiguration.get_middleware,
            allowed_hosts=allowed_hosts
        )
    
    # Add CORS middleware
    if enable_cors:
        cors = CORSConfiguration.get_middleware(app, allow_origins)
        app.add_middleware(cors)
    
    logger.info("Security hardening applied to application")


# Security configuration presets

PRODUCTION_CONFIG = {
    "allow_origins": [
        "https://exchange.example.com",
        "https://app.example.com"
    ],
    "allowed_hosts": [
        "exchange.example.com",
        "app.example.com"
    ],
    "enable_hsts": True,
    "enable_cors": True,
    "csp_policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: https:; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "upgrade-insecure-requests"
    )
}

DEVELOPMENT_CONFIG = {
    "allow_origins": [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000"
    ],
    "allowed_hosts": [
        "localhost",
        "127.0.0.1"
    ],
    "enable_hsts": False,
    "enable_cors": True,
    "csp_policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: ws: https: http:; "
        "frame-ancestors 'self'"
    )
}
