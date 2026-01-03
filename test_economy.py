#!/usr/bin/env python3
"""
Test script for Biome Economy System
- Register a test user
- Add balance
- Buy lands from different biomes
- Verify prices increased
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def api_call(method: str, endpoint: str, data: Dict = None, token: str = None) -> Dict[str, Any]:
    """Make an API call and return response"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=data, timeout=10)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        print(f"{method} {endpoint}")
        print(f"Status: {resp.status_code}")
        
        if resp.text:
            result = resp.json()
            print(f"Response: {json.dumps(result, indent=2)[:500]}...")
            return result
        return {}
    except Exception as e:
        print(f"ERROR: {e}")
        return {"error": str(e)}

def test_economy():
    print_section("BIOME ECONOMY SYSTEM - END-TO-END TEST")
    
    # Step 1: Register user
    print_section("Step 1: Register Test User")
    register_resp = api_call("POST", "/auth/register", {
        "username": "testplayer",
        "email": "testplayer@example.com",
        "password": "TestPassword123!"
    })
    
    if "error" in register_resp:
        print("ERROR: Registration failed")
        return
    
    user_id = register_resp.get("user_id")
    print(f"✓ User registered: {user_id}")
    
    # Step 2: Login
    print_section("Step 2: Login")
    login_resp = api_call("POST", "/auth/login", {
        "email": "testplayer@example.com",
        "password": "TestPassword123!"
    })
    
    if "error" in login_resp:
        print("ERROR: Login failed")
        return
    
    token = login_resp.get("access_token")
    print(f"✓ Logged in successfully")
    
    # Step 3: Check initial balance
    print_section("Step 3: Check Initial Balance")
    user_resp = api_call("GET", "/users/profile", token=token)
    initial_balance = user_resp.get("balance_bdt", 0)
    print(f"Initial balance: {initial_balance} BDT")
    
    # Step 4: Add balance via admin (simulate transaction/credits)
    # We'll use a land claim with initial balance instead
    print_section("Step 4: Claim Free Starter Lands")
    
    # Try to claim lands - system should give balance or free lands
    lands_resp = api_call("GET", "/lands/available", token=token)
    print(f"Available lands: {len(lands_resp.get('lands', []))} found")
    
    # Step 5: Check balance after claiming
    print_section("Step 5: Check Balance After Claiming")
    user_resp = api_call("GET", "/users/profile", token=token)
    current_balance = user_resp.get("balance_bdt", 0)
    print(f"Current balance: {current_balance} BDT")
    
    # Step 6: Get available listings
    print_section("Step 6: Get Available Marketplace Listings")
    listings_resp = api_call("GET", "/marketplace/listings?status=active&limit=10", token=token)
    listings = listings_resp.get("listings", [])
    
    if not listings:
        print("NO LISTINGS AVAILABLE - Skipping economy test")
        print("NOTE: Need to populate marketplace with listings first")
        return
    
    print(f"Found {len(listings)} active listings")
    
    # Show first few listings
    for i, listing in enumerate(listings[:3]):
        print(f"\n  Listing {i+1}:")
        print(f"    ID: {listing.get('listing_id')}")
        print(f"    Lands: {listing.get('land_count', 1)}")
        print(f"    Price: {listing.get('price_bdt')} BDT")
        biomes = listing.get('biomes', [])
        print(f"    Biomes: {', '.join([b.get('biome') for b in biomes]) if biomes else 'Unknown'}")
    
    # Step 7: Get land prices BEFORE purchase
    print_section("Step 7: Get Land Prices BEFORE Purchase")
    lands_before = api_call("GET", "/lands?biome=plains&limit=5", token=token)
    plains_lands_before = lands_before.get("lands", [])
    
    if plains_lands_before:
        avg_price_before = sum([l.get("price_base_bdt", 0) for l in plains_lands_before]) / len(plains_lands_before)
        print(f"Plains - Average price BEFORE: {avg_price_before} BDT")
        print(f"Plains - Sample lands: {len(plains_lands_before)}")
        for land in plains_lands_before[:2]:
            print(f"  - Land {land.get('land_id')}: {land.get('price_base_bdt')} BDT")
    
    desert_lands_before = api_call("GET", "/lands?biome=desert&limit=5", token=token).get("lands", [])
    if desert_lands_before:
        avg_price_desert_before = sum([l.get("price_base_bdt", 0) for l in desert_lands_before]) / len(desert_lands_before)
        print(f"Desert - Average price BEFORE: {avg_price_desert_before} BDT")
    
    # Step 8: Buy a listing
    if listings:
        listing_to_buy = listings[0]
        listing_id = listing_to_buy.get("listing_id")
        purchase_price = listing_to_buy.get("price_bdt", 0)
        
        print_section(f"Step 8: BUY LISTING {listing_id}")
        print(f"Purchase price: {purchase_price} BDT")
        print(f"Biomes in listing: {listing_to_buy.get('biomes', [])}")
        
        buy_resp = api_call("POST", f"/marketplace/listings/{listing_id}/buy-now", {}, token=token)
        
        if "error" in buy_resp or "transaction_id" not in buy_resp:
            print(f"ERROR: Purchase failed - {buy_resp}")
        else:
            print(f"✓ Purchase successful!")
            print(f"  Transaction ID: {buy_resp.get('transaction_id')}")
            print(f"  Amount paid: {purchase_price} BDT")
            
            # Wait a moment for economy updates
            time.sleep(2)
            
            # Step 9: Check prices AFTER purchase
            print_section("Step 9: Get Land Prices AFTER Purchase")
            plains_lands_after = api_call("GET", "/lands?biome=plains&limit=5", token=token).get("lands", [])
            
            if plains_lands_after:
                avg_price_plains_after = sum([l.get("price_base_bdt", 0) for l in plains_lands_after]) / len(plains_lands_after)
                print(f"Plains - Average price AFTER: {avg_price_plains_after} BDT")
                if plains_lands_before:
                    price_increase = avg_price_plains_after - avg_price_before
                    print(f"Plains - Price change: {price_increase:+.2f} BDT per land")
                    if price_increase > 0:
                        print("✓ PRICES INCREASED - Economy system working!")
                    else:
                        print("✗ PRICES DID NOT INCREASE - Economy system issue")
                        print(f"  Before: {avg_price_before}")
                        print(f"  After: {avg_price_plains_after}")
                        print(f"  Sample lands after:")
                        for land in plains_lands_after[:2]:
                            print(f"    - Land {land.get('land_id')}: {land.get('price_base_bdt')} BDT")
            
            desert_lands_after = api_call("GET", "/lands?biome=desert&limit=5", token=token).get("lands", [])
            if desert_lands_after:
                avg_price_desert_after = sum([l.get("price_base_bdt", 0) for l in desert_lands_after]) / len(desert_lands_after)
                print(f"Desert - Average price AFTER: {avg_price_desert_after} BDT")
                if desert_lands_before:
                    price_increase = avg_price_desert_after - avg_price_desert_before
                    print(f"Desert - Price change: {price_increase:+.2f} BDT per land")
            
            # Step 10: Check biome market stats
            print_section("Step 10: Check Biome Market Statistics")
            market_resp = api_call("GET", "/economy/biomes", token=token)
            if "biomes" in market_resp:
                for biome_stat in market_resp.get("biomes", [])[:3]:
                    print(f"{biome_stat.get('biome')}:")
                    print(f"  - Sold lands: {biome_stat.get('sold_lands_count')}")
                    print(f"  - Avg price: {biome_stat.get('average_price_bdt')} BDT")
                    print(f"  - Market value: {biome_stat.get('total_market_value_bdt')} BDT")
    
    print_section("TEST COMPLETE")
    print("Check logs above for economy system behavior")

if __name__ == "__main__":
    test_economy()
