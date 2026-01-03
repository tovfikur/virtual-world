#!/usr/bin/env python3
"""
Direct test of the economy service to see if price changes work
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set environment to avoid validation errors
os.environ['ENVIRONMENT'] = 'development'
os.environ['JWT_SECRET_KEY'] = 'dev-secret-key-for-testing-only-12345678901234567890'
os.environ['ENCRYPTION_KEY'] = 'dev-encryption-key-for-testing-12345678901234567890'

from app.db.session import AsyncSessionLocal
from app.services.biome_land_economy_service import BiomeLandEconomyService
from sqlalchemy import select, text
from app.models.land import Land

async def test_economy():
    print("=" * 60)
    print("DIRECT ECONOMY SERVICE TEST")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        # Check how many lands exist per biome
        print("\n[1/3] Checking owned lands in database...")
        result = await db.execute(
            text("""
                SELECT biome, COUNT(*) as count, AVG(price_base_bdt) as avg_price
                FROM lands 
                WHERE owner_id IS NOT NULL
                GROUP BY biome
                ORDER BY biome
            """)
        )
        
        land_counts = {}
        for row in result:
            biome = row[0]
            count = row[1]
            avg_price = row[2]
            land_counts[biome] = {"count": count, "avg_price": avg_price}
            print(f"  {biome:10}: {count} lands @ avg {avg_price:.2f} BDT")
        
        if not land_counts:
            print("  ✗ No owned lands found! Cannot test economy system.")
            return False
        
        # Get a land to use for testing
        result = await db.execute(
            select(Land).where(Land.owner_id.isnot(None)).limit(1)
        )
        test_land = result.scalar_one_or_none()
        
        if not test_land:
            print("  ✗ No test land found")
            return False
        
        print(f"\n  Using land: {test_land.land_id} ({test_land.biome} biome)")
        
        # Record prices BEFORE
        print("\n[2/3] Recording prices BEFORE economy update...")
        prices_before = {}
        for biome in land_counts.keys():
            result = await db.execute(
                select(Land.price_base_bdt)
                .where(Land.biome == biome, Land.owner_id.isnot(None))
                .limit(5)
            )
            prices = [p[0] for p in result.fetchall()]
            if prices:
                avg = sum(prices) / len(prices)
                prices_before[biome] = avg
                print(f"  {biome:10}: {avg:.2f} BDT avg")
        
        # Call economy service
        print("\n[3/3] Calling economy service...")
        print(f"  Simulating purchase of 50,000 BDT...")
        
        economy_service = BiomeLandEconomyService()
        result = await economy_service.handle_land_purchase(
            db=db,
            land_id=str(test_land.land_id),
            amount_paid_bdt=50000,
            buyer_id="00000000-0000-0000-0000-000000000001",
            seller_id="00000000-0000-0000-0000-000000000002"
        )
        
        print(f"\n  Economy service returned:")
        print(f"    Success: {result.get('success')}")
        if result.get('success'):
            print(f"    Per-biome share: {result.get('per_biome_share'):.2f} BDT")
            
            price_changes = result.get('price_changes', {})
            if price_changes:
                print(f"\n  Price changes reported:")
                for biome, changes in price_changes.items():
                    print(f"    {biome:10}: +{changes.get('increase'):.2f} BDT ({changes.get('lands_affected')} lands)")
            else:
                print(f"    ✗ No price changes reported!")
        else:
            print(f"    ✗ Failed: {result.get('message')}")
        
        # Check prices AFTER
        print("\n  Verifying actual database changes...")
        await db.commit()  # Make sure changes are committed
        
        prices_after = {}
        any_changed = False
        
        for biome in land_counts.keys():
            result = await db.execute(
                select(Land.price_base_bdt)
                .where(Land.biome == biome, Land.owner_id.isnot(None))
                .limit(5)
            )
            prices = [p[0] for p in result.fetchall()]
            if prices:
                avg = sum(prices) / len(prices)
                prices_after[biome] = avg
                
                if biome in prices_before:
                    change = avg - prices_before[biome]
                    if abs(change) > 0.01:  # More than 1 cent change
                        print(f"    {biome:10}: {prices_before[biome]:.2f} → {avg:.2f} BDT ({change:+.2f})")
                        any_changed = True
        
        print("\n" + "=" * 60)
        if any_changed:
            print("✓✓✓ SUCCESS: PRICES CHANGED!")
            print("    The economy system is working!")
        else:
            print("✗✗✗ FAILED: NO PRICE CHANGES DETECTED")
            print("    The economy system may not be working properly.")
        print("=" * 60)
        
        return any_changed

if __name__ == "__main__":
    result = asyncio.run(test_economy())
    sys.exit(0 if result else 1)
