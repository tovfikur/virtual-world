"""
Test Marketplace Economy System
Creates a listing, buys it, and verifies prices changed
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost/api/v1"

def login(email, password):
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def get_owned_lands(token):
    """Get user's owned lands"""
    response = requests.get(
        f"{BASE_URL}/lands/owner/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    return []

def create_listing(token, land_ids, price_bdt):
    """Create a fixed-price marketplace listing"""
    response = requests.post(
        f"{BASE_URL}/listings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "land_ids": land_ids,
            "type": "FIXED_PRICE",
            "price_bdt": price_bdt,
            "description": "Test listing for economy system"
        }
    )
    if response.status_code == 201:
        return response.json()
    else:
        print(f"Create listing failed: {response.status_code} - {response.text}")
        return None

def buy_listing(token, listing_id):
    """Buy a listing"""
    response = requests.post(
        f"{BASE_URL}/listings/{listing_id}/buy",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Buy listing failed: {response.status_code} - {response.text}")
        return None

def get_land_price(token, land_id):
    """Get a specific land's current price"""
    response = requests.get(
        f"{BASE_URL}/lands/{land_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        land = response.json()
        return land.get("price_base_bdt", 0)
    return None

def main():
    print("=" * 60)
    print("MARKETPLACE ECONOMY TEST")
    print("=" * 60)
    
    # Step 1: Login as admin (seller)
    print("\n1. Logging in as demo admin...")
    admin_token = login("demo@example.com", "DemoPassword123!")
    if not admin_token:
        print("❌ Admin login failed!")
        return
    print("✅ Admin logged in")
    
    # Step 2: Get admin's lands
    print("\n2. Getting admin's lands...")
    admin_lands = get_owned_lands(admin_token)
    if not admin_lands or len(admin_lands) == 0:
        print("❌ Admin has no lands! Please claim some lands first.")
        return
    
    # Find a PLAINS land
    plains_land = next((l for l in admin_lands if l.get("biome") == "PLAINS"), None)
    if not plains_land:
        print("❌ No PLAINS land found! Please claim a PLAINS land first.")
        return
    
    land_id = plains_land["land_id"]
    biome = plains_land["biome"]
    original_price = plains_land.get("price_base_bdt", 0)
    
    print(f"✅ Found {biome} land: {land_id}")
    print(f"   Original price: {original_price} BDT")
    
    # Step 3: Create marketplace listing
    print("\n3. Creating marketplace listing...")
    listing_price = 50000  # 50,000 BDT
    listing = create_listing(admin_token, [land_id], listing_price)
    if not listing:
        print("❌ Failed to create listing!")
        return
    
    listing_id = listing["listing_id"]
    print(f"✅ Listing created: {listing_id}")
    print(f"   Price: {listing_price} BDT")
    
    # Step 4: Create/login test buyer
    print("\n4. Creating test buyer account...")
    # Register test buyer
    buyer_email = f"buyer{datetime.now().timestamp()}@test.com"
    buyer_password = "TestBuyer123!"
    
    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": buyer_email,
            "password": buyer_password,
            "full_name": "Test Buyer"
        }
    )
    
    if register_response.status_code in [200, 201]:
        print(f"✅ Buyer registered: {buyer_email}")
    else:
        print(f"⚠️  Buyer registration status: {register_response.status_code}")
    
    buyer_token = login(buyer_email, buyer_password)
    if not buyer_token:
        print("❌ Buyer login failed!")
        return
    print("✅ Buyer logged in")
    
    # Step 5: Give buyer money (admin endpoint needed, or skip this)
    print("\n5. Note: Buyer needs 50,000 BDT balance to purchase")
    print("   (Manual step: Add balance via admin panel or database)")
    input("   Press Enter after adding balance to buyer account...")
    
    # Step 6: Buy the listing
    print("\n6. Buying the listing...")
    purchase = buy_listing(buyer_token, listing_id)
    if not purchase:
        print("❌ Purchase failed!")
        return
    print("✅ Purchase successful!")
    
    # Step 7: Check if prices changed
    print("\n7. Checking price changes...")
    print("\nExpected changes:")
    print(f"   Purchase amount: {listing_price} BDT")
    print(f"   Per-biome share: {listing_price / 7:.2f} BDT")
    print(f"   Expected price increase per PLAINS land: ~{listing_price / (7 * 28):.2f} BDT")
    print(f"   (Assuming 28 PLAINS lands are owned)")
    
    # Check some PLAINS lands
    print("\n   Checking PLAINS land prices...")
    sample_lands = [l for l in admin_lands if l.get("biome") == "PLAINS"][:5]
    
    for land in sample_lands:
        new_price = get_land_price(admin_token, land["land_id"])
        old_price = land.get("price_base_bdt", 0)
        change = new_price - old_price if new_price else 0
        
        if change > 0:
            print(f"   ✅ Land {land['land_id'][:8]}...")
            print(f"      Old: {old_price} BDT → New: {new_price} BDT (+{change:.2f})")
        else:
            print(f"   ❌ Land {land['land_id'][:8]}... No price change (still {old_price} BDT)")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
