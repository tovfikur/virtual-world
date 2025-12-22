"""
Metrics service for collecting and aggregating performance metrics.
Tracks API latency, order matching performance, throughput, and system health.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time
import logging
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics."""
    # API metrics
    API_REQUEST_LATENCY = "api.request.latency"
    API_ERROR_RATE = "api.error_rate"
    API_THROUGHPUT = "api.throughput"
    
    # Trading metrics
    ORDER_MATCH_LATENCY = "order.match_latency"
    ORDER_FILL_RATE = "order.fill_rate"
    TRADE_THROUGHPUT = "trade.throughput"
    
    # WebSocket metrics
    WS_CONNECTION_COUNT = "ws.connection_count"
    WS_MESSAGE_LATENCY = "ws.message_latency"
    WS_BROADCAST_COUNT = "ws.broadcast_count"
    
    # Database metrics
    DB_QUERY_LATENCY = "db.query_latency"
    DB_CONNECTION_POOL = "db.connection_pool"
    
    # Business metrics
    TOTAL_TRADES = "total.trades"
    TOTAL_FEES = "total.fees"
    ACTIVE_ACCOUNTS = "active.accounts"
    ACTIVE_ORDERS = "active.orders"


@dataclass
class Measurement:
    """Single metric measurement."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __hash__(self):
        return id(self)


@dataclass
class MetricAggregate:
    """Aggregated metric statistics."""
    metric_type: MetricType
    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float  # Median
    p95: float  # 95th percentile
    p99: float  # 99th percentile
    stddev: float
    last_updated: datetime
    period_seconds: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_type": self.metric_type.value,
            "count": self.count,
            "sum": round(self.sum, 2),
            "min": round(self.min, 2),
            "max": round(self.max, 2),
            "avg": round(self.avg, 2),
            "p50": round(self.p50, 2),
            "p95": round(self.p95, 2),
            "p99": round(self.p99, 2),
            "stddev": round(self.stddev, 2),
            "last_updated": self.last_updated.isoformat(),
            "period_seconds": self.period_seconds
        }


class MetricsService:
    """
    Service for collecting and aggregating metrics.
    
    Features:
    - Low-overhead metric collection
    - Per-endpoint tracking
    - Percentile calculations
    - Time-windowed aggregation
    - Dead letter tracking
    """
    
    def __init__(self, retention_seconds: int = 3600):
        """
        Initialize metrics service.
        
        Args:
            retention_seconds: How long to keep raw measurements
        """
        self.retention_seconds = retention_seconds
        
        # Raw measurements: {metric_type: deque}
        self.measurements: Dict[MetricType, deque] = defaultdict(
            lambda: deque(maxlen=10000)  # Keep last 10k measurements
        )
        
        # Counters for instant stats
        self.counters: Dict[str, int] = defaultdict(int)
        
        # Gauges for current values
        self.gauges: Dict[str, float] = defaultdict(float)
        
        # Cached aggregates: {metric_type: MetricAggregate}
        self.aggregates: Dict[MetricType, MetricAggregate] = {}
        self.aggregate_timestamp = datetime.utcnow()
        
        logger.info("MetricsService initialized")
    
    def record_latency(
        self,
        metric_type: MetricType,
        latency_ms: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a latency measurement.
        
        Args:
            metric_type: Type of metric
            latency_ms: Latency in milliseconds
            tags: Optional tags for filtering
        """
        measurement = Measurement(
            timestamp=datetime.utcnow(),
            value=latency_ms,
            tags=tags or {}
        )
        self.measurements[metric_type].append(measurement)
    
    def increment_counter(self, counter_name: str, amount: int = 1) -> None:
        """Increment a counter."""
        self.counters[counter_name] += amount
    
    def set_gauge(self, gauge_name: str, value: float) -> None:
        """Set a gauge value."""
        self.gauges[gauge_name] = value
    
    def get_counter(self, counter_name: str) -> int:
        """Get counter value."""
        return self.counters.get(counter_name, 0)
    
    def get_gauge(self, gauge_name: str) -> float:
        """Get gauge value."""
        return self.gauges.get(gauge_name, 0.0)
    
    async def aggregate_metrics(self, period_seconds: int = 60) -> Dict[MetricType, MetricAggregate]:
        """
        Aggregate metrics for a time period.
        
        Args:
            period_seconds: Aggregation period in seconds
        
        Returns:
            Dictionary of aggregates by metric type
        """
        aggregates = {}
        cutoff = datetime.utcnow() - timedelta(seconds=period_seconds)
        
        for metric_type, measurements in self.measurements.items():
            # Filter to period
            recent = [
                m for m in measurements
                if m.timestamp >= cutoff
            ]
            
            if not recent:
                continue
            
            # Extract values
            values = [m.value for m in recent]
            
            # Calculate statistics
            aggregate = MetricAggregate(
                metric_type=metric_type,
                count=len(values),
                sum=sum(values),
                min=min(values),
                max=max(values),
                avg=statistics.mean(values),
                p50=self._percentile(values, 50),
                p95=self._percentile(values, 95),
                p99=self._percentile(values, 99),
                stddev=statistics.stdev(values) if len(values) > 1 else 0.0,
                last_updated=datetime.utcnow(),
                period_seconds=period_seconds
            )
            
            aggregates[metric_type] = aggregate
            self.aggregates[metric_type] = aggregate
        
        self.aggregate_timestamp = datetime.utcnow()
        
        return aggregates
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def get_latency_stats(
        self,
        metric_type: MetricType,
        period_seconds: int = 60
    ) -> Optional[MetricAggregate]:
        """
        Get latency statistics for a metric.
        
        Args:
            metric_type: Type of metric
            period_seconds: Aggregation period
        
        Returns:
            MetricAggregate or None if no data
        """
        # Check if cached aggregate is fresh
        if metric_type in self.aggregates:
            age = (datetime.utcnow() - self.aggregate_timestamp).total_seconds()
            if age < 10:  # Cache for 10 seconds
                return self.aggregates[metric_type]
        
        # Calculate fresh aggregate
        cutoff = datetime.utcnow() - timedelta(seconds=period_seconds)
        measurements = self.measurements.get(metric_type, [])
        
        recent = [
            m for m in measurements
            if m.timestamp >= cutoff
        ]
        
        if not recent:
            return None
        
        values = [m.value for m in recent]
        
        return MetricAggregate(
            metric_type=metric_type,
            count=len(values),
            sum=sum(values),
            min=min(values),
            max=max(values),
            avg=statistics.mean(values),
            p50=self._percentile(values, 50),
            p95=self._percentile(values, 95),
            p99=self._percentile(values, 99),
            stddev=statistics.stdev(values) if len(values) > 1 else 0.0,
            last_updated=datetime.utcnow(),
            period_seconds=period_seconds
        )
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get comprehensive dashboard metrics."""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "api_metrics": {},
            "trading_metrics": {},
            "websocket_metrics": {},
            "database_metrics": {},
            "business_metrics": {},
            "counters": dict(self.counters),
            "gauges": dict(self.gauges)
        }
        
        # Collect latency statistics
        latency_metrics = [
            (MetricType.API_REQUEST_LATENCY, "api_metrics"),
            (MetricType.ORDER_MATCH_LATENCY, "trading_metrics"),
            (MetricType.WS_MESSAGE_LATENCY, "websocket_metrics"),
            (MetricType.DB_QUERY_LATENCY, "database_metrics")
        ]
        
        for metric_type, section in latency_metrics:
            stats = self.get_latency_stats(metric_type)
            if stats:
                metrics[section][metric_type.value] = stats.to_dict()
        
        # Add other aggregates
        for metric_type, aggregate in self.aggregates.items():
            if metric_type in [m[0] for m in latency_metrics]:
                continue  # Already added
            
            section = self._get_metric_section(metric_type)
            metrics[section][metric_type.value] = aggregate.to_dict()
        
        return metrics
    
    def _get_metric_section(self, metric_type: MetricType) -> str:
        """Get section name for metric type."""
        if "api" in metric_type.value:
            return "api_metrics"
        elif "order" in metric_type.value or "trade" in metric_type.value:
            return "trading_metrics"
        elif "ws" in metric_type.value:
            return "websocket_metrics"
        elif "db" in metric_type.value:
            return "database_metrics"
        else:
            return "business_metrics"
    
    def get_health_check(self) -> Dict[str, Any]:
        """Get system health metrics."""
        api_latency = self.get_latency_stats(MetricType.API_REQUEST_LATENCY)
        order_latency = self.get_latency_stats(MetricType.ORDER_MATCH_LATENCY)
        db_latency = self.get_latency_stats(MetricType.DB_QUERY_LATENCY)
        
        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        # Check API latency
        if api_latency and api_latency.p95 > 1000:  # >1 second
            health["status"] = "degraded"
            health["checks"]["api_latency"] = f"High: {api_latency.p95:.0f}ms (p95)"
        else:
            health["checks"]["api_latency"] = "OK"
        
        # Check order matching
        if order_latency and order_latency.p99 > 100:  # >100ms
            health["status"] = "degraded"
            health["checks"]["order_matching"] = f"Slow: {order_latency.p99:.0f}ms (p99)"
        else:
            health["checks"]["order_matching"] = "OK"
        
        # Check database
        if db_latency and db_latency.p95 > 500:  # >500ms
            health["status"] = "degraded"
            health["checks"]["database"] = f"Slow: {db_latency.p95:.0f}ms (p95)"
        else:
            health["checks"]["database"] = "OK"
        
        # Check connection counts
        ws_connections = self.get_gauge("ws_connections")
        health["checks"]["websocket_connections"] = f"{int(ws_connections)} active"
        
        # Check queue sizes
        pending_orders = self.get_gauge("pending_orders")
        if pending_orders > 10000:
            health["status"] = "degraded"
            health["checks"]["pending_orders"] = f"High: {int(pending_orders)}"
        else:
            health["checks"]["pending_orders"] = f"{int(pending_orders)}"
        
        return health
    
    def reset_counters(self) -> int:
        """Reset all counters."""
        count = len(self.counters)
        self.counters.clear()
        return count
    
    def cleanup_old_measurements(self) -> int:
        """Remove measurements older than retention period."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.retention_seconds)
        removed = 0
        
        for metric_type in self.measurements:
            while self.measurements[metric_type]:
                if self.measurements[metric_type][0].timestamp < cutoff:
                    self.measurements[metric_type].popleft()
                    removed += 1
                else:
                    break
        
        return removed


# Global metrics service instance
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """Get or create metrics service."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service
