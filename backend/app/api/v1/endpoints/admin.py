"""
Admin Endpoints
Dashboard, user management, system monitoring, and configuration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
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
from app.models.audit_log import AuditLog, AuditEventCategory
from app.models.admin_config import AdminConfig
from app.models.ban import Ban
from app.models.announcement import Announcement
from app.models.report import Report
from app.services.cache_service import cache_service
from app.services.websocket_service import connection_manager
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
                Transaction.status == "completed"
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

        if transaction.status != "completed":
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
    base_land_price_bdt: Optional[int] = None
    forest_multiplier: Optional[float] = None
    grassland_multiplier: Optional[float] = None
    water_multiplier: Optional[float] = None
    desert_multiplier: Optional[float] = None
    snow_multiplier: Optional[float] = None
    max_land_price_bdt: Optional[int] = None
    min_land_price_bdt: Optional[int] = None
    enable_land_trading: Optional[bool] = None


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

        return {
            "transaction_fee_percent": config.transaction_fee_percent,
            "base_land_price_bdt": config.base_land_price_bdt,
            "biome_multipliers": {
                "forest": config.forest_multiplier,
                "grassland": config.grassland_multiplier,
                "water": config.water_multiplier,
                "desert": config.desert_multiplier,
                "snow": config.snow_multiplier
            },
            "max_land_price_bdt": config.max_land_price_bdt,
            "min_land_price_bdt": config.min_land_price_bdt,
            "enable_land_trading": config.enable_land_trading
        }

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

        if settings.base_land_price_bdt is not None:
            config.base_land_price_bdt = settings.base_land_price_bdt

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

        config.updated_at = datetime.utcnow()
        await db.commit()

        # Log action
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

        return {
            "message": "Economic settings updated successfully",
            "updated_fields": settings.dict(exclude_none=True)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating economic settings: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update economic settings"
        )


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
                and_(Transaction.buyer_id == user_id, Transaction.status == "completed")
            )
        )

        transactions_sold = await db.scalar(
            select(func.count(Transaction.transaction_id)).where(
                and_(Transaction.seller_id == user_id, Transaction.status == "completed")
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
            "auction_extend_minutes": config.auction_extend_minutes
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


# ============================================================================
# Trading Admin Endpoints (Instrument & Market Controls)
# ============================================================================

@router.get("/trading/instruments/{instrument_id}/control", tags=["trading-admin"], summary="Get instrument control settings")
async def get_instrument_control(
    instrument_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get trading control settings for an instrument."""
    from app.services.admin_service import get_admin_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        from uuid import UUID
        control = await admin_service.get_instrument_control(UUID(instrument_id), db)
        
        if not control:
            raise HTTPException(status_code=404, detail="Instrument control not found")
        
        return {
            "instrument_id": str(control.instrument_id),
            "is_trading_enabled": control.is_trading_enabled,
            "is_halted": control.is_halted,
            "halt_reason": control.halt_reason,
            "max_order_size": float(control.max_order_size),
            "max_daily_volume": float(control.max_daily_volume),
            "max_leverage": float(control.max_leverage),
            "circuit_breaker_enabled": control.circuit_breaker_enabled,
            "circuit_breaker_threshold": float(control.circuit_breaker_threshold),
            "updated_at": control.updated_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting instrument control: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/instruments/{instrument_id}/halt", tags=["trading-admin"], summary="Halt trading for instrument")
async def halt_instrument(
    instrument_id: str,
    duration_minutes: int = Query(..., ge=1, le=1440),
    reason: str = Query(..., min_length=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Halt trading for an instrument with specified duration."""
    from app.services.admin_service import get_admin_service
    from uuid import UUID
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        control = await admin_service.halt_instrument(
            UUID(instrument_id),
            duration_minutes,
            reason,
            current_user.id,
            db
        )
        
        # Create audit log
        create_audit_log(
            actor_id=str(current_user.id),
            event_type="halt_instrument",
            resource_type="instrument",
            resource_id=instrument_id,
            action=f"Halted for {duration_minutes} minutes",
            details={"reason": reason}
        )
        
        return {
            "status": "halted",
            "instrument_id": str(control.instrument_id),
            "halted_until": control.halted_until.isoformat() if control.halted_until else None,
            "reason": control.halt_reason
        }
    except Exception as e:
        logger.error(f"Error halting instrument: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/instruments/{instrument_id}/resume", tags=["trading-admin"], summary="Resume trading for instrument")
async def resume_instrument(
    instrument_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resume trading for a halted instrument."""
    from app.services.admin_service import get_admin_service
    from uuid import UUID
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        control = await admin_service.resume_instrument(UUID(instrument_id), current_user.id, db)
        
        return {
            "status": "resumed",
            "instrument_id": str(control.instrument_id),
            "is_trading_enabled": control.is_trading_enabled
        }
    except Exception as e:
        logger.error(f"Error resuming instrument: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/market/status", tags=["trading-admin"], summary="Get market status")
async def get_market_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get global market control status."""
    from app.services.admin_service import get_admin_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        control = await admin_service.get_market_control(db)
        
        return {
            "market_open": control.market_open,
            "market_halted": control.market_halted,
            "halt_reason": control.halt_reason,
            "order_rate_limit": control.order_rate_limit,
            "circuit_breaker_enabled": control.circuit_breaker_enabled,
            "updated_at": control.updated_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting market status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/market/halt", tags=["trading-admin"], summary="Halt entire market")
async def halt_market(
    duration_minutes: int = Query(..., ge=1, le=1440),
    reason: str = Query(..., min_length=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Halt entire market trading."""
    from app.services.admin_service import get_admin_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        control = await admin_service.halt_market(duration_minutes, reason, current_user.id, db)
        
        return {
            "status": "halted",
            "market_halted": control.market_halted,
            "reason": control.halt_reason
        }
    except Exception as e:
        logger.error(f"Error halting market: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/market/resume", tags=["trading-admin"], summary="Resume market trading")
async def resume_market(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resume market trading."""
    from app.services.admin_service import get_admin_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        control = await admin_service.resume_market(current_user.id, db)
        
        return {
            "status": "resumed",
            "market_open": control.market_open,
            "market_halted": control.market_halted
        }
    except Exception as e:
        logger.error(f"Error resuming market: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/risk/config", tags=["trading-admin"], summary="Get risk configuration")
async def get_risk_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get global risk configuration parameters."""
    from app.services.admin_service import get_admin_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        config = await admin_service.get_risk_config(db)
        
        return {
            "maintenance_margin": float(config.maintenance_margin),
            "initial_margin": float(config.initial_margin),
            "liquidation_threshold": float(config.liquidation_threshold),
            "max_position_size": float(config.max_position_size),
            "max_account_leverage": float(config.max_account_leverage)
        }
    except Exception as e:
        logger.error(f"Error getting risk config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/fees/config", tags=["trading-admin"], summary="Get fee configuration")
async def get_fee_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current fee configuration."""
    from app.services.admin_service import get_admin_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_service = get_admin_service()
    try:
        config = await admin_service.get_fee_config(db)
        
        return {
            "maker_fee": float(config.maker_fee),
            "taker_fee": float(config.taker_fee),
            "funding_fee": float(config.funding_fee),
            "swap_fee": float(config.swap_fee),
            "effective_from": config.effective_from.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting fee config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/surveillance/alerts", tags=["trading-admin"], summary="Get surveillance alerts")
async def get_surveillance_alerts(
    account_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get active surveillance alerts."""
    from app.services.surveillance_service import get_surveillance_service
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    surveillance = get_surveillance_service()
    try:
        alerts = await surveillance.get_active_alerts(account_id, severity, db)
        
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "alert_id": a.id,
                    "anomaly_type": a.anomaly_type,
                    "severity": a.severity,
                    "account_id": a.account_id,
                    "instrument_id": str(a.instrument_id) if a.instrument_id else None,
                    "description": a.description,
                    "detected_at": a.detected_at.isoformat()
                }
                for a in alerts
            ]
        }
    except Exception as e:
        logger.error(f"Error getting surveillance alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
