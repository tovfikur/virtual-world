import requests
body = {"email": "demo@example.com", "password": "DemoPassword123!"}
resp1 = requests.post("http://localhost/api/v1/auth/login", json=body, timeout=10)
resp1.raise_for_status()
token1 = resp1.json()["access_token"]
resp2 = requests.post("http://localhost/api/v1/auth/login", json=body, timeout=10)
resp2.raise_for_status()
token2 = resp2.json()["access_token"]
me1 = requests.get("http://localhost/api/v1/auth/me", headers={"Authorization": f"Bearer {token1}"}, timeout=10)
me2 = requests.get("http://localhost/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"}, timeout=10)
print("token1", me1.status_code, me1.text)
print("token2", me2.status_code, me2.text)
