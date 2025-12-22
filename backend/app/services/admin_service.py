"""
Admin service for platform controls and configuration.
Manages instruments, market status, risk parameters, and fees.
"""

from typing import List, Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from datetime import datetime, timedelta
import logging
from uuid import UUID

from app.models.instrument import Instrument
from app.models.admin import (
    AdminUser, InstrumentControl, MarketControl, RiskConfigurable, FeeConfig,
    BrokerAccount, AuditAction, AdminRole
)
from app.models.market_status import MarketStatus, MarketState

logger = logging.getLogger(__name__)


class AdminService:
    """
    Platform administrative service.
    Manages all exchange-level controls and configurations.
    """
    
    async def verify_admin_permission(
        self,
        admin_id: int,
        required_role: str,
        db: AsyncSession = None
    ) -> bool:
        """Verify admin has required permission level."""
        stmt = select(AdminUser).where(AdminUser.id == admin_id)
        result = await db.execute(stmt)
        admin = result.scalars().first()
        
        if not admin or not admin.is_active:
            return False
        
        role_hierarchy = {
            AdminRole.VIEWER: 1,
            AdminRole.OPERATOR: 2,
            AdminRole.ADMIN: 3,
            AdminRole.SUPER_ADMIN: 4
        }
        
        admin_level = role_hierarchy.get(admin.role, 0)
        required_level = role_hierarchy.get(required_role, 1)
        
        return admin_level >= required_level
    
    # ===== INSTRUMENT CONTROLS =====
    
    async def get_instrument_control(
        self,
        instrument_id: UUID,
        db: AsyncSession = None
    ) -> Optional[InstrumentControl]:
        """Get instrument control settings."""
        stmt = select(InstrumentControl).where(
            InstrumentControl.instrument_id == instrument_id
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def create_instrument_control(
        self,
        instrument_id: UUID,
        admin_id: int,
        db: AsyncSession = None,
        **kwargs
    ) -> InstrumentControl:
        """Create control settings for new instrument."""
        control = InstrumentControl(
            instrument_id=instrument_id,
            **kwargs
        )
        
        db.add(control)
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "create_instrument_control",
            "admin", f"instrument_{instrument_id}", None, control.__dict__,
            db
        )
        
        logger.info(f"Created control for instrument {instrument_id}")
        return control
    
    async def halt_instrument(
        self,
        instrument_id: UUID,
        reason: str,
        duration_minutes: Optional[int] = None,
        admin_id: int = None,
        db: AsyncSession = None
    ) -> InstrumentControl:
        """Halt trading for an instrument."""
        control = await self.get_instrument_control(instrument_id, db)
        
        if not control:
            raise ValueError(f"No control found for {instrument_id}")
        
        old_state = {
            "trading_enabled": control.is_trading_enabled,
            "halted_until": control.halted_until
        }
        
        control.is_trading_enabled = False
        control.trading_disabled_at = datetime.utcnow()
        control.trading_disabled_reason = reason
        
        if duration_minutes:
            control.halted_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "halt_instrument", "admin", f"instrument_{instrument_id}",
            old_state, {
                "trading_enabled": control.is_trading_enabled,
                "halted_until": control.halted_until,
                "reason": reason
            }, db
        )
        
        logger.warning(f"Halted instrument {instrument_id}: {reason}")
        return control
    
    async def resume_instrument(
        self,
        instrument_id: UUID,
        admin_id: int = None,
        db: AsyncSession = None
    ) -> InstrumentControl:
        """Resume trading for halted instrument."""
        control = await self.get_instrument_control(instrument_id, db)
        
        if not control:
            raise ValueError(f"No control found for {instrument_id}")
        
        old_state = {
            "trading_enabled": control.is_trading_enabled,
            "halted_until": control.halted_until
        }
        
        control.is_trading_enabled = True
        control.trading_disabled_at = None
        control.trading_disabled_reason = None
        control.halted_until = None
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "resume_instrument", "admin", f"instrument_{instrument_id}",
            old_state, {
                "trading_enabled": control.is_trading_enabled,
                "halted_until": control.halted_until
            }, db
        )
        
        logger.info(f"Resumed trading for instrument {instrument_id}")
        return control
    
    async def update_instrument_limits(
        self,
        instrument_id: UUID,
        max_order_size: Optional[float] = None,
        max_daily_volume: Optional[float] = None,
        max_leverage: Optional[float] = None,
        admin_id: int = None,
        db: AsyncSession = None
    ) -> InstrumentControl:
        """Update trading limits for instrument."""
        control = await self.get_instrument_control(instrument_id, db)
        
        if not control:
            raise ValueError(f"No control found for {instrument_id}")
        
        old_state = {
            "max_order_size": control.max_order_size,
            "max_daily_volume": control.max_daily_volume,
            "max_leverage": control.max_leverage
        }
        
        if max_order_size is not None:
            control.max_order_size = max_order_size
        if max_daily_volume is not None:
            control.max_daily_volume = max_daily_volume
        if max_leverage is not None:
            control.max_leverage = max_leverage
        
        control.updated_by = f"admin_{admin_id}"
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "update_instrument_limits", "admin", f"instrument_{instrument_id}",
            old_state, {
                "max_order_size": control.max_order_size,
                "max_daily_volume": control.max_daily_volume,
                "max_leverage": control.max_leverage
            }, db
        )
        
        logger.info(f"Updated limits for {instrument_id}")
        return control
    
    # ===== MARKET CONTROLS =====
    
    async def get_market_control(
        self,
        db: AsyncSession = None
    ) -> MarketControl:
        """Get global market control settings."""
        stmt = select(MarketControl).limit(1)
        result = await db.execute(stmt)
        control = result.scalars().first()
        
        if not control:
            # Create default
            control = MarketControl()
            db.add(control)
            await db.flush()
        
        return control
    
    async def halt_market(
        self,
        reason: str,
        duration_minutes: Optional[int] = None,
        admin_id: int = None,
        db: AsyncSession = None
    ) -> MarketControl:
        """Halt entire market."""
        control = await self.get_market_control(db)
        
        old_state = {
            "market_open": control.market_open,
            "closed_until": control.closed_until
        }
        
        control.market_open = False
        control.closed_reason = reason
        
        if duration_minutes:
            control.closed_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "halt_market", "admin", "market_global",
            old_state, {
                "market_open": control.market_open,
                "closed_reason": reason,
                "closed_until": control.closed_until
            }, db
        )
        
        logger.critical(f"MARKET HALT: {reason}")
        return control
    
    async def resume_market(
        self,
        admin_id: int = None,
        db: AsyncSession = None
    ) -> MarketControl:
        """Resume trading after market halt."""
        control = await self.get_market_control(db)
        
        old_state = {
            "market_open": control.market_open,
            "closed_until": control.closed_until
        }
        
        control.market_open = True
        control.closed_reason = None
        control.closed_until = None
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "resume_market", "admin", "market_global",
            old_state, {
                "market_open": control.market_open
            }, db
        )
        
        logger.warning(f"Market resumed")
        return control
    
    async def check_market_open(
        self,
        db: AsyncSession = None
    ) -> bool:
        """Check if market is open for trading."""
        control = await self.get_market_control(db)
        
        if not control.market_open:
            return False
        
        if control.closed_until and datetime.utcnow() < control.closed_until:
            return False
        
        return True
    
    # ===== RISK CONFIGURATION =====
    
    async def get_risk_config(
        self,
        db: AsyncSession = None
    ) -> RiskConfigurable:
        """Get risk management configuration."""
        stmt = select(RiskConfigurable).limit(1)
        result = await db.execute(stmt)
        config = result.scalars().first()
        
        if not config:
            config = RiskConfigurable()
            db.add(config)
            await db.flush()
        
        return config
    
    async def update_risk_config(
        self,
        margin_call_level: Optional[float] = None,
        liquidation_level: Optional[float] = None,
        max_leverage: Optional[float] = None,
        admin_id: int = None,
        db: AsyncSession = None,
        **kwargs
    ) -> RiskConfigurable:
        """Update risk configuration."""
        config = await self.get_risk_config(db)
        
        old_state = {
            "margin_call_level": config.margin_call_level,
            "liquidation_level": config.liquidation_level,
            "max_account_leverage": config.max_account_leverage
        }
        
        if margin_call_level is not None:
            config.margin_call_level = margin_call_level
        if liquidation_level is not None:
            config.liquidation_level = liquidation_level
        if max_leverage is not None:
            config.max_account_leverage = max_leverage
        
        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_by = f"admin_{admin_id}"
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "update_risk_config", "admin", "risk_config",
            old_state, {
                "margin_call_level": config.margin_call_level,
                "liquidation_level": config.liquidation_level,
                "max_account_leverage": config.max_account_leverage
            }, db
        )
        
        logger.info("Risk configuration updated")
        return config
    
    # ===== FEE CONFIGURATION =====
    
    async def get_fee_config(
        self,
        db: AsyncSession = None
    ) -> FeeConfig:
        """Get fee configuration."""
        stmt = select(FeeConfig).limit(1)
        result = await db.execute(stmt)
        config = result.scalars().first()
        
        if not config:
            config = FeeConfig()
            db.add(config)
            await db.flush()
        
        return config
    
    async def update_fee_config(
        self,
        maker_fee: Optional[float] = None,
        taker_fee: Optional[float] = None,
        admin_id: int = None,
        db: AsyncSession = None,
        **kwargs
    ) -> FeeConfig:
        """Update fee configuration."""
        config = await self.get_fee_config(db)
        
        old_state = {
            "default_maker_fee": config.default_maker_fee,
            "default_taker_fee": config.default_taker_fee
        }
        
        if maker_fee is not None:
            config.default_maker_fee = maker_fee
        if taker_fee is not None:
            config.default_taker_fee = taker_fee
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_by = f"admin_{admin_id}"
        
        await db.flush()
        
        # Audit
        await self._audit_action(
            admin_id, "update_fee_config", "admin", "fee_config",
            old_state, {
                "default_maker_fee": config.default_maker_fee,
                "default_taker_fee": config.default_taker_fee
            }, db
        )
        
        logger.info("Fee configuration updated")
        return config
    
    # ===== AUDIT LOGGING =====
    
    async def _audit_action(
        self,
        admin_id: int,
        action_type: str,
        category: str,
        target_id: str,
        old_value: Optional[Dict],
        new_value: Optional[Dict],
        db: AsyncSession,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """Create audit log entry."""
        audit = AuditAction(
            action_type=action_type,
            category=category,
            actor_id=admin_id,
            target_type=category,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            success=success,
            error_message=error_message
        )
        
        db.add(audit)
        await db.flush()


# Global admin service instance
_admin_service: Optional['AdminService'] = None


def get_admin_service() -> AdminService:
    """Get or create admin service."""
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service
