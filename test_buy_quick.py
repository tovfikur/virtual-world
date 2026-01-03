#!/usr/bin/env python3
"""Quick test to trigger economy system and check logs"""

import requests
import time

BASE = "http://localhost:8000/api/v1"

# Our test land IDs (admin owns these)
land_ids = ['e0b846de-418a-47ce-9fba-9eafa2907407', 'e726ec30-3183-4401-bebc-275aacf29ded']

print("Testing economy system...")

# Login as seller
print("1. Login as admin (will be seller)...")
resp = requests.post(f"{BASE}/auth/login", json={
    "email": "demo@example.com",
    "password": "DemoPassword123!"
}, timeout=10)

if resp.status_code != 200:
    print(f"Failed to login as seller: {resp.status_code}")
    exit(1)

seller_token = resp.json()["access_token"]
seller_headers = {"Authorization": f"Bearer {seller_token}"}

# Create listing
print("2. Create listing...")
resp = requests.post(f"{BASE}/marketplace/listings", 
                    json={"listing_type": "fixed_price", "buy_now_price_bdt": 25000, "land_ids": land_ids[:1]},
                    headers=seller_headers, timeout=10)

if resp.status_code not in [200, 201]:
    print(f"Failed to create listing: {resp.status_code} - {resp.text[:200]}")
    exit(1)

listing_id = resp.json()["listing_id"]
print(f"✓ Created listing: {listing_id}")

# Login as buyer
print("3. Login as buyer...")
resp = requests.post(f"{BASE}/auth/login", json={
    "email": "testplayer@example.com",
    "password": "TestPassword123!"
}, timeout=10)

if resp.status_code != 200:
    print(f"Failed to login as buyer")
    exit(1)

buyer_token = resp.json()["access_token"]
buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

# Buy it!
print("4. Buying listing...")
resp = requests.post(f"{BASE}/marketplace/listings/{listing_id}/buy-now",
                    json={"payment_method": "balance"}, headers=buyer_headers, timeout=10)

if resp.status_code not in [200, 201]:
    print(f"Failed to buy: {resp.status_code} - {resp.text[:200]}")
    exit(1)

print(f"✓ Purchase complete!")
print("\n" + "="*60)
print("Check backend logs for economy updates:")
print("  docker compose logs backend | findstr /i \"ECONOMY\"")
print("="*60)
