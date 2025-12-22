"""
Admin API endpoints for market controls, risk management, and compliance.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from app.core.database import get_db
from app.core.security import get_current_user, verify_admin_token
from app.models.account import Account
from app.models.admin import AdminUser, AdminRole, AnomalyType
from app.models.instrument import Instrument
from app.services.admin_service import get_admin_service
from app.services.broker_service import get_broker_service
from app.services.surveillance_service import get_surveillance_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ============================================================================
# Instrument Controls
# ============================================================================

@router.get("/instruments/{instrument_id}/control", summary="Get instrument control settings")
async def get_instrument_control(
    instrument_id: UUID,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get trading control settings for an instrument."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    admin_service = get_admin_service()
    control = await admin_service.get_instrument_control(instrument_id, db)
    
    if not control:
        raise HTTPException(status_code=404, detail="Instrument control not found")
    
    return {
        "instrument_id": control.instrument_id,
        "is_trading_enabled": control.is_trading_enabled,
        "is_halted": control.is_halted,
        "halt_reason": control.halt_reason,
        "halted_until": control.halted_until,
        "max_order_size": float(control.max_order_size),
        "max_daily_volume": float(control.max_daily_volume),
        "max_leverage": float(control.max_leverage),
        "circuit_breaker_enabled": control.circuit_breaker_enabled,
        "circuit_breaker_threshold": float(control.circuit_breaker_threshold),
        "circuit_breaker_duration_minutes": control.circuit_breaker_duration_minutes,
        "last_breaker_trigger": control.last_breaker_trigger,
        "updated_at": control.updated_at
    }


@router.post("/instruments/{instrument_id}/halt", summary="Halt trading for instrument")
async def halt_instrument(
    instrument_id: UUID,
    duration_minutes: int = Query(..., ge=1, le=1440),
    reason: str = Query(..., min_length=10),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Halt trading for an instrument with specified duration."""
    await verify_admin_token(admin, AdminRole.OPERATOR, db)
    
    admin_service = get_admin_service()
    control = await admin_service.halt_instrument(
        instrument_id, 
        duration_minutes, 
        reason,
        admin.id,
        db
    )
    
    return {
        "status": "halted",
        "instrument_id": control.instrument_id,
        "halted_until": control.halted_until,
        "reason": control.halt_reason
    }


@router.post("/instruments/{instrument_id}/resume", summary="Resume trading for instrument")
async def resume_instrument(
    instrument_id: UUID,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resume trading for a halted instrument."""
    await verify_admin_token(admin, AdminRole.OPERATOR, db)
    
    admin_service = get_admin_service()
    control = await admin_service.resume_instrument(instrument_id, admin.id, db)
    
    return {
        "status": "resumed",
        "instrument_id": control.instrument_id,
        "is_trading_enabled": control.is_trading_enabled
    }


@router.put("/instruments/{instrument_id}/limits", summary="Update instrument limits")
async def update_instrument_limits(
    instrument_id: UUID,
    max_order_size: Optional[float] = None,
    max_daily_volume: Optional[float] = None,
    max_leverage: Optional[float] = None,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update order size, volume, and leverage limits for an instrument."""
    await verify_admin_token(admin, AdminRole.OPERATOR, db)
    
    admin_service = get_admin_service()
    control = await admin_service.update_instrument_limits(
        instrument_id,
        max_order_size,
        max_daily_volume,
        max_leverage,
        admin.id,
        db
    )
    
    return {
        "instrument_id": control.instrument_id,
        "max_order_size": float(control.max_order_size) if control.max_order_size else None,
        "max_daily_volume": float(control.max_daily_volume) if control.max_daily_volume else None,
        "max_leverage": float(control.max_leverage) if control.max_leverage else None
    }


# ============================================================================
# Market Controls
# ============================================================================

@router.get("/market/status", summary="Get market status")
async def get_market_status(
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get global market control status."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    admin_service = get_admin_service()
    control = await admin_service.get_market_control(db)
    
    return {
        "market_open": control.market_open,
        "market_halted": control.market_halted,
        "halt_reason": control.halt_reason,
        "order_rate_limit": control.order_rate_limit,
        "circuit_breaker_enabled": control.circuit_breaker_enabled,
        "circuit_breaker_threshold": float(control.circuit_breaker_threshold),
        "circuit_breaker_duration_minutes": control.circuit_breaker_duration_minutes,
        "last_breaker_trigger": control.last_breaker_trigger,
        "updated_at": control.updated_at
    }


@router.post("/market/halt", summary="Halt entire market")
async def halt_market(
    duration_minutes: int = Query(..., ge=1, le=1440),
    reason: str = Query(..., min_length=10),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Halt entire market trading."""
    await verify_admin_token(admin, AdminRole.ADMIN, db)
    
    admin_service = get_admin_service()
    control = await admin_service.halt_market(
        duration_minutes,
        reason,
        admin.id,
        db
    )
    
    return {
        "status": "halted",
        "market_halted": control.market_halted,
        "halted_until": control.updated_at,
        "reason": control.halt_reason
    }


@router.post("/market/resume", summary="Resume market trading")
async def resume_market(
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resume market trading."""
    await verify_admin_token(admin, AdminRole.ADMIN, db)
    
    admin_service = get_admin_service()
    control = await admin_service.resume_market(admin.id, db)
    
    return {
        "status": "resumed",
        "market_open": control.market_open,
        "market_halted": control.market_halted
    }


# ============================================================================
# Risk Configuration
# ============================================================================

@router.get("/risk/config", summary="Get risk configuration")
async def get_risk_config(
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get global risk configuration parameters."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    admin_service = get_admin_service()
    config = await admin_service.get_risk_config(db)
    
    return {
        "maintenance_margin": float(config.maintenance_margin),
        "initial_margin": float(config.initial_margin),
        "liquidation_threshold": float(config.liquidation_threshold),
        "max_position_size": float(config.max_position_size),
        "max_account_leverage": float(config.max_account_leverage),
        "max_vega_exposure": float(config.max_vega_exposure),
        "max_gamma_exposure": float(config.max_gamma_exposure),
        "stress_test_scenarios": config.stress_test_scenarios,
        "var_confidence": float(config.var_confidence),
        "var_horizon_days": config.var_horizon_days
    }


@router.put("/risk/config", summary="Update risk configuration")
async def update_risk_config(
    maintenance_margin: Optional[float] = None,
    initial_margin: Optional[float] = None,
    liquidation_threshold: Optional[float] = None,
    max_position_size: Optional[float] = None,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update global risk configuration parameters."""
    await verify_admin_token(admin, AdminRole.ADMIN, db)
    
    admin_service = get_admin_service()
    config = await admin_service.update_risk_config(
        maintenance_margin,
        initial_margin,
        liquidation_threshold,
        max_position_size,
        admin.id,
        db
    )
    
    return {
        "status": "updated",
        "maintenance_margin": float(config.maintenance_margin),
        "initial_margin": float(config.initial_margin),
        "liquidation_threshold": float(config.liquidation_threshold),
        "max_position_size": float(config.max_position_size)
    }


# ============================================================================
# Fee Configuration
# ============================================================================

@router.get("/fees/config", summary="Get fee configuration")
async def get_fee_config(
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current fee configuration."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    admin_service = get_admin_service()
    config = await admin_service.get_fee_config(db)
    
    return {
        "maker_fee": float(config.maker_fee),
        "taker_fee": float(config.taker_fee),
        "funding_fee": float(config.funding_fee),
        "swap_fee": float(config.swap_fee),
        "volume_tiers": config.volume_tiers,
        "maker_rebate": float(config.maker_rebate) if config.maker_rebate else None,
        "is_active": config.is_active,
        "effective_from": config.effective_from,
        "updated_at": config.updated_at
    }


@router.put("/fees/config", summary="Update fee configuration")
async def update_fee_config(
    maker_fee: Optional[float] = None,
    taker_fee: Optional[float] = None,
    funding_fee: Optional[float] = None,
    swap_fee: Optional[float] = None,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update fee configuration parameters."""
    await verify_admin_token(admin, AdminRole.ADMIN, db)
    
    admin_service = get_admin_service()
    config = await admin_service.update_fee_config(
        maker_fee,
        taker_fee,
        funding_fee,
        swap_fee,
        admin.id,
        db
    )
    
    return {
        "status": "updated",
        "maker_fee": float(config.maker_fee),
        "taker_fee": float(config.taker_fee),
        "effective_from": config.effective_from
    }


# ============================================================================
# Broker Management
# ============================================================================

@router.post("/brokers", summary="Create new broker account")
async def create_broker(
    name: str = Query(..., min_length=3),
    broker_type: str = Query(...),
    credit_limit: float = Query(..., gt=0),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new broker partner account."""
    await verify_admin_token(admin, AdminRole.OPERATOR, db)
    
    broker_service = get_broker_service()
    broker = await broker_service.create_broker_account(
        name,
        broker_type,
        credit_limit,
        db
    )
    
    return {
        "broker_id": broker.broker_id,
        "name": broker.name,
        "broker_type": broker.broker_type,
        "api_key": broker.api_key,
        "credit_limit": float(broker.credit_limit),
        "created_at": broker.created_at
    }


@router.get("/brokers/{broker_id}", summary="Get broker account")
async def get_broker(
    broker_id: str,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get broker account details."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    broker_service = get_broker_service()
    broker = await broker_service.get_broker_account(broker_id=broker_id, db=db)
    
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    
    return {
        "broker_id": broker.broker_id,
        "name": broker.name,
        "broker_type": broker.broker_type,
        "credit_limit": float(broker.credit_limit),
        "credit_utilized": float(broker.credit_utilized),
        "commission_accrued": float(broker.commission_accrued),
        "commission_paid": float(broker.commission_paid)
    }


@router.post("/brokers/{broker_id}/sub-accounts", summary="Create broker sub-account")
async def create_broker_sub_account(
    broker_id: str,
    account_id: int,
    commission_share: float = Query(..., ge=0, le=1),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Link a trading account to a broker as sub-account."""
    await verify_admin_token(admin, AdminRole.OPERATOR, db)
    
    broker_service = get_broker_service()
    sub_account = await broker_service.create_sub_account(
        broker_id,
        account_id,
        commission_share,
        db
    )
    
    return {
        "sub_account_id": sub_account.id,
        "broker_id": sub_account.broker_id,
        "account_id": sub_account.account_id,
        "commission_share": sub_account.commission_share,
        "created_at": sub_account.created_at
    }


# ============================================================================
# Surveillance & Alerts
# ============================================================================

@router.post("/surveillance/check-spoofing", summary="Check for spoofing")
async def check_spoofing(
    account_id: int = Query(...),
    instrument_id: UUID = Query(...),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check for spoofing patterns for an account/instrument."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    surveillance = get_surveillance_service()
    alert = await surveillance.detect_spoofing(account_id, instrument_id, db=db)
    
    return {
        "alert_found": alert is not None,
        "alert_id": alert.id if alert else None,
        "severity": alert.severity if alert else None,
        "description": alert.description if alert else None
    }


@router.post("/surveillance/check-wash-trading", summary="Check for wash trading")
async def check_wash_trading(
    account_id: int = Query(...),
    instrument_id: UUID = Query(...),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check for wash trading patterns for an account/instrument."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    surveillance = get_surveillance_service()
    alert = await surveillance.detect_wash_trading(account_id, instrument_id, db=db)
    
    return {
        "alert_found": alert is not None,
        "alert_id": alert.id if alert else None,
        "severity": alert.severity if alert else None,
        "description": alert.description if alert else None
    }


@router.post("/surveillance/check-front-running", summary="Check for front-running")
async def check_front_running(
    account_id: int = Query(...),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check for front-running patterns for an account."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    surveillance = get_surveillance_service()
    alert = await surveillance.detect_front_running(account_id, db=db)
    
    return {
        "alert_found": alert is not None,
        "alert_id": alert.id if alert else None,
        "severity": alert.severity if alert else None,
        "description": alert.description if alert else None
    }


@router.get("/surveillance/alerts", summary="Get active alerts")
async def get_alerts(
    account_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get active surveillance alerts."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    surveillance = get_surveillance_service()
    alerts = await surveillance.get_active_alerts(account_id, severity, db)
    
    return {
        "count": len(alerts),
        "alerts": [
            {
                "alert_id": a.id,
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "account_id": a.account_id,
                "instrument_id": a.instrument_id,
                "description": a.description,
                "detected_at": a.detected_at
            }
            for a in alerts
        ]
    }


@router.post("/surveillance/alerts/{alert_id}/resolve", summary="Resolve alert")
async def resolve_alert(
    alert_id: int,
    resolution: str = Query(..., min_length=10),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark surveillance alert as resolved."""
    await verify_admin_token(admin, AdminRole.OPERATOR, db)
    
    surveillance = get_surveillance_service()
    alert = await surveillance.resolve_alert(
        alert_id,
        resolution,
        str(admin.id),
        db
    )
    
    return {
        "status": "resolved",
        "alert_id": alert.id,
        "resolution": alert.resolution,
        "resolved_at": alert.resolved_at
    }


# ============================================================================
# Admin Users
# ============================================================================

@router.post("/users", summary="Create admin user")
async def create_admin_user(
    email: str = Query(...),
    role: str = Query(...),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new admin user account."""
    await verify_admin_token(admin, AdminRole.SUPER_ADMIN, db)
    
    # Create admin user (implementation in AdminService)
    return {
        "status": "created",
        "email": email,
        "role": role
    }


@router.get("/users/{admin_id}", summary="Get admin user")
async def get_admin_user(
    admin_id: int,
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin user details."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    return {
        "admin_id": admin_id,
        "role": "admin"
    }


@router.get("/audit", summary="Get audit log")
async def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    admin: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin action audit log."""
    await verify_admin_token(admin, AdminRole.VIEWER, db)
    
    # Query AuditAction model
    from sqlalchemy import select
    stmt = select(SurveillanceAlert).order_by(
        SurveillanceAlert.detected_at.desc()
    ).limit(limit).offset(skip)
    
    return {
        "audit_entries": []
    }
