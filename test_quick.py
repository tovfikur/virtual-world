#!/usr/bin/env python3
import requests
import json

print("1. Testing login as testplayer...")
resp = requests.post("http://localhost:8000/api/v1/auth/login", json={
    "email": "testplayer@example.com",
    "password": "TestPassword123!"
}, timeout=10)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    token = data.get("access_token")
    user = data.get("user")
    print(f"✓ Login successful!")
    print(f"  User: {user.get('username')}")
    print(f"  Balance: {user.get('balance_bdt'):,} BDT")
    print(f"  Token: {token[:50]}...\n")
    
    # Test getting chunks
    print("2. Testing world generation (getting chunk 0,0)...")
    headers = {"Authorization": f"Bearer {token}"}
    resp2 = requests.get("http://localhost:8000/api/v1/chunks/0/0", headers=headers, timeout=10)
    print(f"Status: {resp2.status_code}")
    if resp2.status_code == 200:
        lands = resp2.json().get("lands", [])
        print(f"✓ Generated {len(lands)} lands")
        if lands:
            land = lands[0]
            print(f"  Sample land: {land.get('land_id')} ({land.get('biome')} biome, {land.get('price_base_bdt')} BDT)")
    else:
        print(f"Error: {resp2.text[:200]}")
else:
    print(f"✗ Login failed!")
    print(f"Error: {resp.text}")
