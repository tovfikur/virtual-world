"""
Admin Endpoints
Dashboard, user management, system monitoring, and configuration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, text
from typing import List, Optional
from datetime import datetime, timedelta
import time
import os
import re
import ipaddress
import logging
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url

from app.db.session import get_db, engine
from app.dependencies import get_current_user
from app.models.user import User
from app.models.land import Land
from app.models.listing import Listing
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.chat import ChatSession
from app.models.chat import Message
from app.models.audit_log import AuditLog, AuditEventCategory
from app.models.admin_config import AdminConfig
from app.models.ban import Ban
from app.models.announcement import Announcement
from app.models.report import Report
from app.services.cache_service import cache_service
from app.services.websocket_service import connection_manager
from app.models.ip_access_control import IPBlacklist, IPWhitelist
from app.services.ip_access_service import ip_access_service
from app.models.payment_event import PaymentEvent
from app.config import settings, CACHE_TTLS
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def create_audit_log(
    actor_id: str,
    event_type: str,
    resource_type: str,
    resource_id: str = None,
    action: str = None,
    details: dict = None
) -> AuditLog:
    """Helper to create audit logs with correct field structure"""
    return AuditLog(
        actor_id=actor_id,
        event_type=event_type,
        event_category=AuditEventCategory.ADMIN,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        action=action,
        details=details
    )


BASE_DIR = Path(__file__).resolve().parents[4]


def _run_alembic(args: list[str]) -> tuple[bool, str, str]:
    """Run alembic command synchronously and capture output."""
    cmd = ["alembic", "-c", str(BASE_DIR / "alembic.ini"), *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def _get_db_dump_params() -> dict:
    url = make_url(settings.database_url)
    return {
        "host": url.host or "localhost",
        "port": str(url.port or 5432),
        "user": url.username,
        "password": url.password,
        "database": url.database,
    }


def _run_pg_command(cmd: list[str], password: Optional[str]) -> tuple[bool, str, str]:
    env = None
    if password:
        env = os.environ.copy()
        env["PGPASSWORD"] = password
    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            check=False,
            env=env
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def normalize_ip_address(ip: str) -> str:
    """Normalize and validate an IP address string."""
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid IP address"
        )


def validate_gateway_mode(mode: str) -> str:
    if mode not in {"test", "live"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gateway mode must be 'test' or 'live'"
        )
    return mode


def _validate_biome_distribution(dist: dict) -> dict:
    required = {"forest", "grassland", "water", "desert", "snow"}
    missing = required - dist.keys()
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing biome keys: {', '.join(sorted(missing))}")

    for name, value in dist.items():
        if value < 0 or value > 1:
            raise HTTPException(status_code=400, detail=f"Biome percent for {name} must be between 0 and 1")

    total = sum(dist.values())
    if abs(total - 1.0) > 1e-6:
        raise HTTPException(status_code=400, detail="Biome distribution must sum to 1.0")

    return dist


def _gini(values: list[int]) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = 0
    weighted_sum = 0
    for i, val in enumerate(sorted_vals, start=1):
        cumulative += val
        weighted_sum += i * val
    if cumulative == 0:
        return 0.0
    return (2 * weighted_sum) / (n * cumulative) - (n + 1) / n


def _get_pool_stats() -> dict:
    pool = engine.sync_engine.pool
    stats = {}

    for attr in ("size", "checkedin", "checkedout", "overflow", "timeout"):
        if hasattr(pool, attr):
            try:
                stats[attr] = getattr(pool, attr)()
            except Exception:
                stats[attr] = "unknown"

    status_fn = getattr(pool, "status", None)
    stats["status"] = status_fn() if status_fn else "unknown"
    return stats


# ============================================
# Schemas
# ============================================

class DashboardStats(BaseModel):
    total_users: int
    active_users_today: int
    total_lands: int
    owned_lands: int
    total_listings: int
    active_listings: int
    total_transactions: int
    transactions_today: int
    total_revenue_bdt: int
    active_chat_sessions: int
    total_messages: int


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    balance_bdt: Optional[int] = None
    is_active: Optional[bool] = None


# ============================================
# Admin Dependency
# ============================================

async def require_admin(current_user: dict = Depends(get_current_user)):
    """Require admin role"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ============================================
# Dashboard & Analytics
# ============================================

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """
    Get dashboard statistics

    Returns overview of platform metrics
    """
    try:
        # Check cache first
        cache_key = "admin:dashboard:stats"
        cached = await cache_service.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        # Total users
        total_users = await db.scalar(select(func.count(User.user_id)))

        # Active users today (logged in last 24h)
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users_today = await db.scalar(
            select(func.count(User.user_id)).where(User.last_login >= yesterday)
        )

        # Total lands
        total_lands = await db.scalar(select(func.count(Land.land_id)))

        # Owned lands (not None owner)
        owned_lands = await db.scalar(
            select(func.count(Land.land_id)).where(Land.owner_id.isnot(None))
        )

        # Total listings
        total_listings = await db.scalar(select(func.count(Listing.listing_id)))

        # Active listings
        active_listings = await db.scalar(
            select(func.count(Listing.listing_id)).where(Listing.status == "active")
        )

        # Total transactions
        total_transactions = await db.scalar(select(func.count(Transaction.transaction_id)))

        # Transactions today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        transactions_today = await db.scalar(
            select(func.count(Transaction.transaction_id)).where(
                Transaction.created_at >= today_start
            )
        )

        # Total revenue
        total_revenue = await db.scalar(
            select(func.sum(Transaction.amount_bdt)).where(
                Transaction.status == "COMPLETED"
            )
        ) or 0

        # Active chat sessions (count sessions with recent messages)
        active_chat_sessions = await db.scalar(
            select(func.count(ChatSession.session_id))
        )

        # Total messages
        total_messages = await db.scalar(select(func.count(Message.message_id)))

        stats = DashboardStats(
            total_users=total_users or 0,
            active_users_today=active_users_today or 0,
            total_lands=total_lands or 0,
            owned_lands=owned_lands or 0,
            total_listings=total_listings or 0,
            active_listings=active_listings or 0,
            total_transactions=total_transactions or 0,
            transactions_today=transactions_today or 0,
            total_revenue_bdt=int(total_revenue),
            active_chat_sessions=active_chat_sessions or 0,
            total_messages=total_messages or 0
        )

        # Cache for 5 minutes
        import json
        await cache_service.set(cache_key, json.dumps(stats.dict()), ttl=300)

        return stats

    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard statistics"
        )


@router.get("/analytics/revenue")
async def get_revenue_analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get revenue analytics over time"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Daily revenue
        result = await db.execute(
            select(
                func.date(Transaction.created_at).label('date'),
                func.sum(Transaction.amount_bdt).label('revenue'),
                func.count(Transaction.transaction_id).label('count')
            )
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.status == "COMPLETED"
                )
            )
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )

        daily_data = [
            {
                "date": str(row.date),
                "revenue": int(row.revenue or 0),
                "transaction_count": row.count
            }
            for row in result.all()
        ]

        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "daily_data": daily_data,
            "total_revenue": sum(d["revenue"] for d in daily_data),
            "total_transactions": sum(d["transaction_count"] for d in daily_data)
        }

    except Exception as e:
        logger.error(f"Error getting revenue analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch revenue analytics"
        )


@router.get("/analytics/users")
async def get_user_analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get user growth analytics"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Daily user registrations
        result = await db.execute(
            select(
                func.date(User.created_at).label('date'),
                func.count(User.user_id).label('new_users')
            )
            .where(User.created_at >= start_date)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )

        daily_data = [
            {
                "date": str(row.date),
                "new_users": row.new_users
            }
            for row in result.all()
        ]

        return {
            "period_days": days,
            "daily_data": daily_data,
            "total_new_users": sum(d["new_users"] for d in daily_data)
        }

    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user analytics"
        )


@router.get("/analytics/economy/wealth")
async def get_wealth_distribution(
    top: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Wealth distribution metrics (Gini, top balances)."""
    balances_result = await db.execute(select(User.user_id, User.balance_bdt))
    rows = balances_result.all()
    balances = [row.balance_bdt or 0 for row in rows]

    gini = _gini(balances)
    total_balance = sum(balances)
    avg_balance = (total_balance / len(balances)) if balances else 0
    median_balance = None
    if balances:
        sorted_vals = sorted(balances)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2:
            median_balance = sorted_vals[mid]
        else:
            median_balance = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2

    top_rows = await db.execute(
        select(User.user_id, User.balance_bdt)
        .order_by(User.balance_bdt.desc())
        .limit(top)
    )
    top_accounts = [
        {"user_id": str(row.user_id), "balance_bdt": row.balance_bdt}
        for row in top_rows.all()
    ]

    return {
        "gini": gini,
        "total_balance_bdt": total_balance,
        "average_balance_bdt": avg_balance,
        "median_balance_bdt": median_balance,
        "top_accounts": top_accounts,
    }


@router.get("/analytics/market/trends")
async def get_market_trends(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Market trends: listing price stats and transaction averages."""
    start = datetime.utcnow() - timedelta(days=days)

    listing_stats = await db.execute(
        select(func.avg(Listing.price_bdt), func.count(Listing.listing_id))
        .where(Listing.created_at >= start)
    )
    avg_listing_price, listings_created = listing_stats.first()

    txn_stats = await db.execute(
        select(func.avg(Transaction.amount_bdt), func.count(Transaction.transaction_id))
        .where(Transaction.status == "COMPLETED", Transaction.created_at >= start)
    )
    avg_txn_amount, txn_count = txn_stats.first()

    return {
        "window_days": days,
        "listings_created": listings_created or 0,
        "avg_listing_price_bdt": float(avg_listing_price) if avg_listing_price else None,
        "transactions_completed": txn_count or 0,
        "avg_transaction_amount_bdt": float(avg_txn_amount) if avg_txn_amount else None,
    }


@router.get("/analytics/users/retention")
async def get_user_retention(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """User retention/churn snapshot based on last login."""
    now = datetime.utcnow()
    window_start = now - timedelta(days=days)

    active_7d = await db.scalar(select(func.count(User.user_id)).where(User.last_login >= now - timedelta(days=7))) or 0
    active_30d = await db.scalar(select(func.count(User.user_id)).where(User.last_login >= now - timedelta(days=30))) or 0
    inactive_30d = await db.scalar(
        select(func.count(User.user_id)).where(
            or_(User.last_login.is_(None), User.last_login < now - timedelta(days=30))
        )
    ) or 0
    new_users_window = await db.scalar(select(func.count(User.user_id)).where(User.created_at >= window_start)) or 0

    return {
        "window_days": days,
        "active_past_7d": active_7d,
        "active_past_30d": active_30d,
        "inactive_over_30d": inactive_30d,
        "new_users_in_window": new_users_window,
    }


@router.get("/analytics/system/latency")
async def get_system_latency(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Lightweight latency probes for DB and cache."""
    db_latency_ms = None
    cache_latency_ms = None

    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        db_latency_ms = (time.monotonic() - start) * 1000
    except Exception as e:
        logger.error(f"DB latency probe failed: {e}")

    if cache_service.client:
        try:
            start = time.monotonic()
            await cache_service.client.ping()
            cache_latency_ms = (time.monotonic() - start) * 1000
        except Exception as e:
            logger.error(f"Cache latency probe failed: {e}")

    return {
        "db_latency_ms": db_latency_ms,
        "cache_latency_ms": cache_latency_ms,
    }


@router.get("/analytics/economy/velocity")
async def get_economic_velocity(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Estimate economic velocity over a window: volume / money supply."""
    start = datetime.utcnow() - timedelta(days=days)

    total_balance = await db.scalar(select(func.sum(User.balance_bdt))) or 0
    volume = await db.scalar(
        select(func.sum(Transaction.amount_bdt)).where(
            Transaction.status == "COMPLETED",
            Transaction.created_at >= start,
        )
    ) or 0

    txn_count = await db.scalar(
        select(func.count(Transaction.transaction_id)).where(
            Transaction.status == "COMPLETED",
            Transaction.created_at >= start,
        )
    ) or 0

    velocity = (volume / total_balance) if total_balance else None

    daily_rows = await db.execute(
        select(func.date(Transaction.created_at), func.sum(Transaction.amount_bdt))
        .where(Transaction.status == "COMPLETED", Transaction.created_at >= start)
        .group_by(func.date(Transaction.created_at))
        .order_by(func.date(Transaction.created_at))
    )
    daily_volume = [
        {"date": str(row[0]), "volume_bdt": int(row[1] or 0)} for row in daily_rows.all()
    ]

    return {
        "window_days": days,
        "money_supply_bdt": int(total_balance),
        "volume_bdt": int(volume),
        "transactions": txn_count,
        "velocity": velocity,
        "daily_volume": daily_volume,
    }


@router.get("/analytics/economy/top-earners")
async def get_top_earners(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Top earning sellers over a window (completed transactions)."""
    start = datetime.utcnow() - timedelta(days=days)

    rows = await db.execute(
        select(Transaction.seller_id, func.sum(Transaction.amount_bdt).label("revenue"))
        .where(
            Transaction.status == "COMPLETED",
            Transaction.created_at >= start,
            Transaction.seller_id.isnot(None),
        )
        .group_by(Transaction.seller_id)
        .order_by(desc("revenue"))
        .limit(limit)
    )

    top = [
        {"seller_id": str(r.seller_id), "revenue_bdt": int(r.revenue or 0)} for r in rows.all()
    ]

    return {"window_days": days, "top": top}


@router.get("/analytics/system/query-performance")
async def get_query_performance(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Lightweight query timing snapshots for key tables."""
    timings = {}

    async def _time_query(label: str, stmt):
        start = time.monotonic()
        await db.execute(stmt)
        timings[label] = (time.monotonic() - start) * 1000

    try:
        await _time_query("select_1", text("SELECT 1"))
        await _time_query("users_count", select(func.count(User.user_id)))
        await _time_query("listings_count", select(func.count(Listing.listing_id)))
        await _time_query("transactions_count", select(func.count(Transaction.transaction_id)))
    except Exception as e:
        logger.error(f"Query performance probe failed: {e}")

    return {"timings_ms": timings}


@router.get("/analytics/economy/summary")
async def get_economy_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """High-level economic summary over a window."""
    window_start = datetime.utcnow() - timedelta(days=days)

    total_balance = await db.scalar(select(func.sum(User.balance_bdt))) or 0
    completed_sum = await db.scalar(
        select(func.sum(Transaction.amount_bdt)).where(Transaction.status == "COMPLETED")
    ) or 0
    completed_count = await db.scalar(
        select(func.count(Transaction.transaction_id)).where(Transaction.status == "COMPLETED")
    ) or 0

    sold_30d = await db.scalar(
        select(func.count(Listing.listing_id)).where(
            Listing.status == ListingStatus.SOLD,
            Listing.sold_at >= window_start
        )
    ) or 0
    active_listings = await db.scalar(select(func.count(Listing.listing_id)).where(Listing.status == ListingStatus.ACTIVE)) or 0

    return {
        "window_days": days,
        "money_supply_bdt": int(total_balance),
        "total_revenue_bdt": int(completed_sum),
        "total_transactions": completed_count,
        "active_listings": active_listings,
        "listings_sold_in_window": sold_30d,
    }


@router.get("/analytics/market-health")
async def get_market_health(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Marketplace health metrics: success rate, time-to-sale, active inventory."""
    start = datetime.utcnow() - timedelta(days=days)

    total_created = await db.scalar(select(func.count(Listing.listing_id)).where(Listing.created_at >= start)) or 0

    sold_count = await db.scalar(
        select(func.count(Listing.listing_id)).where(
            Listing.status == ListingStatus.SOLD,
            Listing.sold_at.isnot(None),
            Listing.sold_at >= start,
        )
    ) or 0

    expired_count = await db.scalar(
        select(func.count(Listing.listing_id)).where(
            Listing.status == ListingStatus.EXPIRED,
            Listing.updated_at >= start
        )
    ) or 0

    cancelled_count = await db.scalar(
        select(func.count(Listing.listing_id)).where(
            Listing.status == ListingStatus.CANCELLED,
            Listing.updated_at >= start
        )
    ) or 0

    denominator = sold_count + expired_count + cancelled_count
    success_rate = (sold_count / denominator) if denominator else None

    avg_time_to_sale_seconds = await db.scalar(
        select(func.avg(func.extract("epoch", Listing.sold_at - Listing.created_at))).where(
            Listing.status == ListingStatus.SOLD,
            Listing.sold_at.isnot(None),
            Listing.sold_at >= start,
        )
    )
    avg_time_to_sale_hours = (avg_time_to_sale_seconds / 3600) if avg_time_to_sale_seconds else None

    active_listings = await db.scalar(select(func.count(Listing.listing_id)).where(Listing.status == ListingStatus.ACTIVE)) or 0

    return {
        "window_days": days,
        "created": total_created,
        "sold": sold_count,
        "expired": expired_count,
        "cancelled": cancelled_count,
        "success_rate": success_rate,
        "avg_time_to_sale_hours": avg_time_to_sale_hours,
        "active_listings": active_listings,
    }


@router.get("/analytics/users/behavior")
async def get_user_behavior_metrics(
    days: int = Query(default=30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """User behavior metrics: daily active users and recency."""
    start = datetime.utcnow() - timedelta(days=days)

    dau_rows = await db.execute(
        select(func.date(User.last_login).label("date"), func.count(User.user_id)).where(
            User.last_login.isnot(None),
            User.last_login >= start
        ).group_by(func.date(User.last_login)).order_by(func.date(User.last_login))
    )
    daily = [{"date": str(r.date), "active_users": r[1]} for r in dau_rows.all()]

    total_active = sum(item["active_users"] for item in daily)
    avg_daily_active = (total_active / len(daily)) if daily else 0

    recent_logins = await db.scalar(select(func.count(User.user_id)).where(User.last_login >= datetime.utcnow() - timedelta(days=7))) or 0

    return {
        "window_days": days,
        "daily_active": daily,
        "avg_daily_active": avg_daily_active,
        "active_past_7_days": recent_logins,
    }


@router.get("/analytics/system/performance")
async def get_system_performance(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """System performance snapshot using pool/cache/websocket stats."""
    db_ok = True
    try:
        await db.execute(select(1))
    except Exception as e:
        logger.error(f"DB check failed: {e}")
        db_ok = False

    cache_ok = await cache_service.is_healthy()
    cache_stats = await cache_service.get_stats()
    pool_stats = _get_pool_stats()
    websocket_stats = connection_manager.get_stats()

    return {
        "database_ok": db_ok,
        "pool": pool_stats,
        "cache_ok": cache_ok,
        "cache_stats": cache_stats,
        "websocket_stats": websocket_stats,
    }


# ============================================
# User Management
# ============================================

@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """List all users with pagination and filters"""
    try:
        query = select(User)

        # Apply filters
        if search:
            query = query.where(
                (User.username.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%"))
            )

        if role:
            query = query.where(User.role == role)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(User.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        users = result.scalars().all()

        return {
            "data": [
                {
                    "user_id": u.user_id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                    "balance_bdt": u.balance_bdt,
                    "created_at": u.created_at.isoformat(),
                    "last_login": u.last_login.isoformat() if u.last_login else None
                }
                for u in users
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get detailed user information"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get user's lands
        lands_count = await db.scalar(
            select(func.count(Land.land_id)).where(Land.owner_id == user_id)
        )

        # Get user's transactions
        transactions_count = await db.scalar(
            select(func.count(Transaction.transaction_id)).where(
                (Transaction.buyer_id == user_id) | (Transaction.seller_id == user_id)
            )
        )

        # Get user's listings
        listings_count = await db.scalar(
            select(func.count(Listing.listing_id)).where(Listing.seller_id == user_id)
        )

        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "balance_bdt": user.balance_bdt,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "stats": {
                "lands_owned": lands_count or 0,
                "transactions": transactions_count or 0,
                "active_listings": listings_count or 0
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user details"
        )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    update_data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update user details (admin only)"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update fields
        if update_data.role is not None:
            user.role = update_data.role

        if update_data.balance_bdt is not None:
            user.balance_bdt = update_data.balance_bdt

        if update_data.is_active is not None:
            # Assuming User model has is_active field
            pass  # Add field to model if needed

        user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="update_user",
            resource_type="user",
            resource_id=user_id,
            action="Admin updated user",
            details={"changes": update_data.dict(exclude_none=True)}
        )
        db.add(audit_log)
        await db.commit()

        return {
            "message": "User updated successfully",
            "user_id": user.user_id,
            "updated_fields": update_data.dict(exclude_none=True)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


# ============================================
# System Monitoring
# ============================================

@router.get("/system/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get system health metrics"""
    try:
        # Database health
        db_healthy = True
        try:
            await db.execute(select(1))
        except:
            db_healthy = False

        # Redis health
        redis_healthy = await cache_service.is_healthy()

        # Get cache stats
        cache_stats = {
            "hit_rate": "N/A",  # Implement if Redis provides stats
            "memory_usage": "N/A"
        }

        return {
            "status": "healthy" if (db_healthy and redis_healthy) else "degraded",
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy"
            },
            "cache_stats": cache_stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/system/audit-logs")
async def get_audit_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get audit logs"""
    try:
        query = select(AuditLog)

        if action:
            query = query.where(AuditLog.event_type == action)

        if user_id:
            query = query.where(AuditLog.actor_id == user_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(AuditLog.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        logs = result.scalars().all()

        return {
            "data": [
                {
                    "log_id": str(log.log_id),
                    "user_id": str(log.actor_id) if log.actor_id else None,
                    "action": log.event_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": str(log.details) if log.details else None,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audit logs"
        )


# ============================================
# MARKETPLACE & ECONOMY
# ============================================

@router.get("/marketplace/listings")
async def get_marketplace_listings(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get all marketplace listings with filters"""
    try:
        query = select(Listing).join(User, Listing.seller_id == User.user_id)

        # Apply filters
        if status:
            query = query.where(Listing.status == status)

        if search:
            query = query.where(
                User.username.ilike(f"%{search}%")
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(Listing.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        listings = result.scalars().all()

        return {
            "data": [
                {
                    "listing_id": l.listing_id,
                    "land_id": l.land_id,
                    "seller_id": l.seller_id,
                    "price_bdt": l.price_bdt,
                    "listing_type": l.listing_type,
                    "status": l.status,
                    "created_at": l.created_at.isoformat(),
                    "expires_at": l.expires_at.isoformat() if l.expires_at else None
                }
                for l in listings
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting marketplace listings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch marketplace listings"
        )


@router.delete("/marketplace/listings/{listing_id}")
async def remove_listing(
    listing_id: str,
    reason: str = Query(..., description="Reason for removal"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Remove a fraudulent or inappropriate listing"""
    try:
        listing = await db.get(Listing, listing_id)
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        # Update listing status
        listing.status = "removed"
        listing.updated_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="remove_listing",
            resource_type="listing",
            resource_id=listing_id,
            action="Removed listing",
            details={"reason": reason}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Listing removed successfully",
            "listing_id": listing_id,
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing listing: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove listing"
        )


@router.get("/transactions")
async def get_transactions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get all transactions with filters"""
    try:
        query = select(Transaction)

        # Apply filters
        if status:
            query = query.where(Transaction.status == status)

        if search:
            # Search by buyer or seller username
            query = query.join(User, Transaction.buyer_id == User.user_id).where(
                User.username.ilike(f"%{search}%")
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(Transaction.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        transactions = result.scalars().all()

        return {
            "data": [
                {
                    "transaction_id": t.transaction_id,
                    "buyer_id": t.buyer_id,
                    "seller_id": t.seller_id,
                    "land_id": t.land_id,
                    "amount_bdt": t.amount_bdt,
                    "status": t.status,
                    "created_at": t.created_at.isoformat()
                }
                for t in transactions
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch transactions"
        )


@router.post("/transactions/{transaction_id}/refund")
async def refund_transaction(
    transaction_id: str,
    reason: str = Query(..., description="Reason for refund"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Refund a completed transaction"""
    try:
        transaction = await db.get(Transaction, transaction_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        if transaction.status != "COMPLETED":
            raise HTTPException(
                status_code=400,
                detail="Can only refund completed transactions"
            )

        # Get buyer and seller
        buyer = await db.get(User, transaction.buyer_id)
        seller = await db.get(User, transaction.seller_id)

        if not buyer or not seller:
            raise HTTPException(status_code=404, detail="User not found")

        # Refund money to buyer
        buyer.balance_bdt += transaction.amount_bdt

        # Deduct from seller
        seller.balance_bdt -= transaction.amount_bdt

        # Update transaction status
        transaction.status = "refunded"
        transaction.updated_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="refund_transaction",
            resource_type="transaction",
            resource_id=transaction_id,
            action="Refunded transaction",
            details={"reason": reason, "amount_bdt": transaction.amount_bdt}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Transaction refunded successfully",
            "transaction_id": transaction_id,
            "amount_refunded": transaction.amount_bdt,
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refunding transaction: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refund transaction"
        )


@router.get("/transactions/export")
async def export_transactions(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Export transactions as CSV data"""
    try:
        query = select(Transaction)

        if start_date:
            query = query.where(Transaction.created_at >= start_date)

        if end_date:
            query = query.where(Transaction.created_at <= end_date)

        result = await db.execute(query.order_by(Transaction.created_at))
        transactions = result.scalars().all()

        # Format as CSV-like data
        csv_data = []
        for t in transactions:
            csv_data.append({
                "transaction_id": str(t.transaction_id),
                "buyer_id": str(t.buyer_id),
                "seller_id": str(t.seller_id),
                "land_id": str(t.land_id),
                "amount_bdt": t.amount_bdt,
                "status": t.status,
                "created_at": t.created_at.isoformat()
            })

        return {
            "data": csv_data,
            "count": len(csv_data),
            "exported_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export transactions"
        )


class EconomicSettingsUpdate(BaseModel):
    transaction_fee_percent: Optional[float] = None
    biome_trade_fee_percent: Optional[float] = None
    base_land_price_bdt: Optional[int] = None
    elevation_price_min_factor: Optional[float] = None
    elevation_price_max_factor: Optional[float] = None
    forest_multiplier: Optional[float] = None
    grassland_multiplier: Optional[float] = None
    water_multiplier: Optional[float] = None
    desert_multiplier: Optional[float] = None
    snow_multiplier: Optional[float] = None
    max_land_price_bdt: Optional[int] = None
    min_land_price_bdt: Optional[int] = None
    enable_land_trading: Optional[bool] = None
    # Biome Market Controls
    max_price_move_percent: Optional[float] = None
    max_transaction_percent: Optional[float] = None
    redistribution_pool_percent: Optional[float] = None
    biome_trading_paused: Optional[bool] = None
    biome_prices_frozen: Optional[bool] = None
    # Biome Land Base Prices
    plains_base_price: Optional[float] = None
    forest_base_price: Optional[float] = None
    beach_base_price: Optional[float] = None
    mountain_base_price: Optional[float] = None
    desert_base_price: Optional[float] = None
    snow_base_price: Optional[float] = None
    ocean_base_price: Optional[float] = None
    # Marketplace Fee Tiers
    fee_tier_1_threshold: Optional[int] = None
    fee_tier_1_percent: Optional[float] = None
    fee_tier_2_threshold: Optional[int] = None
    fee_tier_2_percent: Optional[float] = None
    fee_tier_3_threshold: Optional[int] = None
    fee_tier_3_percent: Optional[float] = None
    listing_creation_fee_bdt: Optional[int] = None
    premium_listing_fee_bdt: Optional[int] = None
    success_fee_mode: Optional[str] = None
    success_fee_percent: Optional[float] = None
    success_fee_flat_bdt: Optional[int] = None
    max_price_deviation_percent: Optional[float] = None
    parcel_size_limit: Optional[int] = None
    # Rate Limits
    api_requests_per_minute: Optional[int] = None
    marketplace_actions_per_hour: Optional[int] = None
    chat_messages_per_minute: Optional[int] = None
    biome_trades_per_minute: Optional[int] = None
    # Fraud Detection Thresholds
    wash_trading_min_trades_window: Optional[int] = None
    wash_trading_min_volume_percent: Optional[float] = None
    related_account_min_transactions: Optional[int] = None
    related_account_max_price_variance_percent: Optional[float] = None
    price_deviation_auto_reject_percent: Optional[float] = None
    
    # Market Manipulation Detection Thresholds
    market_spike_threshold_percent: Optional[float] = None
    market_spike_window_seconds: Optional[int] = None
    order_clustering_threshold: Optional[int] = None
    order_clustering_window_seconds: Optional[int] = None
    pump_and_dump_price_increase_percent: Optional[float] = None
    pump_and_dump_volume_window_minutes: Optional[int] = None
    manipulation_alert_auto_freeze: Optional[bool] = None
    manipulation_alert_severity_threshold: Optional[str] = None
    
    # Emergency Market Reset Controls
    market_emergency_reset_enabled: Optional[bool] = None
    market_reset_clear_all_orders: Optional[bool] = None
    market_reset_reset_prices: Optional[bool] = None
    market_reset_clear_volatility_history: Optional[bool] = None
    market_reset_redistribute_wealth: Optional[bool] = None
    market_reset_redistribution_gini_target: Optional[float] = None
    market_reset_require_confirmation: Optional[bool] = None
    market_reset_cooldown_minutes: Optional[int] = None
    
    # Biome Market Initialization
    biome_initial_cash_bdt: Optional[int] = None
    biome_initial_shares_outstanding: Optional[int] = None
    biome_initial_share_price_bdt: Optional[float] = None
    biome_price_update_frequency_seconds: Optional[int] = None
    attention_weight_algorithm_version: Optional[str] = None
    
    # Attention-Weight Algorithm Parameters
    attention_weight_recency_decay: Optional[float] = None
    attention_weight_volume_factor: Optional[float] = None
    attention_weight_momentum_threshold: Optional[float] = None
    attention_weight_volatility_window_minutes: Optional[int] = None
    attention_weight_update_interval_seconds: Optional[int] = None
    
    # Auction Duration Limits
    auction_min_duration_hours: Optional[int] = None
    auction_max_duration_hours: Optional[int] = None
    
    # Land Pricing Formula Controls
    land_pricing_formula: Optional[str] = None
    fixed_land_price_bdt: Optional[int] = None
    dynamic_pricing_biome_influence: Optional[float] = None
    dynamic_pricing_elevation_influence: Optional[float] = None
    
    # Fencing Cost Controls
    fencing_enabled: Optional[bool] = None
    fencing_cost_per_unit: Optional[int] = None
    fencing_maintenance_cost_percent: Optional[float] = None
    fencing_durability_years: Optional[int] = None
    
    # Parcel Rules
    parcel_connectivity_required: Optional[bool] = None
    parcel_diagonal_allowed: Optional[bool] = None
    parcel_min_size: Optional[int] = None
    parcel_max_size: Optional[int] = None
    
    # Ownership Limits
    max_lands_per_user: Optional[int] = None
    max_lands_per_biome_per_user: Optional[int] = None
    max_contiguous_lands: Optional[int] = None
    ownership_cooldown_minutes: Optional[int] = None
    
    # Exploration Incentives
    exploration_first_discover_enabled: Optional[bool] = None
    exploration_first_discover_bonus_bdt: Optional[int] = None
    exploration_rare_land_spawn_rate: Optional[float] = None
    exploration_rare_land_bonus_multiplier: Optional[float] = None

    # Fraud Enforcement Controls
    wash_trading_enforcement_enabled: Optional[bool] = None
    related_account_enforcement_enabled: Optional[bool] = None
    price_deviation_auto_reject_enabled: Optional[bool] = None
    fraud_temp_suspend_minutes: Optional[int] = None


class WorldSettingsUpdate(BaseModel):
    world_seed: Optional[int] = None
    noise_frequency: Optional[float] = None
    noise_octaves: Optional[int] = None
    noise_persistence: Optional[float] = None
    noise_lacunarity: Optional[float] = None
    biome_forest_percent: Optional[float] = None
    biome_grassland_percent: Optional[float] = None
    biome_water_percent: Optional[float] = None
    biome_desert_percent: Optional[float] = None
    biome_snow_percent: Optional[float] = None


class CacheSettingsUpdate(BaseModel):
    chunk_cache_ttl_seconds: Optional[int] = None


@router.get("/config/economy")
async def get_economic_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get economic configuration settings"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Use the model's to_dict method to return all fields
        return config.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting economic settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch economic settings"
        )


@router.patch("/config/economy")
async def update_economic_settings(
    settings: EconomicSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update economic configuration settings"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Update fields
        if settings.transaction_fee_percent is not None:
            config.transaction_fee_percent = settings.transaction_fee_percent

        if settings.biome_trade_fee_percent is not None:
            config.biome_trade_fee_percent = settings.biome_trade_fee_percent

        if settings.base_land_price_bdt is not None:
            config.base_land_price_bdt = settings.base_land_price_bdt

        if settings.elevation_price_min_factor is not None:
            config.elevation_price_min_factor = settings.elevation_price_min_factor

        if settings.elevation_price_max_factor is not None:
            config.elevation_price_max_factor = settings.elevation_price_max_factor

        if settings.forest_multiplier is not None:
            config.forest_multiplier = settings.forest_multiplier

        if settings.grassland_multiplier is not None:
            config.grassland_multiplier = settings.grassland_multiplier

        if settings.water_multiplier is not None:
            config.water_multiplier = settings.water_multiplier

        if settings.desert_multiplier is not None:
            config.desert_multiplier = settings.desert_multiplier

        if settings.snow_multiplier is not None:
            config.snow_multiplier = settings.snow_multiplier

        if settings.max_land_price_bdt is not None:
            config.max_land_price_bdt = settings.max_land_price_bdt

        if settings.min_land_price_bdt is not None:
            config.min_land_price_bdt = settings.min_land_price_bdt

        if settings.enable_land_trading is not None:
            config.enable_land_trading = settings.enable_land_trading

        # Biome Market Controls
        if settings.max_price_move_percent is not None:
            config.max_price_move_percent = settings.max_price_move_percent

        if settings.max_transaction_percent is not None:
            config.max_transaction_percent = settings.max_transaction_percent

        if settings.redistribution_pool_percent is not None:
            config.redistribution_pool_percent = settings.redistribution_pool_percent

        if settings.biome_trading_paused is not None:
            config.biome_trading_paused = settings.biome_trading_paused

        if settings.biome_prices_frozen is not None:
            config.biome_prices_frozen = settings.biome_prices_frozen
        # Biome Land Base Prices
        if settings.plains_base_price is not None:
            config.plains_base_price = settings.plains_base_price

        if settings.forest_base_price is not None:
            config.forest_base_price = settings.forest_base_price

        if settings.beach_base_price is not None:
            config.beach_base_price = settings.beach_base_price

        if settings.mountain_base_price is not None:
            config.mountain_base_price = settings.mountain_base_price

        if settings.desert_base_price is not None:
            config.desert_base_price = settings.desert_base_price

        if settings.snow_base_price is not None:
            config.snow_base_price = settings.snow_base_price

        if settings.ocean_base_price is not None:
            config.ocean_base_price = settings.ocean_base_price

        # Marketplace Fee Tiers
        if settings.fee_tier_1_threshold is not None:
            config.fee_tier_1_threshold = settings.fee_tier_1_threshold
        if settings.fee_tier_1_percent is not None:
            config.fee_tier_1_percent = settings.fee_tier_1_percent
        if settings.fee_tier_2_threshold is not None:
            config.fee_tier_2_threshold = settings.fee_tier_2_threshold
        if settings.fee_tier_2_percent is not None:
            config.fee_tier_2_percent = settings.fee_tier_2_percent
        if settings.fee_tier_3_threshold is not None:
            config.fee_tier_3_threshold = settings.fee_tier_3_threshold
        if settings.fee_tier_3_percent is not None:
            config.fee_tier_3_percent = settings.fee_tier_3_percent

        # Listing and success fees
        if settings.listing_creation_fee_bdt is not None:
            if settings.listing_creation_fee_bdt < 0:
                raise HTTPException(status_code=400, detail="listing_creation_fee_bdt must be non-negative")
            config.listing_creation_fee_bdt = settings.listing_creation_fee_bdt

        if settings.premium_listing_fee_bdt is not None:
            if settings.premium_listing_fee_bdt < 0:
                raise HTTPException(status_code=400, detail="premium_listing_fee_bdt must be non-negative")
            config.premium_listing_fee_bdt = settings.premium_listing_fee_bdt

        if settings.success_fee_mode is not None:
            if settings.success_fee_mode not in {"percent", "flat"}:
                raise HTTPException(status_code=400, detail="success_fee_mode must be 'percent' or 'flat'")
            config.success_fee_mode = settings.success_fee_mode

        if settings.success_fee_percent is not None:
            if settings.success_fee_percent < 0:
                raise HTTPException(status_code=400, detail="success_fee_percent must be non-negative")
            config.success_fee_percent = settings.success_fee_percent

        if settings.success_fee_flat_bdt is not None:
            if settings.success_fee_flat_bdt < 0:
                raise HTTPException(status_code=400, detail="success_fee_flat_bdt must be non-negative")
            config.success_fee_flat_bdt = settings.success_fee_flat_bdt

        # Price controls
        if settings.max_price_deviation_percent is not None:
            if settings.max_price_deviation_percent < 0:
                raise HTTPException(status_code=400, detail="max_price_deviation_percent must be non-negative")
            config.max_price_deviation_percent = settings.max_price_deviation_percent

        if settings.parcel_size_limit is not None:
            if settings.parcel_size_limit < 0:
                raise HTTPException(status_code=400, detail="parcel_size_limit must be non-negative")
            config.parcel_size_limit = settings.parcel_size_limit

        # Auction Duration Limits
        if settings.auction_min_duration_hours is not None:
            config.auction_min_duration_hours = settings.auction_min_duration_hours
        if settings.auction_max_duration_hours is not None:
            config.auction_max_duration_hours = settings.auction_max_duration_hours

        # Rate Limits
        if settings.api_requests_per_minute is not None:
            config.api_requests_per_minute = settings.api_requests_per_minute
        if settings.marketplace_actions_per_hour is not None:
            config.marketplace_actions_per_hour = settings.marketplace_actions_per_hour
        if settings.chat_messages_per_minute is not None:
            config.chat_messages_per_minute = settings.chat_messages_per_minute
        if settings.biome_trades_per_minute is not None:
            config.biome_trades_per_minute = settings.biome_trades_per_minute

        # Fraud Detection Thresholds
        if settings.wash_trading_min_trades_window is not None:
            if settings.wash_trading_min_trades_window < 1:
                raise HTTPException(status_code=400, detail="wash_trading_min_trades_window must be >= 1")
            config.wash_trading_min_trades_window = settings.wash_trading_min_trades_window

        if settings.wash_trading_min_volume_percent is not None:
            if settings.wash_trading_min_volume_percent < 0 or settings.wash_trading_min_volume_percent > 100:
                raise HTTPException(status_code=400, detail="wash_trading_min_volume_percent must be 0-100")
            config.wash_trading_min_volume_percent = settings.wash_trading_min_volume_percent

        if settings.related_account_min_transactions is not None:
            if settings.related_account_min_transactions < 1:
                raise HTTPException(status_code=400, detail="related_account_min_transactions must be >= 1")
            config.related_account_min_transactions = settings.related_account_min_transactions

        if settings.related_account_max_price_variance_percent is not None:
            if settings.related_account_max_price_variance_percent < 0:
                raise HTTPException(status_code=400, detail="related_account_max_price_variance_percent must be >= 0")
            config.related_account_max_price_variance_percent = settings.related_account_max_price_variance_percent

        if settings.price_deviation_auto_reject_percent is not None:
            if settings.price_deviation_auto_reject_percent < 0:
                raise HTTPException(status_code=400, detail="price_deviation_auto_reject_percent must be >= 0")
            config.price_deviation_auto_reject_percent = settings.price_deviation_auto_reject_percent

        # Biome Market Initialization
        if settings.biome_initial_cash_bdt is not None:
            if settings.biome_initial_cash_bdt < 0:
                raise HTTPException(status_code=400, detail="biome_initial_cash_bdt must be non-negative")
            config.biome_initial_cash_bdt = settings.biome_initial_cash_bdt

        if settings.biome_initial_shares_outstanding is not None:
            if settings.biome_initial_shares_outstanding < 1:
                raise HTTPException(status_code=400, detail="biome_initial_shares_outstanding must be >= 1")
            config.biome_initial_shares_outstanding = settings.biome_initial_shares_outstanding

        if settings.biome_initial_share_price_bdt is not None:
            if settings.biome_initial_share_price_bdt < 0.01:
                raise HTTPException(status_code=400, detail="biome_initial_share_price_bdt must be >= 0.01")
            config.biome_initial_share_price_bdt = settings.biome_initial_share_price_bdt

        if settings.biome_price_update_frequency_seconds is not None:
            if settings.biome_price_update_frequency_seconds < 60:
                raise HTTPException(status_code=400, detail="biome_price_update_frequency_seconds must be >= 60 (1 minute)")
            config.biome_price_update_frequency_seconds = settings.biome_price_update_frequency_seconds

        if settings.attention_weight_algorithm_version is not None:
            allowed = {"v1_uniform", "v1_volume_weighted", "v2_momentum", "v2_volatility"}
            if settings.attention_weight_algorithm_version not in allowed:
                raise HTTPException(status_code=400, detail=f"attention_weight_algorithm_version must be one of {allowed}")
            config.attention_weight_algorithm_version = settings.attention_weight_algorithm_version

        # Attention-Weight Algorithm Parameters
        if settings.attention_weight_recency_decay is not None:
            if settings.attention_weight_recency_decay < 0 or settings.attention_weight_recency_decay > 1:
                raise HTTPException(status_code=400, detail="attention_weight_recency_decay must be 0-1 (0=maximum decay, 1=no decay)")
            config.attention_weight_recency_decay = settings.attention_weight_recency_decay

        if settings.attention_weight_volume_factor is not None:
            if settings.attention_weight_volume_factor < 0 or settings.attention_weight_volume_factor > 1:
                raise HTTPException(status_code=400, detail="attention_weight_volume_factor must be 0-1")
            config.attention_weight_volume_factor = settings.attention_weight_volume_factor

        if settings.attention_weight_momentum_threshold is not None:
            if settings.attention_weight_momentum_threshold < 0.5:
                raise HTTPException(status_code=400, detail="attention_weight_momentum_threshold must be >= 0.5")
            config.attention_weight_momentum_threshold = settings.attention_weight_momentum_threshold

        if settings.attention_weight_volatility_window_minutes is not None:
            if settings.attention_weight_volatility_window_minutes < 1:
                raise HTTPException(status_code=400, detail="attention_weight_volatility_window_minutes must be >= 1")
            config.attention_weight_volatility_window_minutes = settings.attention_weight_volatility_window_minutes

        if settings.attention_weight_update_interval_seconds is not None:
            if settings.attention_weight_update_interval_seconds < 10:
                raise HTTPException(status_code=400, detail="attention_weight_update_interval_seconds must be >= 10 (10 seconds minimum)")
            config.attention_weight_update_interval_seconds = settings.attention_weight_update_interval_seconds

        # Market Manipulation Detection Thresholds
        if settings.market_spike_threshold_percent is not None:
            if settings.market_spike_threshold_percent < 0:
                raise HTTPException(status_code=400, detail="market_spike_threshold_percent must be non-negative")
            config.market_spike_threshold_percent = settings.market_spike_threshold_percent

        if settings.market_spike_window_seconds is not None:
            if settings.market_spike_window_seconds < 30:
                raise HTTPException(status_code=400, detail="market_spike_window_seconds must be >= 30 (30 seconds minimum)")
            config.market_spike_window_seconds = settings.market_spike_window_seconds

        if settings.order_clustering_threshold is not None:
            if settings.order_clustering_threshold < 1:
                raise HTTPException(status_code=400, detail="order_clustering_threshold must be >= 1")
            config.order_clustering_threshold = settings.order_clustering_threshold

        if settings.order_clustering_window_seconds is not None:
            if settings.order_clustering_window_seconds < 10:
                raise HTTPException(status_code=400, detail="order_clustering_window_seconds must be >= 10")
            config.order_clustering_window_seconds = settings.order_clustering_window_seconds

        if settings.pump_and_dump_price_increase_percent is not None:
            if settings.pump_and_dump_price_increase_percent < 0:
                raise HTTPException(status_code=400, detail="pump_and_dump_price_increase_percent must be non-negative")
            config.pump_and_dump_price_increase_percent = settings.pump_and_dump_price_increase_percent

        if settings.pump_and_dump_volume_window_minutes is not None:
            if settings.pump_and_dump_volume_window_minutes < 1:
                raise HTTPException(status_code=400, detail="pump_and_dump_volume_window_minutes must be >= 1")
            config.pump_and_dump_volume_window_minutes = settings.pump_and_dump_volume_window_minutes

        if settings.manipulation_alert_auto_freeze is not None:
            config.manipulation_alert_auto_freeze = settings.manipulation_alert_auto_freeze

        if settings.manipulation_alert_severity_threshold is not None:
            allowed_severities = {"low", "medium", "high", "critical"}
            if settings.manipulation_alert_severity_threshold not in allowed_severities:
                raise HTTPException(status_code=400, detail=f"manipulation_alert_severity_threshold must be one of {allowed_severities}")
            config.manipulation_alert_severity_threshold = settings.manipulation_alert_severity_threshold

        # Emergency Market Reset Controls
        if settings.market_emergency_reset_enabled is not None:
            config.market_emergency_reset_enabled = settings.market_emergency_reset_enabled

        if settings.market_reset_clear_all_orders is not None:
            config.market_reset_clear_all_orders = settings.market_reset_clear_all_orders

        if settings.market_reset_reset_prices is not None:
            config.market_reset_reset_prices = settings.market_reset_reset_prices

        if settings.market_reset_clear_volatility_history is not None:
            config.market_reset_clear_volatility_history = settings.market_reset_clear_volatility_history

        if settings.market_reset_redistribute_wealth is not None:
            config.market_reset_redistribute_wealth = settings.market_reset_redistribute_wealth

        if settings.market_reset_redistribution_gini_target is not None:
            if settings.market_reset_redistribution_gini_target < 0 or settings.market_reset_redistribution_gini_target > 1:
                raise HTTPException(status_code=400, detail="market_reset_redistribution_gini_target must be 0-1 (0=equality, 1=inequality)")
            config.market_reset_redistribution_gini_target = settings.market_reset_redistribution_gini_target

        if settings.market_reset_require_confirmation is not None:
            config.market_reset_require_confirmation = settings.market_reset_require_confirmation

        if settings.market_reset_cooldown_minutes is not None:
            if settings.market_reset_cooldown_minutes < 0:
                raise HTTPException(status_code=400, detail="market_reset_cooldown_minutes must be non-negative")
            config.market_reset_cooldown_minutes = settings.market_reset_cooldown_minutes

        # Land Pricing Formula Controls
        if settings.land_pricing_formula is not None:
            allowed_formulas = {"dynamic", "fixed"}
            if settings.land_pricing_formula not in allowed_formulas:
                raise HTTPException(status_code=400, detail=f"land_pricing_formula must be one of {allowed_formulas}")
            config.land_pricing_formula = settings.land_pricing_formula

        if settings.fixed_land_price_bdt is not None:
            if settings.fixed_land_price_bdt < 1:
                raise HTTPException(status_code=400, detail="fixed_land_price_bdt must be >= 1")
            config.fixed_land_price_bdt = settings.fixed_land_price_bdt

        if settings.dynamic_pricing_biome_influence is not None:
            if settings.dynamic_pricing_biome_influence < 0:
                raise HTTPException(status_code=400, detail="dynamic_pricing_biome_influence must be non-negative")
            config.dynamic_pricing_biome_influence = settings.dynamic_pricing_biome_influence

        if settings.dynamic_pricing_elevation_influence is not None:
            if settings.dynamic_pricing_elevation_influence < 0:
                raise HTTPException(status_code=400, detail="dynamic_pricing_elevation_influence must be non-negative")
            config.dynamic_pricing_elevation_influence = settings.dynamic_pricing_elevation_influence

        # Fencing Cost Controls
        if settings.fencing_enabled is not None:
            config.fencing_enabled = settings.fencing_enabled

        if settings.fencing_cost_per_unit is not None:
            if settings.fencing_cost_per_unit < 0:
                raise HTTPException(status_code=400, detail="fencing_cost_per_unit must be non-negative")
            config.fencing_cost_per_unit = settings.fencing_cost_per_unit

        if settings.fencing_maintenance_cost_percent is not None:
            if settings.fencing_maintenance_cost_percent < 0 or settings.fencing_maintenance_cost_percent > 100:
                raise HTTPException(status_code=400, detail="fencing_maintenance_cost_percent must be 0-100")
            config.fencing_maintenance_cost_percent = settings.fencing_maintenance_cost_percent

        if settings.fencing_durability_years is not None:
            if settings.fencing_durability_years < 1:
                raise HTTPException(status_code=400, detail="fencing_durability_years must be >= 1")
            config.fencing_durability_years = settings.fencing_durability_years

        # Parcel Rules
        if settings.parcel_connectivity_required is not None:
            config.parcel_connectivity_required = settings.parcel_connectivity_required

        if settings.parcel_diagonal_allowed is not None:
            config.parcel_diagonal_allowed = settings.parcel_diagonal_allowed

        if settings.parcel_min_size is not None:
            if settings.parcel_min_size < 1:
                raise HTTPException(status_code=400, detail="parcel_min_size must be >= 1")
            config.parcel_min_size = settings.parcel_min_size

        if settings.parcel_max_size is not None:
            if settings.parcel_max_size < settings.parcel_min_size if settings.parcel_min_size else 1:
                raise HTTPException(status_code=400, detail="parcel_max_size must be >= parcel_min_size")
            config.parcel_max_size = settings.parcel_max_size

        # Ownership Limits
        if settings.max_lands_per_user is not None:
            if settings.max_lands_per_user < 1:
                raise HTTPException(status_code=400, detail="max_lands_per_user must be >= 1")
            config.max_lands_per_user = settings.max_lands_per_user

        if settings.max_lands_per_biome_per_user is not None:
            if settings.max_lands_per_biome_per_user < 1:
                raise HTTPException(status_code=400, detail="max_lands_per_biome_per_user must be >= 1")
            config.max_lands_per_biome_per_user = settings.max_lands_per_biome_per_user

        if settings.max_contiguous_lands is not None:
            if settings.max_contiguous_lands < 1:
                raise HTTPException(status_code=400, detail="max_contiguous_lands must be >= 1")
            config.max_contiguous_lands = settings.max_contiguous_lands

        if settings.ownership_cooldown_minutes is not None:
            if settings.ownership_cooldown_minutes < 0:
                raise HTTPException(status_code=400, detail="ownership_cooldown_minutes must be non-negative")
            config.ownership_cooldown_minutes = settings.ownership_cooldown_minutes

        # Exploration Incentives
        if settings.exploration_first_discover_enabled is not None:
            config.exploration_first_discover_enabled = settings.exploration_first_discover_enabled

        if settings.exploration_first_discover_bonus_bdt is not None:
            if settings.exploration_first_discover_bonus_bdt < 0:
                raise HTTPException(status_code=400, detail="exploration_first_discover_bonus_bdt must be non-negative")
            config.exploration_first_discover_bonus_bdt = settings.exploration_first_discover_bonus_bdt

        if settings.exploration_rare_land_spawn_rate is not None:
            if settings.exploration_rare_land_spawn_rate < 0 or settings.exploration_rare_land_spawn_rate > 1:
                raise HTTPException(status_code=400, detail="exploration_rare_land_spawn_rate must be 0-1 (probability)")
            config.exploration_rare_land_spawn_rate = settings.exploration_rare_land_spawn_rate

        if settings.exploration_rare_land_bonus_multiplier is not None:
            if settings.exploration_rare_land_bonus_multiplier < 1:
                raise HTTPException(status_code=400, detail="exploration_rare_land_bonus_multiplier must be >= 1")
            config.exploration_rare_land_bonus_multiplier = settings.exploration_rare_land_bonus_multiplier

        # Fraud Enforcement Controls
        if settings.wash_trading_enforcement_enabled is not None:
            config.wash_trading_enforcement_enabled = settings.wash_trading_enforcement_enabled

        if settings.related_account_enforcement_enabled is not None:
            config.related_account_enforcement_enabled = settings.related_account_enforcement_enabled

        if settings.price_deviation_auto_reject_enabled is not None:
            config.price_deviation_auto_reject_enabled = settings.price_deviation_auto_reject_enabled

        if settings.fraud_temp_suspend_minutes is not None:
            if settings.fraud_temp_suspend_minutes < 0:
                raise HTTPException(status_code=400, detail="fraud_temp_suspend_minutes must be non-negative")
            config.fraud_temp_suspend_minutes = settings.fraud_temp_suspend_minutes

        config.updated_at = datetime.utcnow()

        # Log action and commit once
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="update_economic_settings",
            resource_type="config",
            resource_id=str(config.config_id),
            action="Updated economic settings",
            details={"changes": settings.dict(exclude_none=True)}
        )
        db.add(audit_log)
        await db.commit()

        # Return the full updated config
        return config.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating economic settings: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update economic settings"
        )


@router.get("/config/world")
async def get_world_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get world generation and biome distribution settings."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "world_seed": config.world_seed,
        "noise": {
            "frequency": config.noise_frequency,
            "octaves": config.noise_octaves,
            "persistence": config.noise_persistence,
            "lacunarity": config.noise_lacunarity,
        },
        "biome_distribution": {
            "forest": config.biome_forest_percent,
            "grassland": config.biome_grassland_percent,
            "water": config.biome_water_percent,
            "desert": config.biome_desert_percent,
            "snow": config.biome_snow_percent,
        },
    }


@router.patch("/config/world")
async def update_world_settings(
    settings: WorldSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update world seed, noise parameters, and biome distribution."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # Validate and apply world seed
    if settings.world_seed is not None:
        config.world_seed = settings.world_seed

    # Noise params
    if settings.noise_frequency is not None:
        if settings.noise_frequency <= 0:
            raise HTTPException(status_code=400, detail="noise_frequency must be positive")
        config.noise_frequency = settings.noise_frequency

    if settings.noise_octaves is not None:
        if settings.noise_octaves < 1 or settings.noise_octaves > 8:
            raise HTTPException(status_code=400, detail="noise_octaves must be between 1 and 8")
        config.noise_octaves = settings.noise_octaves

    if settings.noise_persistence is not None:
        if settings.noise_persistence <= 0 or settings.noise_persistence >= 1:
            raise HTTPException(status_code=400, detail="noise_persistence must be between 0 and 1")
        config.noise_persistence = settings.noise_persistence

    if settings.noise_lacunarity is not None:
        if settings.noise_lacunarity <= 1:
            raise HTTPException(status_code=400, detail="noise_lacunarity must be greater than 1")
        config.noise_lacunarity = settings.noise_lacunarity

    # Biome distribution
    new_dist = {
        "forest": config.biome_forest_percent,
        "grassland": config.biome_grassland_percent,
        "water": config.biome_water_percent,
        "desert": config.biome_desert_percent,
        "snow": config.biome_snow_percent,
    }

    updates = settings.dict(exclude_none=True)
    for key in [
        "biome_forest_percent",
        "biome_grassland_percent",
        "biome_water_percent",
        "biome_desert_percent",
        "biome_snow_percent",
    ]:
        if key in updates:
            biome_key = key.replace("biome_", "").replace("_percent", "")
            new_dist[biome_key] = updates[key]

    if any(k.startswith("biome_") for k in updates.keys()):
        _validate_biome_distribution(new_dist)
        config.biome_forest_percent = new_dist["forest"]
        config.biome_grassland_percent = new_dist["grassland"]
        config.biome_water_percent = new_dist["water"]
        config.biome_desert_percent = new_dist["desert"]
        config.biome_snow_percent = new_dist["snow"]

    config.updated_at = datetime.utcnow()
    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="update_world_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated world settings",
        details=updates
    ))
    await db.commit()

    return {
        "message": "World settings updated successfully",
        "updated_fields": updates,
    }


@router.get("/config/cache")
async def get_cache_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get cache settings (chunk TTL)."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "chunk_cache_ttl_seconds": config.chunk_cache_ttl_seconds,
        "runtime_chunk_ttl_seconds": CACHE_TTLS.get("chunk"),
    }


@router.patch("/config/cache")
async def update_cache_settings(
    settings: CacheSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update cache controls such as chunk TTL."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    updates = settings.dict(exclude_none=True)

    if settings.chunk_cache_ttl_seconds is not None:
        if settings.chunk_cache_ttl_seconds <= 0:
            raise HTTPException(status_code=400, detail="chunk_cache_ttl_seconds must be positive")
        config.chunk_cache_ttl_seconds = settings.chunk_cache_ttl_seconds
        CACHE_TTLS["chunk"] = settings.chunk_cache_ttl_seconds

    config.updated_at = datetime.utcnow()
    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="update_cache_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated cache settings",
        details=updates,
    ))
    await db.commit()

    return {
        "message": "Cache settings updated successfully",
        "updated_fields": updates,
    }


# ============================================
# LAND MANAGEMENT
# ============================================

@router.get("/lands/analytics")
async def get_land_analytics(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get land analytics and statistics"""
    try:
        # Total lands
        total_lands = await db.scalar(select(func.count(Land.land_id)))

        # Allocated lands (with owner)
        allocated_lands = await db.scalar(
            select(func.count(Land.land_id)).where(Land.owner_id.isnot(None))
        )

        # Unallocated lands
        unallocated_lands = total_lands - allocated_lands if total_lands and allocated_lands else 0

        # Lands by shape (if column exists)
        shape_distribution = {}
        try:
            shape_result = await db.execute(
                select(Land.shape, func.count(Land.land_id).label('count'))
                .group_by(Land.shape)
            )
            shape_distribution = {row.shape: row.count for row in shape_result.all()}
        except:
            pass

        # Lands by biome
        biome_result = await db.execute(
            select(Land.biome, func.count(Land.land_id).label('count'))
            .group_by(Land.biome)
        )
        biome_distribution = {row.biome: row.count for row in biome_result.all()}

        # Lands for sale
        lands_for_sale = await db.scalar(
            select(func.count(Land.land_id)).where(Land.for_sale == True)
        )

        return {
            "total_lands": total_lands or 0,
            "allocated_lands": allocated_lands or 0,
            "unallocated_lands": unallocated_lands,
            "lands_for_sale": lands_for_sale or 0,
            "shape_distribution": shape_distribution,
            "biome_distribution": biome_distribution
        }

    except Exception as e:
        logger.error(f"Error getting land analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch land analytics"
        )


@router.post("/lands/{land_id}/transfer")
async def transfer_land_ownership(
    land_id: str,
    new_owner_id: str = Query(..., description="New owner user ID"),
    reason: str = Query(..., description="Reason for transfer"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Transfer land ownership to another user"""
    try:
        land = await db.get(Land, land_id)
        if not land:
            raise HTTPException(status_code=404, detail="Land not found")

        new_owner = await db.get(User, new_owner_id)
        if not new_owner:
            raise HTTPException(status_code=404, detail="New owner not found")

        old_owner_id = land.owner_id
        land.owner_id = new_owner_id
        land.for_sale = False
        land.updated_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="transfer_land",
            resource_type="land",
            resource_id=land_id,
            action="Transferred land ownership",
            details={"old_owner_id": str(old_owner_id) if old_owner_id else None, "new_owner_id": new_owner_id, "reason": reason}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Land transferred successfully",
            "land_id": land_id,
            "old_owner_id": str(old_owner_id) if old_owner_id else None,
            "new_owner_id": new_owner_id,
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transferring land: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transfer land"
        )


@router.delete("/lands/{land_id}/reclaim")
async def reclaim_land(
    land_id: str,
    reason: str = Query(..., description="Reason for reclaiming"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Reclaim a specific land plot"""
    try:
        land = await db.get(Land, land_id)
        if not land:
            raise HTTPException(status_code=404, detail="Land not found")

        old_owner_id = land.owner_id
        land.owner_id = None
        land.for_sale = False
        land.updated_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="reclaim_land",
            resource_type="land",
            resource_id=land_id,
            action="Reclaimed land",
            details={"previous_owner_id": str(old_owner_id) if old_owner_id else None, "reason": reason}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Land reclaimed successfully",
            "land_id": land_id,
            "previous_owner_id": str(old_owner_id) if old_owner_id else None,
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reclaiming land: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reclaim land"
        )


# ============================================
# USER MANAGEMENT (EXTENDED)
# ============================================

class UserSuspendRequest(BaseModel):
    reason: str
    duration_days: Optional[int] = None  # None = permanent


class UserBanRequest(BaseModel):
    reason: str
    ban_type: str = "full"  # 'full', 'marketplace', 'chat'
    duration_days: Optional[int] = None  # None = permanent


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    request: UserSuspendRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Suspend a user account"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.role == "admin":
            raise HTTPException(
                status_code=400,
                detail="Cannot suspend admin users"
            )

        # Calculate suspension end date
        suspended_until = None
        if request.duration_days:
            suspended_until = datetime.utcnow() + timedelta(days=request.duration_days)

        # Update user
        user.is_suspended = True
        user.suspension_reason = request.reason
        user.suspended_until = suspended_until
        user.updated_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="suspend_user",
            resource_type="user",
            resource_id=user_id,
            action="Suspended user",
            details={"reason": request.reason, "duration_days": request.duration_days or "permanent"}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "User suspended successfully",
            "user_id": user_id,
            "suspended_until": suspended_until.isoformat() if suspended_until else "permanent",
            "reason": request.reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suspending user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suspend user"
        )


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Remove suspension from a user account"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.is_suspended = False
        user.suspension_reason = None
        user.suspended_until = None
        user.updated_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="unsuspend_user",
            resource_type="user",
            resource_id=user_id,
            action="Removed user suspension",
            details={}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "User suspension removed successfully",
            "user_id": user_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unsuspending user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsuspend user"
        )


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    request: UserBanRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Ban a user from the platform or specific features"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.role == "admin":
            raise HTTPException(
                status_code=400,
                detail="Cannot ban admin users"
            )

        # Calculate ban expiration
        expires_at = None
        if request.duration_days:
            expires_at = datetime.utcnow() + timedelta(days=request.duration_days)

        # Create ban record
        ban = Ban(
            user_id=user_id,
            banned_by=admin["sub"],
            reason=request.reason,
            ban_type=request.ban_type,
            expires_at=expires_at,
            is_active=True
        )
        db.add(ban)

        # If full ban, also suspend the user
        if request.ban_type == "full":
            user.is_suspended = True
            user.suspension_reason = f"Banned: {request.reason}"
            user.suspended_until = expires_at

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="ban_user",
            resource_type="user",
            resource_id=user_id,
            action="Banned user",
            details={"ban_type": request.ban_type, "reason": request.reason}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "User banned successfully",
            "user_id": user_id,
            "ban_type": request.ban_type,
            "expires_at": expires_at.isoformat() if expires_at else "permanent",
            "reason": request.reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ban user"
        )


@router.delete("/users/{user_id}/ban")
async def unban_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Remove all active bans from a user"""
    try:
        # Deactivate all active bans
        result = await db.execute(
            select(Ban).where(
                and_(Ban.user_id == user_id, Ban.is_active == True)
            )
        )
        bans = result.scalars().all()

        if not bans:
            raise HTTPException(status_code=404, detail="No active bans found for this user")

        for ban in bans:
            ban.is_active = False

        # Also remove suspension if exists
        user = await db.get(User, user_id)
        if user:
            user.is_suspended = False
            user.suspension_reason = None
            user.suspended_until = None

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="unban_user",
            resource_type="user",
            resource_id=user_id,
            action="Unbanned user",
            details={"bans_removed": len(bans)}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "User unbanned successfully",
            "user_id": user_id,
            "bans_removed": len(bans)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unban user"
        )


@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get detailed user activity and statistics"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get lands count
        lands_count = await db.scalar(
            select(func.count(Land.land_id)).where(Land.owner_id == user_id)
        )

        # Get transactions count
        transactions_bought = await db.scalar(
            select(func.count(Transaction.transaction_id)).where(
                and_(Transaction.buyer_id == user_id, Transaction.status == "COMPLETED")
            )
        )

        transactions_sold = await db.scalar(
            select(func.count(Transaction.transaction_id)).where(
                and_(Transaction.seller_id == user_id, Transaction.status == "COMPLETED")
            )
        )

        # Get active listings
        active_listings = await db.scalar(
            select(func.count(Listing.listing_id)).where(
                and_(Listing.seller_id == user_id, Listing.status == "active")
            )
        )

        # Get messages count
        messages_count = await db.scalar(
            select(func.count(Message.message_id)).where(Message.sender_id == user_id)
        )

        # Get active bans
        result = await db.execute(
            select(Ban).where(
                and_(Ban.user_id == user_id, Ban.is_active == True)
            ).order_by(desc(Ban.created_at))
        )
        active_bans = result.scalars().all()

        return {
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_suspended": user.is_suspended,
            "suspension_reason": user.suspension_reason,
            "suspended_until": user.suspended_until.isoformat() if user.suspended_until else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat(),
            "statistics": {
                "lands_owned": lands_count or 0,
                "transactions_bought": transactions_bought or 0,
                "transactions_sold": transactions_sold or 0,
                "active_listings": active_listings or 0,
                "messages_sent": messages_count or 0,
                "balance_bdt": user.balance_bdt
            },
            "active_bans": [
                {
                    "ban_id": str(ban.ban_id),
                    "ban_type": ban.ban_type,
                    "reason": ban.reason,
                    "expires_at": ban.expires_at.isoformat() if ban.expires_at else "permanent",
                    "created_at": ban.created_at.isoformat()
                }
                for ban in active_bans
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user activity"
        )


# ============================================
# CONFIGURATION (FEATURES & LIMITS)
# ============================================

class FeatureTogglesUpdate(BaseModel):
    enable_land_trading: Optional[bool] = None
    enable_chat: Optional[bool] = None
    enable_registration: Optional[bool] = None
    maintenance_mode: Optional[bool] = None
    starter_land_enabled: Optional[bool] = None


class SystemLimitsUpdate(BaseModel):
    max_lands_per_user: Optional[int] = None
    max_listings_per_user: Optional[int] = None
    auction_bid_increment: Optional[int] = None
    auction_extend_minutes: Optional[int] = None
    max_lands_per_listing: Optional[int] = None
    max_listing_duration_days: Optional[int] = None
    listing_cooldown_minutes: Optional[int] = None
    min_reserve_price_percent: Optional[int] = None
    anti_sniping_enabled: Optional[bool] = None
    anti_sniping_extend_minutes: Optional[int] = None
    anti_sniping_threshold_minutes: Optional[int] = None


class IPAccessCreate(BaseModel):
    ip: str
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class IPAccessEntry(BaseModel):
    entry_id: str
    ip: str
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class PaymentSettingsUpdate(BaseModel):
    enable_bkash: Optional[bool] = None
    enable_nagad: Optional[bool] = None
    enable_rocket: Optional[bool] = None
    enable_sslcommerz: Optional[bool] = None
    bkash_mode: Optional[str] = None
    nagad_mode: Optional[str] = None
    rocket_mode: Optional[str] = None
    sslcommerz_mode: Optional[str] = None
    topup_min_bdt: Optional[int] = None
    topup_max_bdt: Optional[int] = None
    topup_daily_limit_bdt: Optional[int] = None
    topup_monthly_limit_bdt: Optional[int] = None
    gateway_fee_mode: Optional[str] = None
    gateway_fee_percent: Optional[float] = None
    gateway_fee_flat_bdt: Optional[int] = None
    payment_alert_window_minutes: Optional[int] = None
    payment_alert_failure_threshold: Optional[int] = None
    payment_reconcile_tolerance: Optional[int] = None


class CacheClearRequest(BaseModel):
    prefix: Optional[str] = None


class EmailSettingsUpdate(BaseModel):
    enable_email: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None
    default_from_email: Optional[str] = None
    email_rate_limit_per_hour: Optional[int] = None
    email_template_theme: Optional[str] = None


class LoggingSettingsUpdate(BaseModel):
    level: Optional[str] = None
    retention_days: Optional[int] = None


class NotificationSettingsUpdate(BaseModel):
    enable_push_notifications: Optional[bool] = None
    push_system_enabled: Optional[bool] = None
    push_marketing_enabled: Optional[bool] = None
    push_daily_limit: Optional[int] = None
    push_quiet_hours_start: Optional[int] = None
    push_quiet_hours_end: Optional[int] = None
    push_webhook_url: Optional[str] = None


class ChatSettingsUpdate(BaseModel):
    chat_max_length: Optional[int] = None
    chat_profanity_filter_enabled: Optional[bool] = None
    chat_block_keywords: Optional[str] = None
    chat_retention_days: Optional[int] = None
    chat_pm_enabled: Optional[bool] = None
    chat_group_max_members: Optional[int] = None


class AnnouncementSettingsUpdate(BaseModel):
    announcement_allow_high_priority: Optional[bool] = None
    announcement_max_priority: Optional[int] = None
    announcement_rate_limit_per_hour: Optional[int] = None


class BackupRequest(BaseModel):
    filename: Optional[str] = None


class RestoreRequest(BaseModel):
    filename: str


class SecuritySettingsUpdate(BaseModel):
    access_token_expire_minutes: Optional[int] = None
    refresh_token_expire_days: Optional[int] = None
    password_min_length: Optional[int] = None
    password_require_uppercase: Optional[bool] = None
    password_require_lowercase: Optional[bool] = None
    password_require_number: Optional[bool] = None
    password_require_special: Optional[bool] = None
    login_max_attempts: Optional[int] = None
    lockout_duration_minutes: Optional[int] = None
    max_sessions_per_user: Optional[int] = None


@router.get("/config/features")
async def get_feature_toggles(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get feature toggle settings"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        return {
            "enable_land_trading": config.enable_land_trading,
            "enable_chat": config.enable_chat,
            "enable_registration": config.enable_registration,
            "maintenance_mode": config.maintenance_mode,
            "starter_land_enabled": config.starter_land_enabled
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feature toggles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch feature toggles"
        )


@router.patch("/config/features")
async def update_feature_toggles(
    settings: FeatureTogglesUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update feature toggle settings"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Update fields
        if settings.enable_land_trading is not None:
            config.enable_land_trading = settings.enable_land_trading

        if settings.enable_chat is not None:
            config.enable_chat = settings.enable_chat

        if settings.enable_registration is not None:
            config.enable_registration = settings.enable_registration

        if settings.maintenance_mode is not None:
            config.maintenance_mode = settings.maintenance_mode

        if settings.starter_land_enabled is not None:
            config.starter_land_enabled = settings.starter_land_enabled

        config.updated_at = datetime.utcnow()
        await db.commit()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="update_feature_toggles",
            resource_type="config",
            resource_id=str(config.config_id),
            action="Updated feature toggles",
            details={"changes": settings.dict(exclude_none=True)}
        )
        db.add(audit_log)
        await db.commit()

        return {
            "message": "Feature toggles updated successfully",
            "updated_fields": settings.dict(exclude_none=True)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feature toggles: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feature toggles"
        )


@router.get("/config/limits")
async def get_system_limits(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get system limit settings"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        return {
            "max_lands_per_user": config.max_lands_per_user,
            "max_listings_per_user": config.max_listings_per_user,
            "auction_bid_increment": config.auction_bid_increment,
            "auction_extend_minutes": config.auction_extend_minutes,
            "max_lands_per_listing": config.max_lands_per_listing,
            "max_listing_duration_days": config.max_listing_duration_days,
            "listing_cooldown_minutes": config.listing_cooldown_minutes,
            "min_reserve_price_percent": config.min_reserve_price_percent,
            "anti_sniping_enabled": config.anti_sniping_enabled,
            "anti_sniping_extend_minutes": config.anti_sniping_extend_minutes,
            "anti_sniping_threshold_minutes": config.anti_sniping_threshold_minutes
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system limits"
        )


@router.patch("/config/limits")
async def update_system_limits(
    settings: SystemLimitsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update system limit settings"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Update fields
        if settings.max_lands_per_user is not None:
            config.max_lands_per_user = settings.max_lands_per_user

        if settings.max_listings_per_user is not None:
            config.max_listings_per_user = settings.max_listings_per_user

        if settings.auction_bid_increment is not None:
            config.auction_bid_increment = settings.auction_bid_increment

        if settings.auction_extend_minutes is not None:
            config.auction_extend_minutes = settings.auction_extend_minutes

        if settings.max_lands_per_listing is not None:
            config.max_lands_per_listing = settings.max_lands_per_listing

        if settings.max_listing_duration_days is not None:
            config.max_listing_duration_days = settings.max_listing_duration_days

        if settings.listing_cooldown_minutes is not None:
            config.listing_cooldown_minutes = settings.listing_cooldown_minutes

        if settings.min_reserve_price_percent is not None:
            config.min_reserve_price_percent = settings.min_reserve_price_percent

        if settings.anti_sniping_enabled is not None:
            config.anti_sniping_enabled = settings.anti_sniping_enabled

        if settings.anti_sniping_extend_minutes is not None:
            config.anti_sniping_extend_minutes = settings.anti_sniping_extend_minutes

        if settings.anti_sniping_threshold_minutes is not None:
            config.anti_sniping_threshold_minutes = settings.anti_sniping_threshold_minutes

        config.updated_at = datetime.utcnow()
        await db.commit()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="update_system_limits",
            resource_type="config",
            resource_id=str(config.config_id),
            action="Updated system limits",
            details={"changes": settings.dict(exclude_none=True)}
        )
        db.add(audit_log)
        await db.commit()

        return {
            "message": "System limits updated successfully",
            "updated_fields": settings.dict(exclude_none=True)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating system limits: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update system limits"
        )


# ============================================
# CONFIGURATION (PAYMENT GATEWAYS)
# ============================================


@router.get("/config/payments")
async def get_payment_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get payment gateway toggles, limits, fees, and monitoring settings."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "gateways": {
            "bkash": {"enabled": config.enable_bkash, "mode": config.bkash_mode},
            "nagad": {"enabled": config.enable_nagad, "mode": config.nagad_mode},
            "rocket": {"enabled": config.enable_rocket, "mode": config.rocket_mode},
            "sslcommerz": {"enabled": config.enable_sslcommerz, "mode": config.sslcommerz_mode},
        },
        "limits": {
            "min_bdt": config.topup_min_bdt,
            "max_bdt": config.topup_max_bdt,
            "daily_limit_bdt": config.topup_daily_limit_bdt,
            "monthly_limit_bdt": config.topup_monthly_limit_bdt,
        },
        "fees": {
            "mode": config.gateway_fee_mode,
            "percent": config.gateway_fee_percent,
            "flat_bdt": config.gateway_fee_flat_bdt,
        },
        "monitoring": {
            "alert_window_minutes": config.payment_alert_window_minutes,
            "failure_threshold": config.payment_alert_failure_threshold,
            "reconcile_tolerance": config.payment_reconcile_tolerance,
        },
    }


@router.get("/config/email")
async def get_email_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get email system configuration."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "enabled": config.enable_email,
        "smtp": {
            "host": config.smtp_host,
            "port": config.smtp_port,
            "username": config.smtp_username,
            "use_tls": config.smtp_use_tls,
            "use_ssl": config.smtp_use_ssl,
            "password_set": bool(config.smtp_password),
        },
        "defaults": {
            "from_email": config.default_from_email,
            "template_theme": config.email_template_theme,
        },
        "rate_limit_per_hour": config.email_rate_limit_per_hour,
    }


@router.get("/config/logging")
async def get_logging_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get logging configuration."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "level": config.log_level,
        "retention_days": config.log_retention_days,
    }


@router.get("/config/notifications")
async def get_notification_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get notification controls (push)."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "push": {
            "enabled": config.enable_push_notifications,
            "system_enabled": config.push_system_enabled,
            "marketing_enabled": config.push_marketing_enabled,
            "daily_limit": config.push_daily_limit,
            "quiet_hours": {
                "start_hour": config.push_quiet_hours_start,
                "end_hour": config.push_quiet_hours_end,
            },
        }
    }


@router.get("/config/chat")
async def get_chat_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get chat moderation and retention settings."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "max_length": config.chat_max_length,
        "profanity_filter_enabled": config.chat_profanity_filter_enabled,
        "block_keywords": config.chat_block_keywords,
        "retention_days": config.chat_retention_days,
        "pm_enabled": config.chat_pm_enabled,
        "group_max_members": config.chat_group_max_members,
    }


@router.get("/config/announcements")
async def get_announcement_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get announcement priority and rate limits."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "allow_high_priority": config.announcement_allow_high_priority,
        "max_priority": config.announcement_max_priority,
        "rate_limit_per_hour": config.announcement_rate_limit_per_hour,
        "push_webhook_url_set": bool(config.push_webhook_url),
    }


@router.get("/config/security")
async def get_security_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get authentication token lifetimes and password policy settings."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "tokens": {
            "access_token_expire_minutes": config.access_token_expire_minutes,
            "refresh_token_expire_days": config.refresh_token_expire_days,
        },
        "password_policy": {
            "min_length": config.password_min_length,
            "require_uppercase": config.password_require_uppercase,
            "require_lowercase": config.password_require_lowercase,
            "require_number": config.password_require_number,
            "require_special": config.password_require_special,
        },
        "login": {
            "max_attempts": config.login_max_attempts,
            "lockout_duration_minutes": config.lockout_duration_minutes,
            "max_sessions_per_user": config.max_sessions_per_user,
        },
    }


@router.patch("/config/security")
async def update_security_settings(
    settings: SecuritySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update token expiration and password policy settings."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if settings.access_token_expire_minutes is not None:
        if settings.access_token_expire_minutes <= 0:
            raise HTTPException(status_code=400, detail="access_token_expire_minutes must be positive")
        config.access_token_expire_minutes = settings.access_token_expire_minutes

    if settings.refresh_token_expire_days is not None:
        if settings.refresh_token_expire_days <= 0:
            raise HTTPException(status_code=400, detail="refresh_token_expire_days must be positive")
        config.refresh_token_expire_days = settings.refresh_token_expire_days

    if settings.password_min_length is not None:
        if settings.password_min_length < 6:
            raise HTTPException(status_code=400, detail="password_min_length must be at least 6")
        config.password_min_length = settings.password_min_length

    if settings.password_require_uppercase is not None:
        config.password_require_uppercase = settings.password_require_uppercase

    if settings.password_require_lowercase is not None:
        config.password_require_lowercase = settings.password_require_lowercase

    if settings.password_require_number is not None:
        config.password_require_number = settings.password_require_number

    if settings.password_require_special is not None:
        config.password_require_special = settings.password_require_special

    if settings.login_max_attempts is not None:
        if settings.login_max_attempts < 1:
            raise HTTPException(status_code=400, detail="login_max_attempts must be at least 1")
        config.login_max_attempts = settings.login_max_attempts

    if settings.lockout_duration_minutes is not None:
        if settings.lockout_duration_minutes <= 0:
            raise HTTPException(status_code=400, detail="lockout_duration_minutes must be positive")
        config.lockout_duration_minutes = settings.lockout_duration_minutes

    if settings.max_sessions_per_user is not None:
        if settings.max_sessions_per_user < 1:
            raise HTTPException(status_code=400, detail="max_sessions_per_user must be at least 1")
        config.max_sessions_per_user = settings.max_sessions_per_user

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_security_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated security settings",
        details={"changes": settings.dict(exclude_none=True)}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Security settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True)
    }


@router.patch("/config/payments")
async def update_payment_settings(
    settings: PaymentSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update payment gateway toggles and top-up limits."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # Gateway toggles
    if settings.enable_bkash is not None:
        config.enable_bkash = settings.enable_bkash
    if settings.enable_nagad is not None:
        config.enable_nagad = settings.enable_nagad
    if settings.enable_rocket is not None:
        config.enable_rocket = settings.enable_rocket
    if settings.enable_sslcommerz is not None:
        config.enable_sslcommerz = settings.enable_sslcommerz

    # Modes
    if settings.bkash_mode is not None:
        config.bkash_mode = validate_gateway_mode(settings.bkash_mode)
    if settings.nagad_mode is not None:
        config.nagad_mode = validate_gateway_mode(settings.nagad_mode)
    if settings.rocket_mode is not None:
        config.rocket_mode = validate_gateway_mode(settings.rocket_mode)
    if settings.sslcommerz_mode is not None:
        config.sslcommerz_mode = validate_gateway_mode(settings.sslcommerz_mode)

    if settings.gateway_fee_mode is not None:
        if settings.gateway_fee_mode not in {"absorb", "pass_through"}:
            raise HTTPException(status_code=400, detail="gateway_fee_mode must be 'absorb' or 'pass_through'")
        config.gateway_fee_mode = settings.gateway_fee_mode

    if settings.gateway_fee_percent is not None:
        if settings.gateway_fee_percent < 0:
            raise HTTPException(status_code=400, detail="gateway_fee_percent must be non-negative")
        config.gateway_fee_percent = settings.gateway_fee_percent

    if settings.gateway_fee_flat_bdt is not None:
        if settings.gateway_fee_flat_bdt < 0:
            raise HTTPException(status_code=400, detail="gateway_fee_flat_bdt must be non-negative")
        config.gateway_fee_flat_bdt = settings.gateway_fee_flat_bdt

    # Limits
    if settings.topup_min_bdt is not None:
        config.topup_min_bdt = settings.topup_min_bdt
    if settings.topup_max_bdt is not None:
        config.topup_max_bdt = settings.topup_max_bdt
    if settings.topup_daily_limit_bdt is not None:
        config.topup_daily_limit_bdt = settings.topup_daily_limit_bdt
    if settings.topup_monthly_limit_bdt is not None:
        config.topup_monthly_limit_bdt = settings.topup_monthly_limit_bdt

    # Monitoring / alerts
    if settings.payment_alert_window_minutes is not None:
        if settings.payment_alert_window_minutes < 5:
            raise HTTPException(status_code=400, detail="payment_alert_window_minutes must be at least 5")
        config.payment_alert_window_minutes = settings.payment_alert_window_minutes

    if settings.payment_alert_failure_threshold is not None:
        if settings.payment_alert_failure_threshold < 0:
            raise HTTPException(status_code=400, detail="payment_alert_failure_threshold must be non-negative")
        config.payment_alert_failure_threshold = settings.payment_alert_failure_threshold

    if settings.payment_reconcile_tolerance is not None:
        if settings.payment_reconcile_tolerance < 0:
            raise HTTPException(status_code=400, detail="payment_reconcile_tolerance must be non-negative")
        config.payment_reconcile_tolerance = settings.payment_reconcile_tolerance

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_payment_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated payment settings",
        details={"changes": settings.dict(exclude_none=True)}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Payment settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True)
    }


@router.patch("/config/email")
async def update_email_settings(
    settings: EmailSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update email system configuration."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if settings.enable_email is not None:
        config.enable_email = settings.enable_email

    if settings.smtp_host is not None:
        config.smtp_host = settings.smtp_host

    if settings.smtp_port is not None:
        if settings.smtp_port <= 0:
            raise HTTPException(status_code=400, detail="smtp_port must be positive")
        config.smtp_port = settings.smtp_port

    if settings.smtp_username is not None:
        config.smtp_username = settings.smtp_username

    if settings.smtp_password is not None:
        config.smtp_password = settings.smtp_password

    if settings.smtp_use_tls is not None:
        config.smtp_use_tls = settings.smtp_use_tls

    if settings.smtp_use_ssl is not None:
        config.smtp_use_ssl = settings.smtp_use_ssl

    if settings.default_from_email is not None:
        config.default_from_email = settings.default_from_email

    if settings.email_rate_limit_per_hour is not None:
        if settings.email_rate_limit_per_hour < 0:
            raise HTTPException(status_code=400, detail="email_rate_limit_per_hour must be non-negative")
        config.email_rate_limit_per_hour = settings.email_rate_limit_per_hour

    if settings.email_template_theme is not None:
        config.email_template_theme = settings.email_template_theme

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_email_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated email settings",
        details={"changes": settings.dict(exclude_none=True, exclude={"smtp_password"}), "password_updated": settings.smtp_password is not None}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Email settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True, exclude={"smtp_password"}),
        "password_updated": settings.smtp_password is not None,
    }


def _set_global_log_level(level: str) -> None:
    try:
        logging.getLogger().setLevel(level.upper())
    except Exception as e:
        logger.error(f"Failed to set global log level to {level}: {e}")


@router.patch("/config/logging")
async def update_logging_settings(
    settings: LoggingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update logging configuration (level, retention policy indicator)."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if settings.level is not None:
        level = settings.level.upper()
        if level not in allowed_levels:
            raise HTTPException(status_code=400, detail="Invalid log level")
        config.log_level = level
        _set_global_log_level(level)

    if settings.retention_days is not None:
        if settings.retention_days <= 0:
            raise HTTPException(status_code=400, detail="retention_days must be positive")
        config.log_retention_days = settings.retention_days

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_logging_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated logging settings",
        details={"changes": settings.dict(exclude_none=True)}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Logging settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True),
    }


@router.patch("/config/notifications")
async def update_notification_settings(
    settings: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update notification controls (push)."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if settings.enable_push_notifications is not None:
        config.enable_push_notifications = settings.enable_push_notifications

    if settings.push_system_enabled is not None:
        config.push_system_enabled = settings.push_system_enabled

    if settings.push_marketing_enabled is not None:
        config.push_marketing_enabled = settings.push_marketing_enabled

    if settings.push_daily_limit is not None:
        if settings.push_daily_limit < 0:
            raise HTTPException(status_code=400, detail="push_daily_limit must be non-negative")
        config.push_daily_limit = settings.push_daily_limit

    if settings.push_quiet_hours_start is not None:
        if settings.push_quiet_hours_start < 0 or settings.push_quiet_hours_start > 23:
            raise HTTPException(status_code=400, detail="push_quiet_hours_start must be between 0 and 23")
        config.push_quiet_hours_start = settings.push_quiet_hours_start

    if settings.push_quiet_hours_end is not None:
        if settings.push_quiet_hours_end < 0 or settings.push_quiet_hours_end > 23:
            raise HTTPException(status_code=400, detail="push_quiet_hours_end must be between 0 and 23")
        config.push_quiet_hours_end = settings.push_quiet_hours_end

    if settings.push_webhook_url is not None:
        config.push_webhook_url = settings.push_webhook_url

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_notification_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated notification settings",
        details={"changes": settings.dict(exclude_none=True)}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Notification settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True),
    }


@router.patch("/config/chat")
async def update_chat_settings(
    settings: ChatSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update chat moderation and retention settings."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if settings.chat_max_length is not None:
        if settings.chat_max_length <= 0:
            raise HTTPException(status_code=400, detail="chat_max_length must be positive")
        config.chat_max_length = settings.chat_max_length

    if settings.chat_profanity_filter_enabled is not None:
        config.chat_profanity_filter_enabled = settings.chat_profanity_filter_enabled

    if settings.chat_block_keywords is not None:
        config.chat_block_keywords = settings.chat_block_keywords

    if settings.chat_retention_days is not None:
        if settings.chat_retention_days <= 0:
            raise HTTPException(status_code=400, detail="chat_retention_days must be positive")
        config.chat_retention_days = settings.chat_retention_days

    if settings.chat_pm_enabled is not None:
        config.chat_pm_enabled = settings.chat_pm_enabled

    if settings.chat_group_max_members is not None:
        if settings.chat_group_max_members <= 0:
            raise HTTPException(status_code=400, detail="chat_group_max_members must be positive")
        config.chat_group_max_members = settings.chat_group_max_members

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_chat_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated chat settings",
        details={"changes": settings.dict(exclude_none=True)}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Chat settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True),
    }


@router.patch("/config/announcements")
async def update_announcement_settings(
    settings: AnnouncementSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update announcement priority and rate limits."""
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if settings.announcement_allow_high_priority is not None:
        config.announcement_allow_high_priority = settings.announcement_allow_high_priority

    if settings.announcement_max_priority is not None:
        if settings.announcement_max_priority <= 0:
            raise HTTPException(status_code=400, detail="announcement_max_priority must be positive")
        config.announcement_max_priority = settings.announcement_max_priority

    if settings.announcement_rate_limit_per_hour is not None:
        if settings.announcement_rate_limit_per_hour < 0:
            raise HTTPException(status_code=400, detail="announcement_rate_limit_per_hour must be non-negative")
        config.announcement_rate_limit_per_hour = settings.announcement_rate_limit_per_hour

    config.updated_at = datetime.utcnow()
    await db.commit()

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="update_announcement_settings",
        resource_type="config",
        resource_id=str(config.config_id),
        action="Updated announcement settings",
        details={"changes": settings.dict(exclude_none=True)}
    )
    db.add(audit_log)
    await db.commit()

    return {
        "message": "Announcement settings updated successfully",
        "updated_fields": settings.dict(exclude_none=True),
    }


@router.post("/maintenance/migrations/upgrade")
async def run_migrations_upgrade(
    revision: str = Query(default="head"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Run Alembic upgrade to the specified revision (default head)."""
    success, stdout, stderr = _run_alembic(["upgrade", revision])
    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="migration",
        resource_type="database",
        action="upgrade",
        details={"revision": revision, "success": success, "stderr": stderr[:500] if stderr else ""}
    ))
    await db.commit()
    if not success:
        raise HTTPException(status_code=500, detail=f"Alembic upgrade failed: {stderr.strip()}")
    return {"status": "ok", "revision": revision, "stdout": stdout}


@router.post("/maintenance/migrations/downgrade")
async def run_migrations_downgrade(
    steps: int = Query(default=1, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Downgrade Alembic by a number of steps (default 1)."""
    target = f"-{steps}"
    success, stdout, stderr = _run_alembic(["downgrade", target])
    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="migration",
        resource_type="database",
        action="downgrade",
        details={"steps": steps, "success": success, "stderr": stderr[:500] if stderr else ""}
    ))
    await db.commit()
    if not success:
        raise HTTPException(status_code=500, detail=f"Alembic downgrade failed: {stderr.strip()}")
    return {"status": "ok", "steps": steps, "stdout": stdout}


@router.get("/maintenance/migrations/history")
async def get_migration_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Return Alembic history (recent revisions)."""
    success, stdout, stderr = _run_alembic(["history", "-n", str(limit)])
    if not success:
        raise HTTPException(status_code=500, detail=f"Alembic history failed: {stderr.strip()}")
    return {"limit": limit, "history": stdout}


@router.post("/maintenance/backup")
async def backup_database(
    request: BackupRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Trigger a PostgreSQL backup using pg_dump (custom format)."""
    params = _get_db_dump_params()
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    fname = request.filename or f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.dump"
    target = backup_dir / fname

    cmd = [
        "pg_dump",
        "-Fc",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-d", params["database"],
        "-f", str(target),
    ]

    success, stdout, stderr = _run_pg_command(cmd, params["password"])

    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="db_backup",
        resource_type="database",
        action="backup",
        details={"file": str(target), "success": success, "stderr": stderr[:500] if stderr else ""}
    ))
    await db.commit()

    if not success:
        raise HTTPException(status_code=500, detail=f"Backup failed: {stderr.strip()}")

    return {"status": "ok", "file": str(target), "stdout": stdout}


@router.post("/maintenance/restore")
async def restore_database(
    request: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Restore database from a pg_dump custom-format file using pg_restore."""
    params = _get_db_dump_params()
    backup_dir = BASE_DIR / "backups"
    source = Path(request.filename)
    if not source.is_absolute():
        source = backup_dir / request.filename

    if not source.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    cmd = [
        "pg_restore",
        "-c",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-d", params["database"],
        str(source),
    ]

    success, stdout, stderr = _run_pg_command(cmd, params["password"])

    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="db_restore",
        resource_type="database",
        action="restore",
        details={"file": str(source), "success": success, "stderr": stderr[:500] if stderr else ""}
    ))
    await db.commit()

    if not success:
        raise HTTPException(status_code=500, detail=f"Restore failed: {stderr.strip()}")

    return {"status": "ok", "file": str(source), "stdout": stdout}


@router.get("/maintenance/health")
async def maintenance_health(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Report basic health for DB and cache."""
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        db_ok = False

    cache_ok = await cache_service.is_healthy()
    cache_stats = await cache_service.get_stats()

    pool_stats = _get_pool_stats()
    websocket_stats = connection_manager.get_stats()

    return {
        "database_ok": db_ok,
        "cache_ok": cache_ok,
        "cache_stats": cache_stats,
        "pool": pool_stats,
        "websocket_stats": websocket_stats,
    }


@router.get("/maintenance/db/pool")
async def get_db_pool_stats(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Return SQLAlchemy pool stats and a quick connectivity check."""
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB pool check failed: {e}")
        db_ok = False

    return {"database_ok": db_ok, "pool": _get_pool_stats()}


async def _run_maintenance(db: AsyncSession, sql: str) -> None:
    conn = await db.connection()
    await conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(sql))


@router.post("/maintenance/db/vacuum")
async def vacuum_database(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Run VACUUM to reclaim storage (PostgreSQL)."""
    try:
        await _run_maintenance(db, "VACUUM")
        db.add(create_audit_log(
            actor_id=admin["sub"],
            event_type="db_maintenance",
            resource_type="database",
            action="vacuum",
            details={"sql": "VACUUM"}
        ))
        await db.commit()
        return {"status": "ok", "action": "vacuum"}
    except Exception as e:
        logger.error(f"VACUUM failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="VACUUM failed")


@router.post("/maintenance/db/analyze")
async def analyze_database(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Run ANALYZE to update planner statistics."""
    try:
        await _run_maintenance(db, "ANALYZE")
        db.add(create_audit_log(
            actor_id=admin["sub"],
            event_type="db_maintenance",
            resource_type="database",
            action="analyze",
            details={"sql": "ANALYZE"}
        ))
        await db.commit()
        return {"status": "ok", "action": "analyze"}
    except Exception as e:
        logger.error(f"ANALYZE failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="ANALYZE failed")


@router.post("/maintenance/db/reindex")
async def reindex_database(
    table: Optional[str] = Query(default=None, description="Optional table name to reindex"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Run REINDEX for the whole database or a specific table."""
    if table:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise HTTPException(status_code=400, detail="Invalid table name")
        sql = f'REINDEX TABLE "{table}"'
        target = table
    else:
        sql = "REINDEX DATABASE current_database()"
        target = "database"

    try:
        await _run_maintenance(db, sql)
        db.add(create_audit_log(
            actor_id=admin["sub"],
            event_type="db_maintenance",
            resource_type="database",
            action="reindex",
            details={"target": target}
        ))
        await db.commit()
        return {"status": "ok", "action": "reindex", "target": target}
    except Exception as e:
        logger.error(f"REINDEX failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="REINDEX failed")


@router.get("/payments/events")
async def list_payment_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """List recent payment webhook/events for monitoring."""
    result = await db.execute(
        select(PaymentEvent).order_by(PaymentEvent.created_at.desc()).limit(limit)
    )
    events = result.scalars().all()
    return {
        "data": [e.to_dict() for e in events],
        "limit": limit,
    }


@router.get("/payments/events/summary")
async def summarize_payment_events(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Summarize payment events by gateway/status over a time window."""
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(
            PaymentEvent.gateway,
            PaymentEvent.status,
            func.count(PaymentEvent.event_id)
        )
        .where(PaymentEvent.created_at >= since)
        .group_by(PaymentEvent.gateway, PaymentEvent.status)
    )
    rows = result.all()
    summary = {}
    for gateway, status, count in rows:
        summary.setdefault(gateway, {})[status] = count

    return {
        "hours": hours,
        "since": since.isoformat(),
        "summary": summary,
    }


@router.get("/cache/stats")
async def get_cache_stats(
    admin: dict = Depends(require_admin)
):
    """Return cache hit/miss stats and Redis memory info."""
    healthy = await cache_service.is_healthy()
    stats = await cache_service.get_stats()
    return {
        "healthy": healthy,
        "stats": stats,
    }


@router.post("/cache/clear")
async def clear_cache(
    request: CacheClearRequest,
    admin: dict = Depends(require_admin)
):
    """Clear cache: flush all if no prefix, or delete keys by prefix."""
    if not cache_service.client:
        raise HTTPException(status_code=503, detail="Cache service unavailable")

    if request.prefix:
        deleted = await cache_service.delete_by_prefix(request.prefix)
        return {"mode": "prefix", "prefix": request.prefix, "deleted": deleted}

    success = await cache_service.flush_all()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to flush cache")
    return {"mode": "flush_all", "status": "ok"}


@router.post("/maintenance/cache/chunks/clear")
async def clear_chunk_cache(
    chunk_x: Optional[int] = Query(default=None, description="Chunk X coordinate"),
    chunk_y: Optional[int] = Query(default=None, description="Chunk Y coordinate"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Clear chunk caches: targeted (x,y) or all chunks."""
    if not cache_service.client:
        raise HTTPException(status_code=503, detail="Cache service unavailable")

    if (chunk_x is None) ^ (chunk_y is None):
        raise HTTPException(status_code=400, detail="Provide both chunk_x and chunk_y or neither")

    prefix = "chunk:"
    if chunk_x is not None and chunk_y is not None:
        prefix = f"chunk:{chunk_x}:{chunk_y}"

    deleted = await cache_service.delete_by_prefix(prefix)

    db.add(create_audit_log(
        actor_id=admin["sub"],
        event_type="cache_clear",
        resource_type="cache",
        action="clear_chunk_cache",
        details={"prefix": prefix, "deleted": deleted},
    ))
    await db.commit()

    return {
        "message": "Chunk cache cleared",
        "prefix": prefix,
        "deleted": deleted,
    }


@router.get("/payments/monitoring")
async def monitor_payments(
    window_minutes: Optional[int] = Query(default=None, ge=5, le=1440),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Monitor payment health, failures, and reconciliation gaps."""
    config_res = await db.execute(select(AdminConfig).limit(1))
    config = config_res.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    window = window_minutes or config.payment_alert_window_minutes or 60
    since = datetime.utcnow() - timedelta(minutes=window)

    event_rows = await db.execute(
        select(
            PaymentEvent.gateway,
            PaymentEvent.status,
            func.count(PaymentEvent.event_id)
        )
        .where(PaymentEvent.created_at >= since)
        .group_by(PaymentEvent.gateway, PaymentEvent.status)
    )

    event_summary: dict[str, dict[str, int]] = {}
    failure_statuses = {"error", "failed"}
    warning_statuses = {"ignored"}
    failure_total = 0
    warning_total = 0

    for gateway, status, count in event_rows:
        gateway_key = str(gateway)
        event_summary.setdefault(gateway_key, {})[status] = count
        if status in failure_statuses:
            failure_total += count
        if status in warning_statuses:
            warning_total += count

    txn_rows = await db.execute(
        select(Transaction.gateway_name, func.count(Transaction.transaction_id))
        .where(
            Transaction.created_at >= since,
            or_(
                Transaction.transaction_type == TransactionType.TOPUP,
                Transaction.transaction_type == "topup",
            ),
            or_(
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.status == "COMPLETED",
                Transaction.status == "completed",
            ),
        )
        .group_by(Transaction.gateway_name)
    )

    txn_counts = {(gateway or "unknown"): count for gateway, count in txn_rows}

    all_gateways = set(event_summary.keys()) | set(txn_counts.keys())
    reconciliation = {}
    reconcile_trigger_gateways = []
    tolerance = config.payment_reconcile_tolerance or 0

    for gateway in all_gateways:
        success_events = event_summary.get(gateway, {}).get("success", 0)
        recorded_topups = txn_counts.get(gateway, 0)
        delta = success_events - recorded_topups
        reconciliation[gateway] = {
            "success_events": success_events,
            "recorded_topups": recorded_topups,
            "delta": delta,
        }
        if abs(delta) > tolerance:
            reconcile_trigger_gateways.append(gateway)

    reconciliation_totals = {
        "success_events": sum(vals.get("success", 0) for vals in event_summary.values()),
        "recorded_topups": sum(txn_counts.values()),
    }
    reconciliation_totals["delta"] = (
        reconciliation_totals["success_events"] - reconciliation_totals["recorded_topups"]
    )

    recent_errors_result = await db.execute(
        select(PaymentEvent)
        .where(PaymentEvent.status.in_(["error"]))
        .order_by(desc(PaymentEvent.created_at))
        .limit(10)
    )
    recent_errors = recent_errors_result.scalars().all()

    return {
        "window_minutes": window,
        "since": since.isoformat(),
        "alerts": {
            "failures": {
                "threshold": config.payment_alert_failure_threshold,
                "count": failure_total,
                "warnings": warning_total,
                "triggered": failure_total >= (config.payment_alert_failure_threshold or 0),
            },
            "reconciliation": {
                "tolerance": tolerance,
                "triggered": len(reconcile_trigger_gateways) > 0,
                "gateways": reconcile_trigger_gateways,
            },
        },
        "events": {"by_gateway": event_summary},
        "reconciliation": {
            "by_gateway": reconciliation,
            "totals": reconciliation_totals,
        },
        "recent_errors": [e.to_dict() for e in recent_errors],
    }


# ============================================
# SECURITY - IP ACCESS CONTROL
# ============================================


def _serialize_ip_entry(entry):
    return {
        "entry_id": str(entry.entry_id),
        "ip": entry.ip,
        "reason": entry.reason,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "created_at": entry.created_at.isoformat()
    }


@router.get("/security/ip-access")
async def get_ip_access_lists(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get active IP blacklist and whitelist entries."""
    now = datetime.utcnow()

    blacklist_result = await db.execute(
        select(IPBlacklist).where(
            or_(IPBlacklist.expires_at.is_(None), IPBlacklist.expires_at > now)
        ).order_by(desc(IPBlacklist.created_at))
    )
    whitelist_result = await db.execute(
        select(IPWhitelist).where(
            or_(IPWhitelist.expires_at.is_(None), IPWhitelist.expires_at > now)
        ).order_by(desc(IPWhitelist.created_at))
    )

    return {
        "blacklist": [_serialize_ip_entry(entry) for entry in blacklist_result.scalars().all()],
        "whitelist": [_serialize_ip_entry(entry) for entry in whitelist_result.scalars().all()],
        "cache": ip_access_service.snapshot()
    }


@router.post("/security/ip-blacklist")
async def add_ip_blacklist_entry(
    entry: IPAccessCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Add an IP to the blacklist."""
    normalized_ip = normalize_ip_address(entry.ip)

    existing = await db.scalar(select(IPBlacklist).where(IPBlacklist.ip == normalized_ip))
    if existing:
        raise HTTPException(status_code=400, detail="IP already blacklisted")

    record = IPBlacklist(
        ip=normalized_ip,
        reason=entry.reason,
        expires_at=entry.expires_at,
        created_by_id=admin.get("sub")
    )
    db.add(record)

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="ip_blacklist_add",
        resource_type="ip_access",
        resource_id=normalized_ip,
        action="Blacklisted IP",
        details=record.reason and {"reason": record.reason}
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(record)
    ip_access_service.invalidate_cache()

    return {
        "message": "IP added to blacklist",
        "entry": _serialize_ip_entry(record)
    }


@router.delete("/security/ip-blacklist/{entry_id}")
async def remove_ip_blacklist_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Remove an IP from the blacklist."""
    record = await db.get(IPBlacklist, entry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Blacklist entry not found")

    await db.delete(record)

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="ip_blacklist_remove",
        resource_type="ip_access",
        resource_id=str(entry_id),
        action="Removed blacklisted IP",
        details={"ip": record.ip}
    )
    db.add(audit_log)

    await db.commit()
    ip_access_service.invalidate_cache()

    return {"message": "IP removed from blacklist", "entry_id": str(entry_id)}


@router.post("/security/ip-whitelist")
async def add_ip_whitelist_entry(
    entry: IPAccessCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Add an IP to the whitelist."""
    normalized_ip = normalize_ip_address(entry.ip)

    existing = await db.scalar(select(IPWhitelist).where(IPWhitelist.ip == normalized_ip))
    if existing:
        raise HTTPException(status_code=400, detail="IP already whitelisted")

    record = IPWhitelist(
        ip=normalized_ip,
        reason=entry.reason,
        expires_at=entry.expires_at,
        created_by_id=admin.get("sub")
    )
    db.add(record)

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="ip_whitelist_add",
        resource_type="ip_access",
        resource_id=normalized_ip,
        action="Whitelisted IP",
        details=record.reason and {"reason": record.reason}
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(record)
    ip_access_service.invalidate_cache()

    return {
        "message": "IP added to whitelist",
        "entry": _serialize_ip_entry(record)
    }


@router.delete("/security/ip-whitelist/{entry_id}")
async def remove_ip_whitelist_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Remove an IP from the whitelist."""
    record = await db.get(IPWhitelist, entry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Whitelist entry not found")

    await db.delete(record)

    audit_log = create_audit_log(
        actor_id=admin["sub"],
        event_type="ip_whitelist_remove",
        resource_type="ip_access",
        resource_id=str(entry_id),
        action="Removed whitelisted IP",
        details={"ip": record.ip}
    )
    db.add(audit_log)

    await db.commit()
    ip_access_service.invalidate_cache()

    return {"message": "IP removed from whitelist", "entry_id": str(entry_id)}


# ============================================
# CONTENT MODERATION
# ============================================

@router.get("/moderation/chat-messages")
async def get_chat_messages(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    user_id: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get chat messages with filters"""
    try:
        query = select(Message).join(User, Message.sender_id == User.user_id)

        # Apply filters
        if user_id:
            query = query.where(Message.sender_id == user_id)

        if search:
            query = query.where(Message.content.ilike(f"%{search}%"))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(Message.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        messages = result.scalars().all()

        return {
            "data": [
                {
                    "message_id": str(m.message_id),
                    "sender_id": str(m.sender_id),
                    "content": m.content_encrypted,
                    "created_at": m.created_at.isoformat()
                }
                for m in messages
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting chat messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch chat messages"
        )


@router.delete("/moderation/messages/{message_id}")
async def delete_message(
    message_id: str,
    reason: str = Query(..., description="Reason for deletion"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Delete an inappropriate chat message"""
    try:
        message = await db.get(Message, message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        sender_id = message.sender_id

        # Delete the message
        await db.delete(message)

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="delete_message",
            resource_type="message",
            resource_id=message_id,
            action="Deleted message",
            details={"sender_id": str(sender_id), "reason": reason}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Message deleted successfully",
            "message_id": message_id,
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )


class MuteUserRequest(BaseModel):
    duration_minutes: int  # Duration in minutes


@router.post("/moderation/users/{user_id}/mute")
async def mute_user(
    user_id: str,
    request: MuteUserRequest,
    reason: str = Query(..., description="Reason for mute"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Mute a user from chat"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Calculate mute expiration
        expires_at = datetime.utcnow() + timedelta(minutes=request.duration_minutes)

        # Create chat ban
        ban = Ban(
            user_id=user_id,
            banned_by=admin["sub"],
            reason=reason,
            ban_type="chat",
            expires_at=expires_at,
            is_active=True
        )
        db.add(ban)

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="mute_user",
            resource_type="user",
            resource_id=user_id,
            action="Muted user",
            details={"duration_minutes": request.duration_minutes, "reason": reason}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "User muted successfully",
            "user_id": user_id,
            "duration_minutes": request.duration_minutes,
            "expires_at": expires_at.isoformat(),
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error muting user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mute user"
        )


@router.get("/moderation/reports")
async def get_reports(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get user reports with filters"""
    try:
        query = select(Report)

        # Apply filters
        if status:
            query = query.where(Report.status == status)

        if resource_type:
            query = query.where(Report.resource_type == resource_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(Report.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        reports = result.scalars().all()

        return {
            "data": [
                {
                    "report_id": str(r.report_id),
                    "reporter_id": str(r.reporter_id),
                    "reported_user_id": str(r.reported_user_id) if r.reported_user_id else None,
                    "resource_type": r.resource_type,
                    "resource_id": str(r.resource_id) if r.resource_id else None,
                    "reason": r.reason,
                    "status": r.status,
                    "assigned_to": str(r.assigned_to) if r.assigned_to else None,
                    "created_at": r.created_at.isoformat(),
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None
                }
                for r in reports
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch reports"
        )


class ReportResolutionRequest(BaseModel):
    action: str  # 'resolved', 'dismissed'
    notes: Optional[str] = None


@router.patch("/moderation/reports/{report_id}")
async def resolve_report(
    report_id: str,
    request: ReportResolutionRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Resolve or dismiss a user report"""
    try:
        report = await db.get(Report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Update report
        report.status = request.action
        report.assigned_to = admin["sub"]
        report.resolution_notes = request.notes
        report.resolved_at = datetime.utcnow()

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="resolve_report",
            resource_type="report",
            resource_id=report_id,
            action=f"Report {request.action}",
            details={"resolution": request.action, "notes": request.notes}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": f"Report {request.action} successfully",
            "report_id": report_id,
            "action": request.action,
            "notes": request.notes
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving report: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve report"
        )


# ============================================
# COMMUNICATION (ANNOUNCEMENTS & BROADCAST)
# ============================================

class AnnouncementCreateRequest(BaseModel):
    title: str
    message: str
    type: str = "info"  # 'info', 'warning', 'urgent'
    target_audience: str = "all"  # 'all', 'admins', 'users'
    display_location: str = "banner"  # 'banner', 'popup', 'both'
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@router.get("/announcements")
async def get_announcements(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get all announcements"""
    try:
        query = select(Announcement)

        # Filter for active announcements if requested
        if active_only:
            now = datetime.utcnow()
            query = query.where(
                and_(
                    or_(Announcement.start_date.is_(None), Announcement.start_date <= now),
                    or_(Announcement.end_date.is_(None), Announcement.end_date >= now)
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(Announcement.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        announcements = result.scalars().all()

        return {
            "data": [
                {
                    "announcement_id": str(a.announcement_id),
                    "title": a.title,
                    "message": a.message,
                    "type": a.type,
                    "target_audience": a.target_audience,
                    "display_location": a.display_location,
                    "start_date": a.start_date.isoformat() if a.start_date else None,
                    "end_date": a.end_date.isoformat() if a.end_date else None,
                    "created_by": str(a.created_by),
                    "created_at": a.created_at.isoformat()
                }
                for a in announcements
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting announcements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch announcements"
        )


@router.post("/announcements")
async def create_announcement(
    request: AnnouncementCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Create a new announcement"""
    try:
        announcement = Announcement(
            title=request.title,
            message=request.message,
            type=request.type,
            target_audience=request.target_audience,
            display_location=request.display_location,
            start_date=request.start_date,
            end_date=request.end_date,
            created_by=admin["sub"]
        )
        db.add(announcement)

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="create_announcement",
            resource_type="announcement",
            resource_id=str(announcement.announcement_id),
            action="Created announcement",
            details={"title": request.title}
        )
        db.add(audit_log)

        await db.commit()
        await db.refresh(announcement)

        return {
            "message": "Announcement created successfully",
            "announcement_id": str(announcement.announcement_id),
            "title": announcement.title
        }

    except Exception as e:
        logger.error(f"Error creating announcement: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create announcement"
        )


@router.patch("/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    request: AnnouncementCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update an existing announcement"""
    try:
        announcement = await db.get(Announcement, announcement_id)
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")

        # Update fields
        announcement.title = request.title
        announcement.message = request.message
        announcement.type = request.type
        announcement.target_audience = request.target_audience
        announcement.display_location = request.display_location
        announcement.start_date = request.start_date
        announcement.end_date = request.end_date

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="update_announcement",
            resource_type="announcement",
            resource_id=announcement_id,
            action="Updated announcement",
            details={"title": request.title}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Announcement updated successfully",
            "announcement_id": announcement_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating announcement: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update announcement"
        )


@router.delete("/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Delete an announcement"""
    try:
        announcement = await db.get(Announcement, announcement_id)
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")

        title = announcement.title
        await db.delete(announcement)

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="delete_announcement",
            resource_type="announcement",
            resource_id=announcement_id,
            action="Deleted announcement",
            details={"title": title}
        )
        db.add(audit_log)

        await db.commit()

        return {
            "message": "Announcement deleted successfully",
            "announcement_id": announcement_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting announcement: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete announcement"
        )


class BroadcastMessageRequest(BaseModel):
    message: str
    target: str = "all"  # 'all', 'admins', 'users', 'online'
    title: Optional[str] = "System Announcement"


@router.post("/broadcast")
async def send_broadcast(
    request: BroadcastMessageRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Send broadcast message to all connected users via WebSocket"""
    try:
        from datetime import datetime
        import uuid

        # Get target users based on request.target
        target_user_ids = []

        if request.target == "online":
            # Send only to currently online users
            target_user_ids = connection_manager.get_all_online_users()
        elif request.target == "admins":
            # Get all admin user IDs who are online
            online_users = connection_manager.get_all_online_users()
            if online_users:
                user_uuids = [uuid.UUID(uid) for uid in online_users]
                result = await db.execute(
                    select(User.user_id).where(
                        and_(
                            User.user_id.in_(user_uuids),
                            User.role == "admin"
                        )
                    )
                )
                admin_ids = result.scalars().all()
                target_user_ids = [str(uid) for uid in admin_ids]
        elif request.target == "users":
            # Get all non-admin users who are online
            online_users = connection_manager.get_all_online_users()
            if online_users:
                user_uuids = [uuid.UUID(uid) for uid in online_users]
                result = await db.execute(
                    select(User.user_id).where(
                        and_(
                            User.user_id.in_(user_uuids),
                            User.role != "admin"
                        )
                    )
                )
                user_ids = result.scalars().all()
                target_user_ids = [str(uid) for uid in user_ids]
        else:
            # "all" - send to all online users
            target_user_ids = connection_manager.get_all_online_users()

        # Prepare broadcast message
        broadcast_message = {
            "type": "broadcast",
            "title": request.title,
            "message": request.message,
            "from": "System Administrator",
            "timestamp": datetime.utcnow().isoformat(),
            "target": request.target
        }

        # Send to all target users
        sent_count = 0
        for user_id in target_user_ids:
            success = await connection_manager.send_personal_message(broadcast_message, user_id)
            if success:
                sent_count += 1

        # Log action
        audit_log = create_audit_log(
            actor_id=admin["sub"],
            event_type="send_broadcast",
            resource_type="broadcast",
            resource_id=None,
            action="Sent broadcast",
            details={
                "target": request.target,
                "message_preview": request.message[:100],
                "recipients_count": sent_count
            }
        )
        db.add(audit_log)

        await db.commit()

        logger.info(f"Broadcast sent to {sent_count} users (target: {request.target})")

        return {
            "message": "Broadcast message sent successfully",
            "target": request.target,
            "recipients_count": sent_count,
            "online_users": len(connection_manager.get_all_online_users())
        }

    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send broadcast"
        )


# ============================================
# SECURITY & BANS MANAGEMENT
# ============================================

@router.get("/security/bans")
async def get_all_bans(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    active_only: bool = Query(default=True),
    ban_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get all bans in the system"""
    try:
        query = select(Ban)

        # Apply filters
        if active_only:
            query = query.where(Ban.is_active == True)

        if ban_type:
            query = query.where(Ban.ban_type == ban_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(Ban.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        bans = result.scalars().all()

        return {
            "data": [
                {
                    "ban_id": str(b.ban_id),
                    "user_id": str(b.user_id),
                    "banned_by": str(b.banned_by),
                    "reason": b.reason,
                    "ban_type": b.ban_type,
                    "expires_at": b.expires_at.isoformat() if b.expires_at else "permanent",
                    "is_active": b.is_active,
                    "created_at": b.created_at.isoformat()
                }
                for b in bans
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting bans: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch bans"
        )


@router.get("/security/logs")
async def get_security_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    action_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get security-related audit logs"""
    try:
        # Security-related actions
        security_actions = [
            "suspend_user", "unsuspend_user", "ban_user", "unban_user",
            "delete_message", "mute_user", "resolve_report"
        ]

        query = select(AuditLog).where(AuditLog.event_type.in_(security_actions))

        if action_type:
            query = query.where(AuditLog.event_type == action_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Paginate
        query = query.order_by(desc(AuditLog.created_at))
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        logs = result.scalars().all()

        return {
            "data": [
                {
                    "log_id": str(log.log_id),
                    "user_id": str(log.actor_id) if log.actor_id else None,
                    "action": log.event_type,
                    "resource_type": log.resource_type,
                    "resource_id": str(log.resource_id) if log.resource_id else None,
                    "details": str(log.details) if log.details else None,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting security logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch security logs"
        )
