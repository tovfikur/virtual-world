#!/usr/bin/env python3
"""
Full end-to-end test for Biome Economy System
1. Login as test player with 500K BDT
2. Get chunks to generate lands (Plains and Desert)
3. Create listings from those lands
4. Check prices before purchase
5. Buy a listing
6. Check prices after purchase (should increase)
7. Verify economy system worked
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
headers_base = {"Content-Type": "application/json"}

# Use the token from our earlier login
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyNGQ5MjQ1MS0wNjIwLTRkM2MtODJlOS0yYzc3YWNhNjFlNzciLCJlbWFpbCI6InRlc3RwbGF5ZXJAZXhhbXBsZS5jb20iLCJyb2xlIjoidXNlciIsImlhdCI6MTc2NzQ0NjMzMiwiZXhwIjoxNzY3NDQ5OTMyLCJ0eXBlIjoiYWNjZXNzIiwic2Vzc2lvbl9pZCI6Im4xQTZYd2xrNFN4SldZTFhJR2RYS2tkNzRkVVRrenpWQUJvZ1hhTVl4dXcifQ.V7rT2bn8HnVXgaKEE7Hfzz-pWgeVOtpE5T9d6cTdiM0"

def get_headers():
    return {**headers_base, "Authorization": f"Bearer {TOKEN}"}

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

def test():
    log("=== BIOME ECONOMY SYSTEM - FULL END-TO-END TEST ===\n")
    
    # Step 1: Get Plains chunk to generate land
    log("Step 1: Generating Plains lands from chunk (0, 0)...")
    resp = requests.get(f"{BASE_URL}/chunks/0/0", headers=get_headers())
    if resp.status_code != 200:
        log(f"ERROR: {resp.status_code} - {resp.text}")
        return
    
    plains_lands = resp.json().get("lands", [])
    log(f"✓ Generated {len(plains_lands)} Plains lands")
    
    # Step 2: Get Desert chunk to generate land
    log("\nStep 2: Generating Desert lands from chunk (10, 10)...")
    resp = requests.get(f"{BASE_URL}/chunks/10/10", headers=get_headers())
    if resp.status_code != 200:
        log(f"ERROR: {resp.status_code}")
        return
    
    desert_lands = resp.json().get("lands", [])
    desert_lands = [l for l in desert_lands if l.get("biome") == "desert"][:3]
    log(f"✓ Found {len(desert_lands)} Desert lands")
    
    if len(plains_lands) < 2 or len(desert_lands) < 2:
        log("ERROR: Not enough lands generated for test")
        return
    
    # Step 3: Claim some lands to own them
    log("\nStep 3: Claiming lands to set them up for marketplace...")
    plains_ids = [l.get("land_id") for l in plains_lands[:2]]
    desert_ids = [l.get("land_id") for l in desert_lands[:2]]
    
    all_land_ids = plains_ids + desert_ids
    for land_id in all_land_ids:
        resp = requests.post(f"{BASE_URL}/lands/claim", 
                           json={"land_id": land_id},
                           headers=get_headers())
        if resp.status_code != 201:
            log(f"  WARNING: Could not claim land - {resp.status_code}")
    
    log(f"✓ Attempted to claim lands")
    
    # Step 4: Check prices BEFORE purchase
    log("\nStep 4: Recording land prices BEFORE purchase...")
    resp = requests.get(f"{BASE_URL}/lands?biome=plains&limit=10&owner=null",
                       headers=get_headers())
    plains_before = []
    if resp.status_code == 200:
        lands = resp.json().get("lands", [])[:5]
        avg = sum([l.get("price_base_bdt", 0) for l in lands]) / len(lands) if lands else 0
        log(f"  Plains: ~{len(lands)} unclaimed lands, avg price: {avg:.2f} BDT")
        plains_before = lands
    
    resp = requests.get(f"{BASE_URL}/lands?biome=desert&limit=10&owner=null",
                       headers=get_headers())
    desert_before = []
    if resp.status_code == 200:
        lands = resp.json().get("lands", [])[:5]
        avg = sum([l.get("price_base_bdt", 0) for l in lands]) / len(lands) if lands else 0
        log(f"  Desert: ~{len(lands)} unclaimed lands, avg price: {avg:.2f} BDT")
        desert_before = lands
    
    # Step 5: Create a test listing with multi-biome lands
    log("\nStep 5: Creating marketplace listing...")
    
    # Create listing using API
    listing_data = {
        "type": "fixed_price",
        "price_bdt": 10000,
        "land_ids": plains_ids[:1] + desert_ids[:1]  # Mix of biomes
    }
    
    resp = requests.post(f"{BASE_URL}/marketplace/listings",
                        json=listing_data,
                        headers=get_headers())
    
    if resp.status_code != 201:
        log(f"ERROR creating listing: {resp.status_code} - {resp.text[:200]}")
        return
    
    listing = resp.json()
    listing_id = listing.get("listing_id")
    price = listing.get("price_bdt")
    log(f"✓ Created listing {listing_id} for {price} BDT")
    
    # Step 6: BUY the listing
    log(f"\nStep 6: Purchasing listing (this should trigger economy adjustments)...")
    log(f"  Purchase amount: {price} BDT")
    log(f"  Per-biome share: {price / 7:.2f} BDT")
    
    resp = requests.post(f"{BASE_URL}/marketplace/listings/{listing_id}/buy-now",
                        json={},
                        headers=get_headers())
    
    if resp.status_code != 201:
        log(f"ERROR buying listing: {resp.status_code}")
        if resp.text:
            log(f"  Response: {resp.text[:300]}")
        return
    
    transaction = resp.json()
    log(f"✓ Purchase successful! Transaction ID: {transaction.get('transaction_id')}")
    
    # Wait for database updates
    time.sleep(2)
    
    # Step 7: Check prices AFTER purchase
    log("\nStep 7: Checking land prices AFTER purchase...")
    
    resp = requests.get(f"{BASE_URL}/lands?biome=plains&limit=10&owner=null",
                       headers=get_headers())
    if resp.status_code == 200:
        plains_after = resp.json().get("lands", [])[:5]
        if plains_before:
            avg_before = sum([l.get("price_base_bdt", 0) for l in plains_before]) / len(plains_before)
            avg_after = sum([l.get("price_base_bdt", 0) for l in plains_after]) / len(plains_after)
            change = avg_after - avg_before
            pct = (change / avg_before * 100) if avg_before > 0 else 0
            
            log(f"  Plains:")
            log(f"    Before: {avg_before:.2f} BDT")
            log(f"    After:  {avg_after:.2f} BDT")
            log(f"    Change: {change:+.2f} BDT ({pct:+.2f}%)")
            
            if change > 0:
                log(f"    ✓ PRICES INCREASED - ECONOMY SYSTEM WORKING!")
            elif change == 0:
                log(f"    ✗ NO PRICE CHANGE - Check if lands exist in plains biome")
            else:
                log(f"    ✗ PRICES DECREASED - UNEXPECTED")
    
    resp = requests.get(f"{BASE_URL}/lands?biome=desert&limit=10&owner=null",
                       headers=get_headers())
    if resp.status_code == 200:
        desert_after = resp.json().get("lands", [])[:5]
        if desert_before:
            avg_before = sum([l.get("price_base_bdt", 0) for l in desert_before]) / len(desert_before)
            avg_after = sum([l.get("price_base_bdt", 0) for l in desert_after]) / len(desert_after)
            change = avg_after - avg_before
            pct = (change / avg_before * 100) if avg_before > 0 else 0
            
            log(f"  Desert:")
            log(f"    Before: {avg_before:.2f} BDT")
            log(f"    After:  {avg_after:.2f} BDT")
            log(f"    Change: {change:+.2f} BDT ({pct:+.2f}%)")
            
            if change > 0:
                log(f"    ✓ PRICES INCREASED - ECONOMY SYSTEM WORKING!")
            elif change == 0:
                log(f"    ✗ NO PRICE CHANGE - Check if lands exist in desert biome")
    
    # Step 8: Check biome market statistics
    log("\nStep 8: Checking database biome market stats...")
    resp = requests.get(f"http://localhost:8000/admin/config", headers=get_headers())
    if resp.status_code == 200:
        log("✓ Admin config accessible")
    
    log("\n=== TEST COMPLETE ===")
    log("Check backend logs for economy messages:")
    log("  docker compose logs backend | grep -i 'economy\\|purchase'")

if __name__ == "__main__":
    test()
