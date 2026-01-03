#!/usr/bin/env python3
"""
Focused test for Biome Economy System
Just test if prices change after a purchase
"""

import requests
import time

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 15

print("=" * 60)
print("BIOME ECONOMY SYSTEM TEST")
print("=" * 60)

# Login
print("\n[1/6] Logging in as testplayer...")
resp = requests.post(f"{BASE}/auth/login", json={
    "email": "testplayer@example.com",
    "password": "TestPassword123!"
}, timeout=TIMEOUT)

if resp.status_code != 200:
    print(f"✗ Login failed: {resp.status_code}")
    exit(1)

token = resp.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}
user = resp.json().get("user")
print(f"✓ Logged in: {user['username']} ({user['balance_bdt']:,} BDT)")

# Get chunks to generate lands
print("\n[2/6] Generating lands from world...")
resp = requests.get(f"{BASE}/chunks/0/0", headers=headers, timeout=TIMEOUT)
lands = resp.json().get("lands", [])[:4]
print(f"✓ Generated {len(lands)} Plains lands")

# Record prices BEFORE
print("\n[3/6] Recording initial prices...")
resp = requests.get(f"{BASE}/lands?biome=plains&limit=10&owner=null", headers=headers, timeout=TIMEOUT)
lands_before = resp.json().get("lands", [])[:5]
prices_before = [l.get("price_base_bdt") for l in lands_before]
avg_before = sum(prices_before) / len(prices_before) if prices_before else 0
print(f"✓ Plains average price: {avg_before:.2f} BDT ({len(lands_before)} lands)")

# Create listing
print("\n[4/6] Creating marketplace listing...")
listing_data = {
    "type": "fixed_price",
    "price_bdt": 30000,
    "land_ids": [l.get("land_id") for l in lands[:2]]
}
resp = requests.post(f"{BASE}/marketplace/listings", json=listing_data, headers=headers, timeout=TIMEOUT)

if resp.status_code not in [200, 201]:
    print(f"✗ Listing failed: {resp.status_code} - {resp.text[:200]}")
    exit(1)

listing = resp.json()
listing_id = listing.get("listing_id")
price = listing.get("price_bdt")
print(f"✓ Created listing: {listing_id} for {price:,} BDT")

# Buy the listing
print("\n[5/6] Executing purchase...")
resp = requests.post(f"{BASE}/marketplace/listings/{listing_id}/buy-now", json={}, headers=headers, timeout=TIMEOUT)

if resp.status_code not in [200, 201]:
    print(f"✗ Purchase failed: {resp.status_code} - {resp.text[:200]}")
    exit(1)

print(f"✓ Purchase successful!")
time.sleep(2)

# Check prices AFTER
print("\n[6/6] Checking final prices...")
resp = requests.get(f"{BASE}/lands?biome=plains&limit=10&owner=null", headers=headers, timeout=TIMEOUT)
lands_after = resp.json().get("lands", [])[:5]
prices_after = [l.get("price_base_bdt") for l in lands_after]
avg_after = sum(prices_after) / len(prices_after) if prices_after else 0
change = avg_after - avg_before
pct = (change / avg_before * 100) if avg_before > 0 else 0

print(f"✓ Plains prices now: {avg_after:.2f} BDT")
print(f"  Change: {change:+.2f} BDT ({pct:+.2f}%)")

# Results
print("\n" + "=" * 60)
if change > 0:
    print("✓✓✓ SUCCESS: ECONOMY SYSTEM WORKING!")
    print(f"    Prices increased as expected after purchase")
else:
    print("✗✗✗ FAILED: NO PRICE CHANGE DETECTED")
    print(f"    Check backend logs for economy service errors")
print("=" * 60)

exit(0 if change > 0 else 1)
