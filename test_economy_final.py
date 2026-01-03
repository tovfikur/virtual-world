#!/usr/bin/env python3
"""
Full end-to-end test for Biome Economy System
Tests the complete buying flow with economy price changes
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
headers_base = {"Content-Type": "application/json"}

# Set a reasonable timeout to avoid hanging
TIMEOUT = 10

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def test_economy():
    log("╔════════════════════════════════════════════════════╗")
    log("║  BIOME ECONOMY SYSTEM - FULL END-TO-END TEST      ║")
    log("╚════════════════════════════════════════════════════╝\n")
    
    # Step 1: Login as testplayer
    log("Step 1: Login as testplayer...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "testplayer@example.com",
        "password": "TestPassword123!"
    }, headers=headers_base, timeout=TIMEOUT)
    
    if resp.status_code != 200:
        log(f"✗ LOGIN FAILED: {resp.status_code}")
        log(f"  Error: {resp.text[:200]}")
        return False
    
    token = resp.json().get("access_token")
    headers = {**headers_base, "Authorization": f"Bearer {token}"}
    log(f"✓ Logged in successfully\n")
    
    # Step 2: Check player balance
    log("Step 2: Checking player balance...")
    resp = requests.get(f"{BASE_URL}/users/profile", headers=headers)
    if resp.status_code == 200:
        balance = resp.json().get("balance_bdt")
        log(f"✓ Balance: {balance:,} BDT\n")
    else:
        log(f"✗ Could not get balance\n")
    
    # Step 3: Retrieve lands from chunks to generate world
    log("Step 3: Generating lands from world chunks...")
    chunks = [
        (0, 0, "Plains"),
        (5, 5, "Desert"),
        (10, 10, "Forest"),
    ]
    
    generated_lands = {}
    for chunk_x, chunk_y, biome_name in chunks:
        resp = requests.get(f"{BASE_URL}/chunks/{chunk_x}/{chunk_y}", headers=headers)
        if resp.status_code == 200:
            lands = resp.json().get("lands", [])
            generated_lands[biome_name] = lands
            log(f"✓ Generated {len(lands)} {biome_name} lands")
        else:
            log(f"✗ Failed to generate {biome_name} lands")
    
    # Step 4: Get current prices for verification
    log("\nStep 4: Recording initial prices for all biomes...")
    prices_before = {}
    biomes = ["plains", "desert", "forest", "mountain", "beach", "snow", "ocean"]
    
    for biome in biomes:
        resp = requests.get(
            f"{BASE_URL}/lands?biome={biome}&limit=5&owner=null",
            headers=headers
        )
        if resp.status_code == 200:
            lands = resp.json().get("lands", [])
            if lands:
                prices = [l.get("price_base_bdt", 0) for l in lands]
                avg = sum(prices) / len(prices)
                prices_before[biome] = {
                    "avg": avg,
                    "count": len(lands),
                    "sample_lands": lands[:2]
                }
                log(f"  {biome:10} : {avg:>8.2f} BDT (avg of {len(lands)} lands)")
    
    # Step 5: Create a listing
    log("\nStep 5: Creating marketplace listing...")
    
    # Use lands from multiple biomes
    listing_lands = []
    for biome_name, lands in generated_lands.items():
        if lands:
            # Take first 2 lands from each biome type
            listing_lands.extend([l.get("land_id") for l in lands[:2]])
    
    if not listing_lands:
        log("✗ No lands available to list")
        return False
    
    listing_data = {
        "type": "fixed_price",
        "price_bdt": 50000,
        "land_ids": listing_lands[:4]  # Limit to 4 lands for test
    }
    
    resp = requests.post(f"{BASE_URL}/marketplace/listings",
                        json=listing_data,
                        headers=headers)
    
    if resp.status_code not in [200, 201]:
        log(f"✗ Could not create listing: {resp.status_code}")
        log(f"  Error: {resp.text[:300]}")
        return False
    
    listing = resp.json()
    listing_id = listing.get("listing_id")
    purchase_price = listing.get("price_bdt")
    log(f"✓ Created listing {listing_id}")
    log(f"  Price: {purchase_price:,} BDT")
    log(f"  Lands: {len(listing_lands)} lands\n")
    
    # Step 6: Execute purchase
    log("Step 6: Executing purchase (should trigger economy updates)...")
    log(f"  Purchase amount: {purchase_price:,} BDT")
    log(f"  Per-biome share: {purchase_price / 7:,.2f} BDT")
    log(f"  Expected impact: All biomes with owned lands should see price increases\n")
    
    resp = requests.post(f"{BASE_URL}/marketplace/listings/{listing_id}/buy-now",
                        json={},
                        headers=headers)
    
    if resp.status_code not in [200, 201]:
        log(f"✗ PURCHASE FAILED: {resp.status_code}")
        log(f"  Error: {resp.text[:300]}")
        return False
    
    transaction = resp.json()
    log(f"✓ PURCHASE SUCCESSFUL!")
    log(f"  Transaction ID: {transaction.get('transaction_id')}")
    log(f"  Buyer: {transaction.get('buyer_id', 'N/A')[:8]}...")
    log(f"  Amount: {transaction.get('amount_bdt', purchase_price):,} BDT\n")
    
    # Step 7: Wait and get new prices
    log("Step 7: Waiting for economy calculations (3 seconds)...")
    time.sleep(3)
    
    log("\nStep 8: Recording final prices and comparing...\n")
    
    prices_after = {}
    price_changes = {}
    
    for biome in biomes:
        resp = requests.get(
            f"{BASE_URL}/lands?biome={biome}&limit=5&owner=null",
            headers=headers
        )
        if resp.status_code == 200:
            lands = resp.json().get("lands", [])
            if lands and biome in prices_before:
                prices = [l.get("price_base_bdt", 0) for l in lands]
                avg_after = sum(prices) / len(prices)
                avg_before = prices_before[biome]["avg"]
                change = avg_after - avg_before
                pct = (change / avg_before * 100) if avg_before > 0 else 0
                
                prices_after[biome] = avg_after
                price_changes[biome] = {
                    "before": avg_before,
                    "after": avg_after,
                    "change": change,
                    "pct": pct
                }
                
                indicator = "✓" if change > 0 else ("✗" if change < 0 else "~")
                print(f"  {indicator} {biome:10}: {avg_before:8.2f} BDT → {avg_after:8.2f} BDT ({change:+7.2f} / {pct:+6.2f}%)")
    
    # Step 9: Summary
    log("\n╔════════════════════════════════════════════════════╗")
    log("║                    TEST SUMMARY                    ║")
    log("╚════════════════════════════════════════════════════╝\n")
    
    increased_count = sum(1 for c in price_changes.values() if c["change"] > 0)
    unchanged_count = sum(1 for c in price_changes.values() if c["change"] == 0)
    decreased_count = sum(1 for c in price_changes.values() if c["change"] < 0)
    
    log(f"Results Summary:")
    log(f"  Biomes with price increases: {increased_count}")
    log(f"  Biomes with no change: {unchanged_count}")
    log(f"  Biomes with price decreases: {decreased_count}")
    
    if increased_count > 0:
        log("\n✓ ECONOMY SYSTEM IS WORKING!")
        log("  Prices increased as expected after purchase.")
        return True
    else:
        log("\n✗ ECONOMY SYSTEM MAY HAVE ISSUES")
        log("  No price changes detected after purchase.")
        log("  Check backend logs for economy service errors:")
        log("    docker compose logs backend | grep -i 'economy\\|handle_land'")
        return False

if __name__ == "__main__":
    success = test_economy()
    exit(0 if success else 1)
