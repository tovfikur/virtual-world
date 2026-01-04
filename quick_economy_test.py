"""
Quick Economy Test - Creates listing and provides instructions
"""
import requests
import sys

BASE_URL = "http://localhost/api/v1"

def login(email, password):
    response = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    return None

def get_lands(token):
    response = requests.get(f"{BASE_URL}/lands/owner/me", headers={"Authorization": f"Bearer {token}"})
    if response.status_code == 200:
        return response.json()
    return []

def create_listing(token, land_ids, price):
    response = requests.post(
        f"{BASE_URL}/listings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "land_ids": land_ids,
            "type": "FIXED_PRICE",
            "price_bdt": price,
            "description": "Economy test listing"
        }
    )
    if response.status_code == 201:
        return response.json()
    print(f"Failed: {response.status_code} - {response.text}")
    return None

def register_buyer():
    email = "testbuyer@test.com"
    password = "TestBuyer123!"
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "full_name": "Test Buyer"}
    )
    if response.status_code in [200, 201]:
        print(f"✅ Buyer registered: {email} / {password}")
    else:
        print(f"⚠️ Registration: {response.status_code} (may already exist)")
    return email, password

print("=" * 60)
print("ECONOMY SYSTEM TEST SETUP")
print("=" * 60)

# Login as admin
print("\n1. Logging in as admin...")
admin_token = login("demo@example.com", "DemoPassword123!")
if not admin_token:
    print("❌ Admin login failed!")
    sys.exit(1)
print("✅ Admin logged in")

# Get lands
print("\n2. Getting admin's lands...")
lands = get_lands(admin_token)
if not lands:
    print("❌ No lands found! Please claim some lands first.")
    sys.exit(1)

plains_lands = [l for l in lands if l.get("biome") == "PLAINS"]
if not plains_lands:
    print("❌ No PLAINS lands found! Please claim a PLAINS land first.")
    sys.exit(1)

land = plains_lands[0]
print(f"✅ Found PLAINS land: {land['land_id'][:8]}... (price: {land.get('price_base_bdt', 0)} BDT)")

# Create listing
print("\n3. Creating marketplace listing...")
listing_price = 50000
listing = create_listing(admin_token, [land["land_id"]], listing_price)
if not listing:
    print("❌ Failed to create listing!")
    sys.exit(1)

listing_id = listing["listing_id"]
print(f"✅ Listing created: {listing_id}")
print(f"   Price: {listing_price} BDT")

# Register buyer
print("\n4. Creating test buyer...")
buyer_email, buyer_password = register_buyer()

print("\n" + "=" * 60)
print("✅ SETUP COMPLETE!")
print("=" * 60)
print("\nNEXT STEPS:")
print(f"1. Run this SQL to give buyer 100K BDT:")
print(f"   docker exec virtualworld-postgres psql -U virtualworld -d virtualworld -c \"UPDATE users SET balance_bdt = 100000 WHERE email = '{buyer_email}'\"")
print()
print(f"2. Login as buyer and buy the listing:")
print(f"   Email: {buyer_email}")
print(f"   Password: {buyer_password}")
print(f"   Listing ID: {listing_id}")
print()
print("3. Check logs for economy updates:")
print("   docker logs virtualworld-backend --tail 50 | Select-String -Pattern \"🌍|💰|📈\"")
print()
print("4. Verify prices changed:")
print("   docker exec virtualworld-postgres psql -U virtualworld -d virtualworld -c \"SELECT biome, AVG(price_base_bdt) FROM lands WHERE owner_id IS NOT NULL GROUP BY biome ORDER BY biome\"")
print()
