"""
Admin Endpoints
Dashboard, user management, system monitoring, and configuration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.land import Land
from app.models.listing import Listing
from app.models.transaction import Transaction
from app.models.chat import ChatSession
from app.models.chat import Message
from app.models.audit_log import AuditLog
from app.models.admin_config import AdminConfig
from app.services.cache_service import cache_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


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


class WorldConfigUpdate(BaseModel):
    default_world_seed: Optional[int] = None
    chunk_cache_ttl: Optional[int] = None
    max_chunks_in_memory: Optional[int] = None
    enable_maintenance_mode: Optional[bool] = None


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
                Transaction.status == "completed"
            )
        ) or 0

        # Active chat sessions
        active_chat_sessions = await db.scalar(
            select(func.count(ChatSession.session_id)).where(
                ChatSession.is_active == True
            )
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
                    Transaction.status == "completed"
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
        audit_log = AuditLog(
            user_id=admin["sub"],
            action="update_user",
            resource_type="user",
            resource_id=user_id,
            details=f"Admin updated user: {update_data.dict(exclude_none=True)}"
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
            query = query.where(AuditLog.action == action)

        if user_id:
            query = query.where(AuditLog.user_id == user_id)

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
                    "log_id": log.log_id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
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
# World Configuration
# ============================================

@router.get("/config/world")
async def get_world_config(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Get current world configuration"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            return {
                "message": "No configuration found",
                "config": None
            }

        return {
            "config_id": config.config_id,
            "default_world_seed": config.default_world_seed,
            "enable_land_trading": config.enable_land_trading,
            "enable_chat": config.enable_chat,
            "maintenance_mode": config.maintenance_mode,
            "max_land_price_bdt": config.max_land_price_bdt,
            "min_land_price_bdt": config.min_land_price_bdt,
            "auction_extend_minutes": config.auction_extend_minutes,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        }

    except Exception as e:
        logger.error(f"Error getting world config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch world configuration"
        )


@router.patch("/config/world")
async def update_world_config(
    config_update: WorldConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Update world configuration"""
    try:
        result = await db.execute(select(AdminConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            # Create new config
            config = AdminConfig(
                default_world_seed=config_update.default_world_seed or 12345
            )
            db.add(config)
        else:
            # Update existing
            if config_update.default_world_seed is not None:
                config.default_world_seed = config_update.default_world_seed

            if config_update.enable_maintenance_mode is not None:
                config.maintenance_mode = config_update.enable_maintenance_mode

            config.updated_at = datetime.utcnow()

        await db.commit()

        # Log action
        audit_log = AuditLog(
            user_id=admin["sub"],
            action="update_world_config",
            resource_type="config",
            resource_id=str(config.config_id),
            details=f"Updated config: {config_update.dict(exclude_none=True)}"
        )
        db.add(audit_log)
        await db.commit()

        return {
            "message": "World configuration updated successfully",
            "updated_fields": config_update.dict(exclude_none=True)
        }

    except Exception as e:
        logger.error(f"Error updating world config: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update world configuration"
        )
