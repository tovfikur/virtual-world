#!/usr/bin/env python3
import requests
import json
import sys

API_URL = "http://localhost:8000/api/v1"

print("=== Testing Marketplace Listing Creation in Docker ===\n")

# Step 1: Login
print("Step 1: Login as topu@gmail.com")
try:
    login_response = requests.post(
        f"{API_URL}/auth/login",
        json={"email": "topu@gmail.com", "password": "DemoPassword123!"}
    )
    print(f"Login Status: {login_response.status_code}")
    print("Login Response:")
    print(json.dumps(login_response.json(), indent=2))
    print()

    if login_response.status_code != 200:
        print("❌ Login failed!")
        sys.exit(1)

    token = login_response.json().get("access_token")
    user_id = login_response.json().get("user", {}).get("user_id")

    print(f"✅ Token: {token[:20]}...")
    print(f"✅ User ID: {user_id}\n")

except Exception as e:
    print(f"❌ Login error: {e}")
    sys.exit(1)

# Step 2: Get user's lands
print("Step 2: Get user's lands")
try:
    lands_response = requests.get(
        f"{API_URL}/users/{user_id}/lands",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 1, "limit": 5}
    )
    print(f"Lands Status: {lands_response.status_code}")
    print("Lands Response:")
    print(json.dumps(lands_response.json(), indent=2))
    print()

    if lands_response.status_code != 200:
        print("❌ Failed to get lands!")
        sys.exit(1)

    lands = lands_response.json().get("data", [])
    if not lands:
        print("❌ No lands found!")
        sys.exit(1)

    land_id = lands[0].get("land_id")
    land_coords = lands[0].get("coordinates")
    print(f"✅ Using Land ID: {land_id}")
    print(f"✅ Coordinates: ({land_coords.get('x')}, {land_coords.get('y')})\n")

except Exception as e:
    print(f"❌ Get lands error: {e}")
    sys.exit(1)

# Step 3: Create listing
print("Step 3: Create Fixed Price Listing (500 BDT)")
listing_data = {
    "land_id": land_id,
    "listing_type": "fixed_price",
    "buy_now_price_bdt": 500
}

print("Request Data:")
print(json.dumps(listing_data, indent=2))
print()

try:
    listing_response = requests.post(
        f"{API_URL}/marketplace/listings",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=listing_data
    )

    print(f"Listing Status: {listing_response.status_code}")
    print("Listing Response:")
    try:
        print(json.dumps(listing_response.json(), indent=2))
    except:
        print(listing_response.text)
    print()

    if listing_response.status_code in [200, 201]:
        print("✅ SUCCESS: Listing created successfully!")
    else:
        print(f"❌ FAILED: Listing creation failed with status {listing_response.status_code}")
        print("\nChecking backend logs...")
        import subprocess
        logs = subprocess.run(
            ["docker", "logs", "--tail", "50", "virtualworld-backend"],
            capture_output=True,
            text=True
        )
        print("=== Backend Logs ===")
        print(logs.stdout)
        if logs.stderr:
            print("=== Backend Errors ===")
            print(logs.stderr)

except Exception as e:
    print(f"❌ Create listing error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
