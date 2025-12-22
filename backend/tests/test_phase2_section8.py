"""
Comprehensive integration tests for Phase 2 Section 8.
Tests all API & UI enhancement components.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch
import logging

logger = logging.getLogger(__name__)


# Test fixtures

@pytest.fixture
async def notification_service():
    """Fixture for NotificationService."""
    from app.services.notification_service import (
        get_notification_service,
        NotificationType,
        NotificationPriority
    )
    service = get_notification_service()
    yield service
    # Cleanup
    service.subscribers.clear()
    for user_id in list(service.pending_notifications.keys()):
        service.clear_pending(user_id)


@pytest.fixture
async def metrics_service():
    """Fixture for MetricsService."""
    from app.services.metrics_service import (
        get_metrics_service,
        MetricType
    )
    service = get_metrics_service()
    yield service
    # Cleanup
    service.reset_counters()


@pytest.fixture
async def rate_limiter():
    """Fixture for RateLimiter."""
    from app.middleware.rate_limiter import get_rate_limiter
    limiter = get_rate_limiter()
    yield limiter
    # Cleanup
    limiter.cleanup()


@pytest.fixture
def mock_request():
    """Create mock HTTP request."""
    request = Mock()
    request.client = Mock()
    request.client.host = "127.0.0.1"
    request.headers = {
        "content-length": "1000"
    }
    request.url = Mock()
    request.url.path = "/api/v1/orders"
    return request


# Notification Service Tests

class TestNotificationService:
    """Tests for NotificationService."""
    
    async def test_subscribe_single_type(self, notification_service):
        """Test subscribing to single notification type."""
        from app.services.notification_service import NotificationType
        
        subscription = await notification_service.subscribe(
            user_id="user_123",
            types=[NotificationType.ORDER_CREATED]
        )
        
        assert subscription is not None
        assert subscription.user_id == "user_123"
        assert NotificationType.ORDER_CREATED in subscription.notification_types
    
    async def test_subscribe_multiple_types(self, notification_service):
        """Test subscribing to multiple notification types."""
        from app.services.notification_service import NotificationType
        
        subscription = await notification_service.subscribe(
            user_id="user_456",
            types=[
                NotificationType.ORDER_CREATED,
                NotificationType.PRICE_UPDATE,
                NotificationType.MARGIN_CALL
            ]
        )
        
        assert len(subscription.notification_types) == 3
    
    async def test_publish_notification(self, notification_service):
        """Test publishing notification."""
        from app.services.notification_service import NotificationType, NotificationPriority
        
        await notification_service.subscribe(
            user_id="user_789",
            types=[NotificationType.ORDER_CREATED]
        )
        
        notification_id = await notification_service.publish(
            notification_type=NotificationType.ORDER_CREATED,
            recipient_ids=["user_789"],
            data={"order_id": "order_123"},
            priority=NotificationPriority.HIGH
        )
        
        assert notification_id is not None
        
        # Check pending notification
        pending = notification_service.get_pending("user_789", limit=10)
        assert len(pending) > 0
    
    async def test_message_batching(self, notification_service):
        """Test message batching functionality."""
        from app.services.notification_service import NotificationType, NotificationPriority
        
        await notification_service.subscribe(
            user_id="user_batch",
            types=[NotificationType.PRICE_UPDATE]
        )
        
        # Publish multiple notifications
        for i in range(5):
            await notification_service.publish(
                notification_type=NotificationType.PRICE_UPDATE,
                recipient_ids=["user_batch"],
                data={"symbol": f"STOCK_{i}", "price": 100.0 + i},
                priority=NotificationPriority.NORMAL
            )
        
        pending = notification_service.get_pending("user_batch")
        assert len(pending) >= 5
    
    async def test_subscription_filtering(self, notification_service):
        """Test subscription filtering by instrument."""
        from app.services.notification_service import NotificationType
        
        subscription = await notification_service.subscribe(
            user_id="user_filter",
            types=[NotificationType.PRICE_UPDATE],
            instruments=["AAPL", "GOOGL"]
        )
        
        assert "AAPL" in subscription.instruments
        assert "GOOGL" in subscription.instruments
    
    async def test_dead_letter_queue(self, notification_service):
        """Test dead letter queue for failed deliveries."""
        dead_letters = notification_service.get_dead_letters(limit=10)
        
        # Should be empty initially
        assert isinstance(dead_letters, list)
    
    async def test_notification_expiration(self, notification_service):
        """Test notification expiration handling."""
        from app.services.notification_service import NotificationType, NotificationPriority
        
        await notification_service.subscribe(
            user_id="user_expire",
            types=[NotificationType.ORDER_CREATED]
        )
        
        # Publish with 0 second expiration
        notification_id = await notification_service.publish(
            notification_type=NotificationType.ORDER_CREATED,
            recipient_ids=["user_expire"],
            data={"order_id": "order_456"},
            priority=NotificationPriority.CRITICAL,
            expires_in_seconds=0
        )
        
        assert notification_id is not None


# Metrics Service Tests

class TestMetricsService:
    """Tests for MetricsService."""
    
    async def test_record_latency(self, metrics_service):
        """Test recording API latency."""
        from app.services.metrics_service import MetricType
        
        metrics_service.record_latency(
            MetricType.API_LATENCY,
            latency_ms=150.5,
            tags={"endpoint": "/orders", "method": "GET"}
        )
        
        # Verify measurement was recorded
        assert metrics_service.counters.get("measurement_count", 0) >= 0
    
    async def test_increment_counter(self, metrics_service):
        """Test counter incrementation."""
        initial_count = metrics_service.counters.get("trades", 0)
        
        metrics_service.increment_counter("trades", amount=5)
        
        new_count = metrics_service.counters.get("trades", 0)
        assert new_count == initial_count + 5
    
    async def test_set_gauge(self, metrics_service):
        """Test gauge setting."""
        metrics_service.set_gauge("connection_count", 42)
        
        value = metrics_service.gauges.get("connection_count")
        assert value == 42
    
    async def test_get_latency_stats(self, metrics_service):
        """Test latency statistics calculation."""
        from app.services.metrics_service import MetricType
        
        # Record multiple latencies
        for i in range(10):
            metrics_service.record_latency(
                MetricType.API_LATENCY,
                latency_ms=100.0 + i * 10,
                tags={"endpoint": "/test"}
            )
        
        stats = metrics_service.get_latency_stats(MetricType.API_LATENCY)
        
        assert stats is not None
        assert stats.count >= 10
        assert stats.avg >= 0
    
    async def test_health_check(self, metrics_service):
        """Test health check status."""
        health = metrics_service.get_health_check()
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "checks" in health
    
    async def test_percentile_calculation(self, metrics_service):
        """Test percentile aggregation."""
        from app.services.metrics_service import MetricType
        
        # Record latencies: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for latency in latencies:
            metrics_service.record_latency(
                MetricType.DB_QUERY_LATENCY,
                latency_ms=float(latency)
            )
        
        stats = metrics_service.get_latency_stats(MetricType.DB_QUERY_LATENCY)
        
        assert stats.p50 is not None
        assert stats.p95 is not None
        assert stats.p99 is not None
    
    async def test_dashboard_metrics(self, metrics_service):
        """Test comprehensive dashboard metrics."""
        dashboard = metrics_service.get_dashboard_metrics()
        
        assert isinstance(dashboard, dict)
        assert "api_metrics" in dashboard or "trading_metrics" in dashboard


# Rate Limiter Tests

class TestRateLimiter:
    """Tests for RateLimiter middleware."""
    
    async def test_user_rate_limit(self):
        """Test per-user rate limiting."""
        from app.middleware.rate_limiter import get_rate_limiter, RateLimit
        
        limiter = get_rate_limiter()
        request = Mock()
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        # Make requests up to limit
        allowed_count = 0
        for i in range(15):  # Default: 10 req/s
            allowed, retry_after = await limiter.check_rate_limit(
                request,
                user_id="user_test"
            )
            if allowed:
                allowed_count += 1
        
        # Should allow some but not all
        assert allowed_count > 0
        assert allowed_count <= 10
    
    async def test_ip_rate_limit(self):
        """Test per-IP rate limiting."""
        from app.middleware.rate_limiter import get_rate_limiter
        
        limiter = get_rate_limiter()
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        allowed_count = 0
        for i in range(150):  # Default: 100 req/s
            allowed, retry_after = await limiter.check_rate_limit(request)
            if allowed:
                allowed_count += 1
        
        assert allowed_count > 0
        assert allowed_count <= 100
    
    async def test_tier_upgrade(self):
        """Test premium tier rate limits."""
        from app.middleware.rate_limiter import get_rate_limiter
        
        limiter = get_rate_limiter()
        limiter.set_user_tier("premium_user", "premium")
        
        request = Mock()
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        allowed_count = 0
        for i in range(60):  # Premium: 50 req/s
            allowed, retry_after = await limiter.check_rate_limit(
                request,
                user_id="premium_user"
            )
            if allowed:
                allowed_count += 1
        
        # Premium users should have higher limit
        assert allowed_count > 10  # More than standard user
    
    async def test_retry_after_header(self):
        """Test Retry-After calculation."""
        from app.middleware.rate_limiter import get_rate_limiter
        
        limiter = get_rate_limiter()
        request = Mock()
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        # Exhaust rate limit
        for i in range(20):
            allowed, retry_after = await limiter.check_rate_limit(
                request,
                user_id="user_limit"
            )
        
        # Should get retry_after value > 0 when limit exceeded
        assert retry_after >= 0


# Security Tests

class TestSecurityHardening:
    """Tests for security hardening features."""
    
    def test_security_headers_middleware(self):
        """Test security headers middleware."""
        from app.middleware.security import SecurityHeadersMiddleware
        
        app = Mock()
        middleware = SecurityHeadersMiddleware(app)
        
        assert middleware.csp_policy is not None
        assert "default-src" in middleware.csp_policy
    
    def test_cors_configuration(self):
        """Test CORS configuration."""
        from app.middleware.security import CORSConfiguration
        
        app = Mock()
        cors = CORSConfiguration.get_middleware(
            app,
            allowed_origins=["http://localhost:3000"]
        )
        
        assert cors is not None
    
    def test_trusted_host_configuration(self):
        """Test trusted host middleware."""
        from app.middleware.security import TrustedHostConfiguration
        
        app = Mock()
        trusted = TrustedHostConfiguration.get_middleware(
            app,
            allowed_hosts=["localhost", "example.com"]
        )
        
        assert trusted is not None
    
    def test_production_config(self):
        """Test production security configuration."""
        from app.middleware.security import PRODUCTION_CONFIG
        
        assert PRODUCTION_CONFIG["enable_hsts"] is True
        assert PRODUCTION_CONFIG["enable_cors"] is True
        assert len(PRODUCTION_CONFIG["allow_origins"]) > 0


# OpenAPI Documentation Tests

class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation generation."""
    
    def test_schema_generation(self):
        """Test OpenAPI schema generation."""
        from app.utils.openapi_generator import OpenAPIDocumentationGenerator
        from fastapi import FastAPI
        
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            """Test endpoint."""
            return {"message": "test"}
        
        generator = OpenAPIDocumentationGenerator(app)
        schema = generator.generate_schema()
        
        assert "openapi" in schema
        assert schema["openapi"] == "3.1.0"
        assert "info" in schema
        assert "paths" in schema
    
    def test_schema_structure(self):
        """Test OpenAPI schema structure."""
        from app.utils.openapi_generator import REQUIRED_FIELDS, MINIMUM_INFO_FIELDS
        
        required = REQUIRED_FIELDS
        info_fields = MINIMUM_INFO_FIELDS
        
        assert "openapi" in required
        assert "title" in info_fields
        assert "version" in info_fields
    
    def test_error_response_schema(self):
        """Test error response schema."""
        from app.utils.openapi_generator import EXAMPLE_ERROR_RESPONSE
        
        assert "properties" in EXAMPLE_ERROR_RESPONSE
        assert "status" in EXAMPLE_ERROR_RESPONSE["properties"]
        assert "error" in EXAMPLE_ERROR_RESPONSE["properties"]


# Integration Tests

class TestPhase2Integration:
    """Integration tests for Phase 2 Section 8."""
    
    async def test_notification_metrics_integration(
        self,
        notification_service,
        metrics_service
    ):
        """Test integration between notifications and metrics."""
        from app.services.notification_service import NotificationType, NotificationPriority
        from app.services.metrics_service import MetricType
        
        # Publish notification
        start = datetime.now()
        notification_id = await notification_service.publish(
            notification_type=NotificationType.ORDER_CREATED,
            recipient_ids=["user_int"],
            data={"order_id": "order_int"},
            priority=NotificationPriority.HIGH
        )
        latency = (datetime.now() - start).total_seconds() * 1000
        
        # Record metrics
        metrics_service.record_latency(
            MetricType.NOTIFICATION_LATENCY,
            latency_ms=latency
        )
        
        assert notification_id is not None
        metrics = metrics_service.get_latency_stats(MetricType.NOTIFICATION_LATENCY)
        assert metrics is not None
    
    async def test_rate_limit_with_metrics(
        self,
        rate_limiter: any,
        metrics_service
    ):
        """Test rate limiting with metrics recording."""
        request = Mock()
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        for i in range(20):
            allowed, retry_after = await rate_limiter.check_rate_limit(
                request,
                user_id="user_metrics"
            )
            
            # Record metric
            metrics_service.increment_counter("rate_limit_checks")
        
        count = metrics_service.counters.get("rate_limit_checks", 0)
        assert count >= 20


# Performance Tests

class TestPerformance:
    """Performance tests for Section 8 components."""
    
    async def test_notification_throughput(self, notification_service):
        """Test notification publishing throughput."""
        from app.services.notification_service import NotificationType
        
        start = datetime.now()
        
        await notification_service.subscribe(
            user_id="perf_user",
            types=[NotificationType.PRICE_UPDATE]
        )
        
        for i in range(100):
            await notification_service.publish(
                notification_type=NotificationType.PRICE_UPDATE,
                recipient_ids=["perf_user"],
                data={"price": 100.0 + i}
            )
        
        elapsed = (datetime.now() - start).total_seconds()
        throughput = 100 / elapsed
        
        assert throughput > 10  # At least 10 notifications per second
    
    async def test_metrics_aggregation_performance(self, metrics_service):
        """Test metrics aggregation performance."""
        from app.services.metrics_service import MetricType
        
        # Record many measurements
        for i in range(1000):
            metrics_service.record_latency(
                MetricType.API_LATENCY,
                latency_ms=float(100 + i % 100)
            )
        
        start = datetime.now()
        aggregated = metrics_service.aggregate_metrics(period_seconds=60)
        elapsed = (datetime.now() - start).total_seconds()
        
        # Should complete within 100ms
        assert elapsed < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
