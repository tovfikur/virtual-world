"""
Trading service implementing 0.5s batch price recalculation.
"""
from __future__ import annotations

from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import TradingCompany, TradingTransaction
from app.models.user import User

# Ensure enough precision
getcontext().prec = 28
PRICE_Q = Decimal("0.00000001")


def _quant_price(val: Decimal) -> Decimal:
    return val.quantize(PRICE_Q, rounding=ROUND_HALF_UP)


def _round_int(val: Decimal) -> int:
    return int(val.to_integral_value(rounding=ROUND_HALF_UP))


class TradingService:
    """
    Encapsulates batch processing for trading.
    """

    async def create_company(
        self,
        db: AsyncSession,
        name: str,
        total_shares: int,
        initial_price: Decimal,
    ) -> TradingCompany:
        company = TradingCompany(
            name=name,
            total_shares=total_shares,
            sold_shares=0,
            share_price=_quant_price(initial_price),
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company

    async def list_companies(self, db: AsyncSession) -> List[TradingCompany]:
        result = await db.execute(select(TradingCompany))
        return result.scalars().all()

    async def queue_transaction(
        self,
        db: AsyncSession,
        company_id: UUID,
        user_id: UUID,
        shares: int,
        fee_percent: Decimal,
        fee_fixed_shares: Decimal,
    ) -> TradingTransaction:
        tx = TradingTransaction(
            company_id=company_id,
            user_id=user_id,
            shares=shares,
            fee_percent=fee_percent,
            fee_fixed_shares=fee_fixed_shares,  # share-based fixed fee input
            processed=False,
        )
        db.add(tx)
        await db.commit()
        await db.refresh(tx)
        return tx

    async def _load_holdings(
        self, db: AsyncSession, company_ids: List[UUID]
    ) -> Dict[UUID, Dict[UUID, int]]:
        """
        Return holdings map: {company_id: {user_id: shares}}
        Based on processed transactions only (snapshot before the pending batch).
        """
        holdings_stmt = (
            select(
                TradingTransaction.company_id,
                TradingTransaction.user_id,
                func.coalesce(func.sum(TradingTransaction.shares), 0),
            )
            .where(
                TradingTransaction.company_id.in_(company_ids),
                TradingTransaction.processed.is_(True),
            )
            .group_by(TradingTransaction.company_id, TradingTransaction.user_id)
        )
        result = await db.execute(holdings_stmt)
        holdings_map: Dict[UUID, Dict[UUID, int]] = {}
        for comp_id, user_id, shares in result.all():
            comp_entry = holdings_map.setdefault(comp_id, {})
            comp_entry[user_id] = int(shares)
        return holdings_map

    async def _distribute_fees(
        self,
        db: AsyncSession,
        fee_pool_by_company: Dict[UUID, Decimal],
        holdings_before: Dict[UUID, Dict[UUID, int]],
    ) -> None:
        """
        Distribute collected fees to holders based on pre-batch holdings.
        """
        for company_id, fee_amount in fee_pool_by_company.items():
            holders = holdings_before.get(company_id, {})
            total_shares = sum(shares for shares in holders.values() if shares > 0)
            if fee_amount <= 0 or total_shares <= 0:
                continue
            for user_id, shares in holders.items():
                if shares <= 0:
                    continue
                payout_dec = (fee_amount * Decimal(shares)) / Decimal(total_shares)
                payout_int = _round_int(payout_dec)
                if payout_int <= 0:
                    continue
                await db.execute(
                    update(User)
                    .where(User.user_id == user_id)
                    .values(balance_bdt=User.balance_bdt + payout_int)
                )

    async def run_batch(self, db: AsyncSession) -> Tuple[int, Decimal, List[dict]]:
        """
        Process all pending transactions in one atomic batch.
        Returns (processed_count, total_net_bs, updated_companies)
        """
        pending_stmt = (
            select(TradingTransaction)
            .where(TradingTransaction.processed.is_(False))
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(pending_stmt)
        tx_rows = result.scalars().all()
        if not tx_rows:
            return 0, Decimal(0), []

        # Lock all companies to ensure consistent C and pricing across batch
        companies_stmt = select(TradingCompany).with_for_update()
        companies_result = await db.execute(companies_stmt)
        company_rows = companies_result.scalars().all()
        company_map = {c.company_id: c for c in company_rows}
        C = len(company_rows) if company_rows else 1

        company_ids = list(company_map.keys())

        # Snapshot of holdings before applying this batch (for fee distribution eligibility)
        holdings_before = await self._load_holdings(db, company_ids)

        per_company: Dict[UUID, Dict[str, Decimal]] = {}
        for tx in tx_rows:
            comp = company_map.get(tx.company_id)
            if not comp:
                continue
            entry = per_company.setdefault(
                tx.company_id, {"net_shares": Decimal(0), "fee_pool": Decimal(0)}
            )
            entry["net_shares"] += Decimal(tx.shares)
            fee_shares = Decimal(abs(tx.shares)) * Decimal(tx.fee_percent) + Decimal(tx.fee_fixed_shares or 0)
            entry["fee_pool"] += fee_shares * Decimal(comp.share_price)

        total_net_bs = sum((v["net_shares"] for v in per_company.values()), Decimal(0))

        updated = []
        for comp in company_rows:
            net = per_company.get(comp.company_id, {}).get("net_shares", Decimal(0))
            fee_pool = per_company.get(comp.company_id, {}).get("fee_pool", Decimal(0))
            ss_before = Decimal(comp.sold_shares)
            total_shares = Decimal(comp.total_shares)
            psp = Decimal(comp.share_price)

            # Clamp to treasury/outstanding
            if net > 0:
                net = min(net, total_shares - ss_before)
            if net < 0:
                net = max(net, -ss_before)

            ss_after = ss_before + net

            if ss_before > 0:
                csp = ((psp * total_net_bs) / Decimal(C)) / ss_before
                new_price = _quant_price(psp + csp)
            else:
                new_price = psp

            await db.execute(
                update(TradingCompany)
                .where(TradingCompany.company_id == comp.company_id)
                .values(
                    sold_shares=int(ss_after),
                    share_price=new_price,
                )
            )

            updated.append(
                {
                    "company_id": comp.company_id,
                    "name": comp.name,
                    "total_shares": comp.total_shares,
                    "sold_shares": int(ss_after),
                    "share_price": new_price,
                }
            )

            entry = per_company.get(comp.company_id)
            if entry is not None:
                entry["fee_pool"] = fee_pool

        # Distribute collected fees to prior holders
        fee_pool_by_company = {
            cid: data["fee_pool"] for cid, data in per_company.items() if data["fee_pool"] > 0
        }
        await self._distribute_fees(db, fee_pool_by_company, holdings_before)

        await db.execute(
            update(TradingTransaction)
            .where(TradingTransaction.tx_id.in_([t.tx_id for t in tx_rows]))
            .values(processed=True)
        )

        await db.commit()
        return len(tx_rows), _quant_price(total_net_bs), updated


trading_service = TradingService()
