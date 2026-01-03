#!/usr/bin/env python3
import requests

# Test admin login
resp = requests.post("http://localhost:8000/api/v1/auth/login", json={
    "email": "demo@example.com",
    "password": "DemoPassword123!"
})
print(f"Admin login: {resp.status_code}")
print(resp.json())
