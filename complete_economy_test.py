"""
Complete Economy Test - Automated
Creates seller listing, registers buyer, gives money, makes purchase
"""
import requests
import time
import sys

BASE_URL = "http://localhost/api/v1"

def login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password, "force_login": True})
    if r.status_code == 200:
        return r.json()["access_token"]
    else:
        print(f"   Login error: {r.status_code} - {r.text[:200]}")
        return None

def get_lands(token):
    r = requests.get(f"{BASE_URL}/lands/owner/me", headers={"Authorization": f"Bearer {token}"})
    return r.json() if r.status_code == 200 else []

def create_listing(token, land_ids, price):
    r = requests.post(
        f"{BASE_URL}/listings",
        headers={"Authorization": f"Bearer {token}"},
        json={"land_ids": land_ids, "type": "FIXED_PRICE", "price_bdt": price, "description": "Economy test"}
    )
    return r.json() if r.status_code == 201 else None

def register(email, password, name):
    r = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "full_name": name})
    return r.status_code in [200, 201]

def get_listings(token):
    r = requests.get(f"{BASE_URL}/listings?status=ACTIVE", headers={"Authorization": f"Bearer {token}"})
    return r.json().get("items", []) if r.status_code == 200 else []

def buy_listing(token, listing_id):
    r = requests.post(f"{BASE_URL}/listings/{listing_id}/buy", headers={"Authorization": f"Bearer {token}"})
    return r.json() if r.status_code == 200 else None

print("="*70)
print("COMPLETE AUTOMATED ECONOMY TEST")
print("="*70)

# Step 1: Admin login
print("\n[1/7] Logging in as admin...")
admin_token = login("demo@example.com", "DemoPassword123!")
if not admin_token:
    print("❌ Admin login failed!")
    sys.exit(1)
print("✅ Admin logged in")

# Step 2: Check admin lands
print("\n[2/7] Checking admin's lands...")
admin_lands = get_lands(admin_token)
if not admin_lands:
    print("❌ No lands! Please claim some lands first:")
    print("   1. Go to http://localhost")
    print("   2. Login as demo@example.com / DemoPassword123!")
    print("   3. Claim 5-10 lands (different biomes)")
    print("   4. Run this script again")
    sys.exit(1)

plains = [l for l in admin_lands if l.get("biome") == "PLAINS"]
if not plains:
    print("❌ No PLAINS land! Please claim at least one PLAINS land.")
    sys.exit(1)

land = plains[0]
print(f"✅ Found {len(admin_lands)} lands")
print(f"   Using PLAINS land: {land['land_id'][:8]}...")
print(f"   Current price: {land.get('price_base_bdt', 0)} BDT")

# Step 3: Create listing
print("\n[3/7] Creating marketplace listing...")
price = 50000
listing = create_listing(admin_token, [land["land_id"]], price)
if not listing:
    print("❌ Failed to create listing!")
    sys.exit(1)

listing_id = listing["listing_id"]
print(f"✅ Listing created: {listing_id[:8]}...")
print(f"   Price: {price:,} BDT")

# Step 4: Register buyer
print("\n[4/7] Registering buyer account...")
buyer_email = "economybuyer@test.com"
buyer_password = "TestBuyer123!"
register(buyer_email, buyer_password, "Economy Test Buyer")
buyer_token = login(buyer_email, buyer_password)
if not buyer_token:
    print("❌ Buyer registration/login failed!")
    sys.exit(1)
print(f"✅ Buyer registered: {buyer_email}")

# Step 5: Give buyer money
print("\n[5/7] Giving buyer 100,000 BDT...")
print("   Running SQL command...")
import subprocess
result = subprocess.run(
    ["docker", "exec", "virtualworld-postgres", "psql", "-U", "virtualworld", "-d", "virtualworld", 
     "-c", f"UPDATE users SET balance_bdt = 100000 WHERE email = '{buyer_email}'"],
    capture_output=True,
    text=True
)
if "UPDATE 1" in result.stdout:
    print("✅ Buyer funded with 100,000 BDT")
else:
    print("❌ Failed to fund buyer!")
    print(result.stdout)
    sys.exit(1)

# Step 6: Verify listing exists
print("\n[6/7] Verifying listing is active...")
time.sleep(1)
buyer_token = login(buyer_email, buyer_password)  # Re-login to refresh
listings = get_listings(buyer_token)
if not any(l["listing_id"] == listing_id for l in listings):
    print("❌ Listing not found in marketplace!")
    sys.exit(1)
print("✅ Listing is active and visible")

# Step 7: BUY THE LISTING (TRIGGER ECONOMY!)
print("\n[7/7] 💰 BUYING LISTING (THIS TRIGGERS ECONOMY)...")
print("="*70)
purchase = buy_listing(buyer_token, listing_id)
if not purchase:
    print("❌ Purchase failed!")
    sys.exit(1)

print("✅✅✅ PURCHASE COMPLETE! ✅✅✅")
print("="*70)

# Step 8: Check results
print("\n🔍 CHECKING RESULTS...")
print("\n1. Check backend logs for economy activity:")
print("   docker logs virtualworld-backend --tail 50 | Select-String -Pattern \"🌍|💰|📈\"")

print("\n2. Check if prices changed:")
print("   docker exec virtualworld-postgres psql -U virtualworld -d virtualworld -c \"SELECT biome, COUNT(*), AVG(price_base_bdt) as avg_price FROM lands WHERE owner_id IS NOT NULL GROUP BY biome ORDER BY biome\"")

print("\n3. Expected changes:")
print(f"   - Purchase amount: {price:,} BDT")
print(f"   - Per-biome share: {price/7:,.2f} BDT")
print(f"   - If {len(plains)} PLAINS lands owned: +{(price/7)/len(plains):,.2f} BDT each")

print("\n" + "="*70)
print("✅ TEST COMPLETE! Check the commands above to verify economy worked.")
print("="*70)
