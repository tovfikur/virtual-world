# Virtual Land World - Security Architecture

## Executive Summary

Virtual Land World implements defense-in-depth security across all layers: transport security (TLS), authentication (JWT), authorization (RBAC), data protection (encryption), and audit trails. This document specifies security measures for OWASP Top 10 risks, payment security, and Bangladesh regulatory compliance.

---

## Security Layers

```
┌────────────────────────────────────────────────────────────┐
│ Layer 1: Transport Security (TLS 1.3)                      │
│ - All traffic encrypted (HTTPS, WSS)                       │
│ - Certificate pinning (optional for mobile)                │
└────────────────────────────────────────────────────────────┘
                          ▼
┌────────────────────────────────────────────────────────────┐
│ Layer 2: Edge Security (Cloudflare WAF)                    │
│ - DDoS protection                                          │
│ - SQL injection / XSS filtering                           │
│ - Geo-blocking (optional)                                  │
│ - Bot detection                                            │
└────────────────────────────────────────────────────────────┘
                          ▼
┌────────────────────────────────────────────────────────────┐
│ Layer 3: Application Security                              │
│ - JWT authentication & authorization (RBAC)               │
│ - Input validation & sanitization                         │
│ - Rate limiting                                            │
│ - CSRF tokens for state-changing operations               │
└────────────────────────────────────────────────────────────┘
                          ▼
┌────────────────────────────────────────────────────────────┐
│ Layer 4: Data Security                                     │
│ - Database encryption (at-rest)                           │
│ - E2EE for sensitive messages                             │
│ - Password hashing (bcrypt)                               │
│ - Secrets management (environment variables)              │
└────────────────────────────────────────────────────────────┘
                          ▼
┌────────────────────────────────────────────────────────────┐
│ Layer 5: Audit & Compliance                                │
│ - Immutable audit logs                                     │
│ - Transaction logging                                      │
│ - Compliance monitoring                                    │
│ - Breach notification procedures                          │
└────────────────────────────────────────────────────────────┘
```

---

## Transport Security (Layer 1)

### TLS/HTTPS Configuration

All external communications use TLS 1.3 (minimum 1.2 for compatibility).

**Nginx Configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name api.virtuallandworld.com;

    # TLS certificate
    ssl_certificate /etc/letsencrypt/live/virtuallandworld.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/virtuallandworld.com/privkey.pem;

    # TLS 1.3 and 1.2 only
    ssl_protocols TLSv1.3 TLSv1.2;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Session resumption
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS (Strict Transport Security)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Redirect HTTP to HTTPS
    if ($scheme != "https") {
        return 301 https://$server_name$request_uri;
    }

    # Other security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    # Disable server signature
    server_tokens off;
}
```

### WebSocket Security (WSS)

```python
# FastAPI with WebSocket over TLS
from fastapi import WebSocket

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    # Verify TLS connection
    assert websocket.url.scheme == "wss"

    # Authenticate before accepting connection
    token = websocket.query_params.get("token")
    payload = verify_jwt_token(token)
    if not payload:
        await websocket.close(code=401)
        return

    await websocket.accept()
    # ... handle WebSocket communication
```

---

## Authentication (Layer 3)

### JWT Token Strategy

**Token Types:**

1. **Access Token (JWT)**
   - Lifespan: 1 hour
   - Contains: user_id, email, role, iat, exp
   - Stored: in-memory (browser), sent in Authorization header
   - Algorithm: HS256 (HMAC-SHA256)

2. **Refresh Token**
   - Lifespan: 7 days
   - Stored: HTTP-only, Secure, SameSite=Strict cookie
   - Used to obtain new access token without re-login
   - Rotated on each use (old token invalidated)

**Token Generation:**

```python
# app/services/auth_service.py

import jwt
import secrets
from datetime import datetime, timedelta

class AuthService:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_access_token(self, user_id: str, email: str, role: str) -> str:
        """Create short-lived access token."""
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self) -> str:
        """Create long-lived refresh token."""
        return secrets.token_urlsafe(32)

    def verify_token(self, token: str) -> dict:
        """Verify JWT signature and expiration."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
```

**Login Flow:**

```python
@app.post("/auth/login")
async def login(email: str, password: str, db: Session):
    # 1. Find user by email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. Verify password (constant-time comparison)
    if not bcrypt.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 3. Generate tokens
    access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role
    )
    refresh_token = auth_service.create_refresh_token()

    # 4. Store refresh token in Redis with TTL (7 days)
    redis.setex(
        f"refresh_token:{user.user_id}",
        7 * 24 * 60 * 60,
        refresh_token
    )

    # 5. Store session in Redis for token revocation
    redis.setex(
        f"session:{user.user_id}",
        60 * 60,  # 1 hour (matches access token TTL)
        json.dumps({"token_jti": generate_jti(), "created_at": now})
    )

    # 6. Return tokens
    response = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600
    }

    # 7. Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=7 * 24 * 60 * 60,  # 7 days
        httponly=True,
        secure=True,  # HTTPS only
        samesite="strict"
    )

    return response
```

### Token Refresh

```python
@app.post("/auth/refresh")
async def refresh_token(request: Request, db: Session):
    # 1. Extract refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    # 2. Verify refresh token exists in Redis
    user_id = None
    for key in redis.scan_iter("refresh_token:*"):
        if redis.get(key) == refresh_token:
            user_id = key.split(":")[1]
            break

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # 3. Fetch user
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # 4. Invalidate old refresh token
    redis.delete(f"refresh_token:{user_id}")

    # 5. Generate new tokens (refresh token rotation)
    new_access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role
    )
    new_refresh_token = auth_service.create_refresh_token()

    # 6. Store new refresh token
    redis.setex(
        f"refresh_token:{user_id}",
        7 * 24 * 60 * 60,
        new_refresh_token
    )

    response = {
        "access_token": new_access_token,
        "token_type": "Bearer",
        "expires_in": 3600
    }

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    return response
```

---

## Authorization (RBAC)

**Role-Based Access Control:**

```python
# app/dependencies.py

from enum import Enum
from fastapi import Depends, HTTPException

class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Extract and verify JWT token from Authorization header."""
    payload = auth_service.verify_token(token)
    return payload

def require_role(*allowed_roles: Role):
    """Dependency to enforce role requirements."""
    def check_role(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in [r.value for r in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return check_role
```

**Usage in Endpoints:**

```python
# User can only view their own profile
@app.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user["sub"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    # ... return user profile

# Only admins can access analytics
@app.get("/admin/analytics")
async def get_analytics(
    _: dict = Depends(require_role(Role.ADMIN))
):
    # ... return analytics

# Moderators can view audit logs
@app.get("/admin/audit-logs")
async def get_audit_logs(
    _: dict = Depends(require_role(Role.ADMIN, Role.MODERATOR))
):
    # ... return audit logs
```

---

## Password Security

### Hashing Strategy

```python
import bcrypt

class PasswordManager:
    COST_FACTOR = 12  # Rounds of hashing (higher = slower, more secure)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt(rounds=PasswordManager.COST_FACTOR)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hash: str) -> bool:
        """Verify password against hash (constant-time comparison)."""
        return bcrypt.checkpw(password.encode('utf-8'), hash.encode('utf-8'))
```

### Password Requirements

```python
import re

def validate_password(password: str) -> bool:
    """Enforce password requirements."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain uppercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:',.<>?]", password):
        raise ValueError("Password must contain special character")
    return True
```

---

## Data Protection

### Encryption at Rest

**Sensitive Fields:**

Encrypt sensitive database fields using envelope encryption:

```python
from cryptography.fernet import Fernet

class EncryptionManager:
    def __init__(self, master_key: str):
        self.cipher = Fernet(master_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """Encrypt sensitive data."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt sensitive data."""
        return self.cipher.decrypt(ciphertext.encode()).decode()

# Apply to User model
class User(Base):
    __tablename__ = "users"
    # ...
    email_encrypted = Column(String, nullable=False)

    @hybrid_property
    def email(self):
        return encryption_manager.decrypt(self.email_encrypted)

    @email.setter
    def email(self, value):
        self.email_encrypted = encryption_manager.encrypt(value)
```

### Message Encryption (E2EE)

**Client-Side Implementation (WebCrypto API):**

```javascript
// app/static/encryption.js

class MessageEncryption {
    constructor() {
        this.sharedKey = null;
    }

    // Generate ephemeral keypair for ECDH key exchange
    async generateKeypair() {
        return await window.crypto.subtle.generateKey(
            {
                name: "ECDH",
                namedCurve: "P-256"
            },
            false,  // Not extractable (stays in browser)
            ["deriveBits", "deriveKey"]
        );
    }

    // Encrypt message using AES-256-GCM
    async encryptMessage(message, sharedKey) {
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const encoder = new TextEncoder();
        const data = encoder.encode(message);

        const encryptedData = await window.crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv: iv,
                additionalData: new TextEncoder().encode("message")
            },
            sharedKey,
            data
        );

        return {
            ciphertext: this.arrayBufferToBase64(encryptedData),
            iv: this.arrayBufferToBase64(iv)
        };
    }

    // Decrypt message
    async decryptMessage(ciphertext, iv, sharedKey) {
        const decryptedData = await window.crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: this.base64ToArrayBuffer(iv),
                additionalData: new TextEncoder().encode("message")
            },
            sharedKey,
            this.base64ToArrayBuffer(ciphertext)
        );

        const decoder = new TextDecoder();
        return decoder.decode(decryptedData);
    }

    arrayBufferToBase64(buffer) {
        return btoa(String.fromCharCode(...new Uint8Array(buffer)));
    }

    base64ToArrayBuffer(base64) {
        const binaryString = atob(base64);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    }
}
```

**Key Exchange (ECDH):**

```javascript
// Establish shared key between two clients
async establishSharedKey(otherPartyPublicKey) {
    const sharedKey = await window.crypto.subtle.deriveKey(
        {
            name: "ECDH",
            public: otherPartyPublicKey
        },
        this.privateKey,
        {
            name: "AES-GCM",
            length: 256
        },
        false,  // Not extractable
        ["encrypt", "decrypt"]
    );

    return sharedKey;
}
```

---

## Payment Security

### Webhook Signature Verification

```python
import hmac
import hashlib

class PaymentWebhookValidator:
    def __init__(self, gateway_secrets: dict):
        self.secrets = gateway_secrets

    def verify_signature(self, gateway_name: str, payload: str, signature: str) -> bool:
        """Verify webhook signature using HMAC-SHA256."""
        secret = self.secrets.get(gateway_name)
        if not secret:
            return False

        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(expected_signature, signature)

    def verify_and_process_webhook(self, gateway_name: str, payload: dict, signature: str) -> bool:
        """Verify and process payment webhook."""
        payload_str = json.dumps(payload, sort_keys=True)

        if not self.verify_signature(gateway_name, payload_str, signature):
            logger.warning(f"Invalid webhook signature from {gateway_name}")
            return False

        # Process payment
        transaction_id = payload["orderID"]
        amount = payload["amount"]

        # Check idempotency: ensure transaction only processed once
        if redis.exists(f"webhook_processed:{transaction_id}"):
            logger.info(f"Duplicate webhook for transaction {transaction_id}, skipping")
            return True

        # Process payment atomically
        with db.transaction():
            user = db.query(User).filter_by(user_id=payload["user_id"]).with_for_update()
            user.balance_bdt += amount

            audit_log = AuditLog(
                event_type="payment_received",
                actor_id=None,  # System event
                amount_bdt=amount,
                status="success"
            )
            db.add(audit_log)
            db.commit()

        # Mark webhook as processed (idempotency key)
        redis.setex(f"webhook_processed:{transaction_id}", 86400, "1")

        return True
```

### Idempotency Keys

```python
@app.post("/listings/{listing_id}/bid")
async def place_bid(
    listing_id: str,
    amount_bdt: int,
    idempotency_key: str = Header(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Place bid with idempotency guarantee."""

    # Check if request already processed
    cache_key = f"idempotency:{idempotency_key}"
    cached_response = redis.get(cache_key)
    if cached_response:
        return json.loads(cached_response)

    # Process bid
    bid = Bid(
        listing_id=listing_id,
        bidder_id=current_user["sub"],
        amount_bdt=amount_bdt
    )
    db.add(bid)
    db.commit()

    response = {
        "bid_id": str(bid.bid_id),
        "amount_bdt": bid.amount_bdt,
        "status": "success"
    }

    # Cache response for 24 hours
    redis.setex(cache_key, 86400, json.dumps(response))

    return response
```

---

## OWASP Top 10 Protections

### 1. SQL Injection

**Prevention:** Use parameterized queries (SQLAlchemy ORM)

```python
# ✓ SAFE: Using ORM
user = db.query(User).filter(User.email == email).first()

# ✗ UNSAFE: String concatenation
user = db.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

### 2. Broken Authentication

**Prevention:** JWT + refresh token rotation

- Access tokens expire after 1 hour
- Refresh tokens rotated on each use
- Sessions invalidated on logout
- Account lockout after 5 failed login attempts

### 3. Sensitive Data Exposure

**Prevention:** TLS 1.3, encryption at-rest, E2EE

- All data encrypted in transit (HTTPS/WSS)
- Sensitive fields encrypted at-rest
- Messages encrypted client-side (E2EE)
- No sensitive data in logs

### 4. XML External Entities (XXE)

**Prevention:** Input validation, disable XML features

```python
# Disable XXE in XML parsers
import xml.etree.ElementTree as ET
parser = ET.XMLParser(
    resolve_entities=False,
    defused=True
)
```

### 5. Broken Access Control

**Prevention:** RBAC, verify ownership

```python
@app.put("/lands/{land_id}/fence")
async def fence_land(
    land_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    land = db.query(Land).filter(Land.land_id == land_id).first()

    # Verify ownership
    if land.owner_id != UUID(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Forbidden")

    # ... update fencing
```

### 6. Security Misconfiguration

**Prevention:** Secure defaults, HSTS, CSP

```
# HTTP Security Headers
Strict-Transport-Security: max-age=31536000
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

### 7. Cross-Site Scripting (XSS)

**Prevention:** Input validation, output encoding

```python
from markupsafe import escape

# ✓ SAFE: Escape user input
message = escape(user_input)

# Frontend: Tailwind CSS + frameworks handle escaping
```

### 8. Insecure Deserialization

**Prevention:** Use JSON only, validate types

```python
# ✓ SAFE: Validate schema
from pydantic import BaseModel, validator

class BidRequest(BaseModel):
    amount_bdt: int

    @validator('amount_bdt')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v
```

### 9. Using Components with Known Vulnerabilities

**Prevention:** Dependency scanning, regular updates

```bash
# Regular security audits
pip audit
npm audit

# Use dependency scanners (GitHub, Snyk, etc.)
```

### 10. Insufficient Logging & Monitoring

**Prevention:** Comprehensive audit trails

- Log all payment events
- Log all admin actions
- Log failed login attempts
- Monitor alert thresholds

---

## Audit Trail & Compliance

### Immutable Audit Logs

All significant events logged to `audit_logs` table (INSERT-only):

```python
class AuditService:
    def log_event(self, event_type: str, actor_id: UUID,
                  resource_type: str, resource_id: str,
                  action: str, amount_bdt: int = None,
                  status: str = "success", error: str = None):
        """Log event to immutable audit trail."""

        log = AuditLog(
            event_type=event_type,
            event_category="payment",  # or "admin", "land_transfer", etc.
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            amount_bdt=amount_bdt,
            status=status,
            error_message=error,
            created_at=datetime.utcnow()
        )

        db.add(log)
        db.commit()

        return log
```

### Bangladesh Compliance

**Document Retention:**
- Transaction records: 7 years (per Bangladesh tax law)
- User data: Until account deletion
- Audit logs: Indefinitely

**Privacy Policy:**
- Data collected: username, email, balance, IP address
- Data usage: Transaction processing, fraud prevention, analytics
- Data sharing: None with third parties except payment gateways
- Data deletion: Available upon request (right to be forgotten)

---

## Secrets Management

### Environment Variables

```bash
# .env file (gitignored)
DATABASE_URL=postgresql://user:pass@localhost/vworld
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-super-secret-key-min-32-chars
BKASH_API_KEY=xxx
BKASH_API_SECRET=xxx
NAGAD_API_KEY=xxx
# ... etc
```

### Secrets in Production

Use managed secrets service:

```python
# AWS Secrets Manager
import boto3

def get_secret(secret_name: str) -> dict:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
secrets = get_secret('virtuallandworld/prod')
db_url = secrets['database_url']
```

---

## Rate Limiting & DDoS Protection

### Per-User Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/listings/{listing_id}/bid")
@limiter.limit("1/5 seconds")  # 1 bid per 5 seconds per IP
async def place_bid(...):
    pass

@app.get("/lands/search")
@limiter.limit("100/minute")  # 100 searches per minute
async def search_lands(...):
    pass
```

### Cloudflare DDoS Protection

- Rate limiting at edge (Cloudflare WAF)
- Automatic bot detection
- Geographic restrictions (optional)
- Fingerprinting and challenge

---

## Incident Response

### Breach Notification

```python
class IncidentService:
    def notify_data_breach(self, affected_user_ids: list, description: str):
        """Notify users of data breach per Bangladesh data protection law."""

        for user_id in affected_user_ids:
            user = db.query(User).get(user_id)
            send_email(
                to=user.email,
                subject="Security Incident Notification",
                body=f"We detected a security incident affecting your account. {description}"
            )

            # Log incident
            audit_log = AuditLog(
                event_type="security_incident",
                event_category="system",
                resource_type="user",
                resource_id=str(user_id),
                action="breach_notification_sent",
                status="success"
            )
            db.add(audit_log)

        db.commit()
```

---

## Security Testing

```python
# tests/test_security.py

def test_password_hashing():
    """Verify passwords are hashed, not stored plaintext."""
    password = "TestPassword123!"
    hash1 = PasswordManager.hash_password(password)
    hash2 = PasswordManager.hash_password(password)

    assert hash1 != hash2  # Different salts
    assert PasswordManager.verify_password(password, hash1)
    assert not PasswordManager.verify_password("WrongPassword", hash1)

def test_jwt_expiration():
    """Verify tokens expire."""
    past_token = create_token_with_exp(datetime.utcnow() - timedelta(hours=1))
    with pytest.raises(HTTPException):
        verify_token(past_token)

def test_sql_injection_prevention():
    """Verify SQL injection is prevented."""
    malicious_email = "' OR '1'='1"
    user = db.query(User).filter(User.email == malicious_email).first()
    assert user is None  # ORM prevents injection

def test_xss_prevention():
    """Verify XSS is prevented."""
    message = "<script>alert('XSS')</script>"
    safe_message = escape(message)
    assert "<script>" not in safe_message

def test_cors_configuration():
    """Verify CORS is properly configured."""
    response = client.options("/api/v1/users")
    assert "Access-Control-Allow-Origin" in response.headers
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.virtuallandworld.com"
```

---

## Conclusion

Virtual Land World's security architecture implements defense-in-depth across all layers, from transport security through application logic to data protection. The use of JWT, RBAC, immutable audit trails, and E2EE ensures both security and compliance with Bangladesh regulations.

---

**Resume Token:** `✓ PHASE_2_SECURITY_COMPLETE`
