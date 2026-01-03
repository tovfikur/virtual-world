#!/usr/bin/env python3
import requests
import json

resp = requests.post("http://localhost:8000/api/v1/auth/login", json={
    "email": "testplayer@example.com",
    "password": "TestPassword123!"
})

token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

resp = requests.get("http://localhost:8000/api/v1/chunks/0/0", headers=headers)
lands = resp.json().get("lands", [])[:1]
print(json.dumps(lands, indent=2))
