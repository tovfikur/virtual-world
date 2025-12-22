"""
Monitoring and metrics API endpoints.
Provides real-time performance metrics, system health, and analytics dashboards.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.account import Account
from app.services.metrics_service import (
    get_metrics_service,
    MetricType
)
from app.services.notification_service import get_notification_service

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/health", summary="System health check")
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    Get system health status.
    
    Returns:
    - status: healthy/degraded/unhealthy
    - checks: Per-component health status
    - timestamp: Health check time
    """
    metrics_service = get_metrics_service()
    health = metrics_service.get_health_check()
    
    return health


@router.get("/metrics/api", summary="API performance metrics")
async def get_api_metrics(
    period_seconds: int = Query(60, ge=10, le=3600),
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get API request latency metrics.
    
    Returns:
    - count: Number of requests in period
    - min/max/avg: Latency statistics (ms)
    - p50/p95/p99: Percentile latencies
    - stddev: Standard deviation
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    stats = metrics_service.get_latency_stats(
        MetricType.API_REQUEST_LATENCY,
        period_seconds
    )
    
    if not stats:
        return {
            "message": "No metrics available",
            "period_seconds": period_seconds
        }
    
    return {
        "metric": "api.request_latency",
        "period_seconds": period_seconds,
        "count": stats.count,
        "sum_ms": round(stats.sum, 2),
        "min_ms": round(stats.min, 2),
        "max_ms": round(stats.max, 2),
        "avg_ms": round(stats.avg, 2),
        "median_ms": round(stats.p50, 2),
        "p95_ms": round(stats.p95, 2),
        "p99_ms": round(stats.p99, 2),
        "stddev_ms": round(stats.stddev, 2),
        "last_updated": stats.last_updated.isoformat()
    }


@router.get("/metrics/trading", summary="Trading performance metrics")
async def get_trading_metrics(
    period_seconds: int = Query(60, ge=10, le=3600),
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trading system performance metrics.
    
    Returns:
    - order_match_latency: Time to match orders (ms)
    - fill_rate: Percentage of orders filled
    - trade_throughput: Trades per second
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    
    match_latency = metrics_service.get_latency_stats(
        MetricType.ORDER_MATCH_LATENCY,
        period_seconds
    )
    
    fill_rate = metrics_service.get_counter("orders_filled") / max(
        metrics_service.get_counter("orders_created"), 1
    ) * 100
    
    trade_throughput = metrics_service.get_counter("trades_executed") / period_seconds
    
    return {
        "period_seconds": period_seconds,
        "order_match_latency": {
            "count": match_latency.count if match_latency else 0,
            "avg_ms": round(match_latency.avg, 2) if match_latency else 0,
            "p99_ms": round(match_latency.p99, 2) if match_latency else 0
        },
        "fill_rate_percent": round(fill_rate, 2),
        "trade_throughput_per_sec": round(trade_throughput, 2),
        "total_trades": metrics_service.get_counter("trades_executed"),
        "last_updated": datetime.utcnow().isoformat()
    }


@router.get("/metrics/websocket", summary="WebSocket metrics")
async def get_websocket_metrics(
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get WebSocket connection and message metrics.
    
    Returns:
    - active_connections: Number of active WebSocket connections
    - message_latency: Message delivery latency statistics
    - broadcast_count: Number of broadcasts
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    
    message_latency = metrics_service.get_latency_stats(
        MetricType.WS_MESSAGE_LATENCY,
        60
    )
    
    return {
        "active_connections": int(metrics_service.get_gauge("ws_connections")),
        "message_latency_ms": {
            "avg": round(message_latency.avg, 2) if message_latency else 0,
            "p95": round(message_latency.p95, 2) if message_latency else 0,
            "p99": round(message_latency.p99, 2) if message_latency else 0
        },
        "total_broadcasts": metrics_service.get_counter("ws_broadcasts"),
        "total_messages": metrics_service.get_counter("ws_messages_sent"),
        "last_updated": datetime.utcnow().isoformat()
    }


@router.get("/metrics/database", summary="Database metrics")
async def get_database_metrics(
    period_seconds: int = Query(60, ge=10, le=3600),
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get database query performance metrics.
    
    Returns:
    - query_latency: Database query latency statistics
    - connection_pool_size: Current connection pool usage
    - slow_queries: Queries taking >500ms
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    
    query_latency = metrics_service.get_latency_stats(
        MetricType.DB_QUERY_LATENCY,
        period_seconds
    )
    
    return {
        "period_seconds": period_seconds,
        "query_latency_ms": {
            "count": query_latency.count if query_latency else 0,
            "avg": round(query_latency.avg, 2) if query_latency else 0,
            "min": round(query_latency.min, 2) if query_latency else 0,
            "max": round(query_latency.max, 2) if query_latency else 0,
            "p95": round(query_latency.p95, 2) if query_latency else 0,
            "p99": round(query_latency.p99, 2) if query_latency else 0
        },
        "connection_pool_status": {
            "active_connections": metrics_service.get_gauge("db_connections_active"),
            "pool_size": metrics_service.get_gauge("db_pool_size")
        },
        "slow_queries": metrics_service.get_counter("db_slow_queries"),
        "last_updated": datetime.utcnow().isoformat()
    }


@router.get("/dashboard", summary="Comprehensive metrics dashboard")
async def get_dashboard(
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive dashboard with all metrics.
    
    Returns aggregated metrics for:
    - API performance
    - Trading system
    - WebSocket activity
    - Database performance
    - Business metrics
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    dashboard = metrics_service.get_dashboard_metrics()
    
    return dashboard


@router.get("/notifications/stats", summary="Notification service stats")
async def get_notification_stats(
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notification service statistics.
    
    Returns:
    - active_subscriptions: Number of active subscriptions
    - pending_notifications: Queue size
    - delivery_success_rate: Percentage of successful deliveries
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    notification_service = get_notification_service()
    stats = notification_service.get_stats()
    
    return {
        "subscriptions": stats["subscriptions"],
        "total_subscribers": stats["subscribers"],
        "pending_notifications": stats["pending_notifications"],
        "dead_letter_queue_size": stats["dead_letter_queue_size"],
        "active_delivery_callbacks": stats["active_delivery_callbacks"],
        "active_batch_tasks": stats["active_batch_tasks"],
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/system/status", summary="Overall system status")
async def get_system_status(
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall system status and key metrics.
    
    Returns:
    - status: System health status
    - uptime: Time since last restart
    - key_metrics: Most important metrics
    - alerts: Any active alerts
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    notification_service = get_notification_service()
    
    api_latency = metrics_service.get_latency_stats(MetricType.API_REQUEST_LATENCY)
    order_latency = metrics_service.get_latency_stats(MetricType.ORDER_MATCH_LATENCY)
    health = metrics_service.get_health_check()
    
    return {
        "status": health["status"],
        "timestamp": datetime.utcnow().isoformat(),
        "key_metrics": {
            "api_latency_p95_ms": round(api_latency.p95, 2) if api_latency else 0,
            "order_matching_p99_ms": round(order_latency.p99, 2) if order_latency else 0,
            "active_ws_connections": int(metrics_service.get_gauge("ws_connections")),
            "active_orders": int(metrics_service.get_gauge("pending_orders")),
            "total_trades_today": metrics_service.get_counter("trades_executed")
        },
        "notification_queue": {
            "pending": notification_service.get_stats()["pending_notifications"],
            "dead_letters": notification_service.get_stats()["dead_letter_queue_size"]
        },
        "health_checks": health["checks"]
    }


@router.post("/metrics/reset", summary="Reset metrics counters")
async def reset_metrics(
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset all metric counters. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    count = metrics_service.reset_counters()
    
    return {
        "status": "reset",
        "counters_reset": count,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/cleanup", summary="Cleanup old metrics")
async def cleanup_metrics(
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove old measurements outside retention window."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_service = get_metrics_service()
    removed = metrics_service.cleanup_old_measurements()
    
    return {
        "status": "cleanup_complete",
        "measurements_removed": removed,
        "timestamp": datetime.utcnow().isoformat()
    }
