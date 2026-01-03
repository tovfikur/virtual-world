#!/usr/bin/env python3
"""Test economy system with actual buy transaction"""

import requests
import time

BASE = "http://localhost:8000/api/v1"

print("="*60)
print("TESTING ECONOMY SYSTEM - BUY/SELL PRICE CHANGES")
print("="*60)

# Wait for backend to be ready
print("\nWaiting for backend...")
for i in range(10):
    try:
        resp = requests.get("http://localhost:8000/health", timeout=2)
        if resp.status_code == 200:
            print("✓ Backend ready!")
            break
    except:
        pass
    time.sleep(2)
else:
    print("✗ Backend not ready")
    exit(1)

# Login as admin (seller)
print("\n[1/6] Login as admin (seller)...")
resp = requests.post(f"{BASE}/auth/login", json={
    "email": "demo@example.com",
    "password": "DemoPassword123!"
}, timeout=10)
if resp.status_code != 200:
    print(f"✗ Login failed: {resp.status_code}")
    exit(1)
admin_token = resp.json()["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}
print("✓ Admin logged in")

# Login as buyer (use admin for both - easier for testing)
print("\n[2/6] Login as buyer...")
resp = requests.post(f"{BASE}/auth/login", json={
    "email": "testplayer@example.com",
    "password": "TestPassword123!"
}, timeout=10)
if resp.status_code != 200:
    print(f"✗ Buyer login failed: {resp.status_code}")
    exit(1)
buyer_token = resp.json()["access_token"]
buyer_headers = {"Authorization": f"Bearer {buyer_token}"}
buyer = resp.json()["user"]
print(f"✓ Buyer logged in: {buyer['username']} ({buyer['balance_bdt']:,} BDT)")

# Check prices BEFORE
print("\n[3/6] Recording prices BEFORE purchase...")
resp = requests.get(f"{BASE}/lands?limit=100", headers=buyer_headers, timeout=10)
if resp.status_code == 200:
    all_lands = resp.json().get("lands", [])
    owned_lands = [l for l in all_lands if l.get("owner_id")]
    
    biome_prices_before = {}
    for land in owned_lands:
        biome = land["biome"]
        price = land["price_base_bdt"]
        if biome not in biome_prices_before:
            biome_prices_before[biome] = []
        biome_prices_before[biome].append(price)
    
    print(f"  Found {len(owned_lands)} owned lands:")
    for biome, prices in biome_prices_before.items():
        avg = sum(prices) / len(prices)
        print(f"    {biome:10}: {len(prices)} lands @ avg {avg:.2f} BDT")
else:
    print("  ✗ Could not fetch lands")
    biome_prices_before = {}

# Create listing
print("\n[4/6] Creating listing...")
land_ids = ['2bfac7c7-154c-46a5-a073-e06a7e3195eb']  # One plains land
resp = requests.post(f"{BASE}/marketplace/listings",
    json={"listing_type": "fixed_price", "buy_now_price_bdt": 50000, "land_ids": land_ids},
    headers=admin_headers, timeout=10)
if resp.status_code not in [200, 201]:
    print(f"✗ Listing failed: {resp.status_code} - {resp.text[:300]}")
    exit(1)
listing = resp.json()
listing_id = listing["listing_id"]
price = listing.get("buy_now_price_bdt", 50000)
print(f"✓ Created listing {listing_id} for {price:,} BDT")

# BUY!
print(f"\n[5/6] BUYING listing for {price:,} BDT...")
print(f"  Expected per-biome share: {price / 7:,.2f} BDT")
print(f"  Expected price increases in ALL biomes with owned lands")

resp = requests.post(f"{BASE}/marketplace/listings/{listing_id}/buy-now",
    json={"payment_method": "balance"}, headers=buyer_headers, timeout=10)
if resp.status_code not in [200, 201]:
    print(f"✗ Purchase failed: {resp.status_code} - {resp.text[:300]}")
    exit(1)

print(f"✓ PURCHASE SUCCESSFUL!")
time.sleep(3)  # Wait for all updates

# Check prices AFTER
print("\n[6/6] Checking prices AFTER purchase...")
resp = requests.get(f"{BASE}/lands?limit=100", headers=buyer_headers, timeout=10)
if resp.status_code == 200:
    all_lands = resp.json().get("lands", [])
    owned_lands = [l for l in all_lands if l.get("owner_id")]
    
    biome_prices_after = {}
    for land in owned_lands:
        biome = land["biome"]
        price = land["price_base_bdt"]
        if biome not in biome_prices_after:
            biome_prices_after[biome] = []
        biome_prices_after[biome].append(price)
    
    any_changed = False
    print("\n  Price comparison:")
    for biome in set(list(biome_prices_before.keys()) + list(biome_prices_after.keys())):
        before_prices = biome_prices_before.get(biome, [])
        after_prices = biome_prices_after.get(biome, [])
        
        if before_prices and after_prices:
            avg_before = sum(before_prices) / len(before_prices)
            avg_after = sum(after_prices) / len(after_prices)
            change = avg_after - avg_before
            pct = (change / avg_before * 100) if avg_before > 0 else 0
            
            indicator = "✓" if abs(change) > 0.01 else "✗"
            print(f"    {indicator} {biome:10}: {avg_before:8.2f} → {avg_after:8.2f} BDT ({change:+7.2f} / {pct:+6.2f}%)")
            
            if abs(change) > 0.01:
                any_changed = True
    
    print("\n" + "="*60)
    if any_changed:
        print("✓✓✓ SUCCESS: ECONOMY SYSTEM WORKING!")
        print("    Prices changed as expected after purchase!")
    else:
        print("✗✗✗ FAILED: NO PRICE CHANGES DETECTED")
        print("    Check backend logs:")
        print("      docker compose logs backend | findstr /i economy")
    print("="*60)

print("\nBackend logs (last 20 lines with 'economy'):")
print("  docker compose logs backend --tail 100 | findstr /i economy")
