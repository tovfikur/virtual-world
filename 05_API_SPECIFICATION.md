# Virtual Land World - Complete API Specification

## API Overview

Virtual Land World exposes two main communication channels:
1. **REST API** – Stateless CRUD operations, queries, transactions
2. **WebSocket API** – Real-time messaging, presence, signaling

All endpoints require authentication (JWT Bearer token in Authorization header) unless explicitly marked as public.

---

## Base URLs
- **REST:** `https://api.virtuallandworld.com/api/v1`
- **WebSocket:** `wss://api.virtuallandworld.com/ws`

---

## HTTP Status Codes
- **200 OK** – Request succeeded
- **201 Created** – Resource created successfully
- **204 No Content** – Request succeeded, no response body
- **400 Bad Request** – Invalid parameters or validation error
- **401 Unauthorized** – Missing or invalid JWT token
- **403 Forbidden** – Authenticated but lacks permission
- **404 Not Found** – Resource does not exist
- **409 Conflict** – State conflict (e.g., land already owned)
- **422 Unprocessable Entity** – Validation failed with details
- **429 Too Many Requests** – Rate limit exceeded
- **500 Internal Server Error** – Unexpected server error
- **502 Bad Gateway** – Backend unavailable
- **503 Service Unavailable** – Maintenance or overload

---

## Error Response Format

All error responses follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields failed validation",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ],
    "timestamp": "2025-11-01T12:34:56Z",
    "request_id": "req-abc123def456"
  }
}
```

Common error codes:
- `VALIDATION_ERROR` – Input validation failed
- `AUTHENTICATION_FAILED` – Invalid credentials
- `UNAUTHORIZED` – Missing or expired token
- `FORBIDDEN` – Insufficient permissions
- `NOT_FOUND` – Resource doesn't exist
- `CONFLICT` – State conflict
- `RATE_LIMIT_EXCEEDED` – Too many requests
- `INTERNAL_ERROR` – Server error

---

## Authentication & Authorization

### JWT Token Structure

All protected endpoints require a JWT Bearer token in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Token payload:
```json
{
  "sub": "user_id_uuid",
  "email": "player@example.com",
  "role": "user",
  "iat": 1698825600,
  "exp": 1698829200
}
```

### Token Lifecycle
- **Access Token:** Expires in 1 hour
- **Refresh Token:** Expires in 7 days, stored in HTTP-only cookie
- Token rotation: After refresh, new token issued and old invalidated

### Role-Based Access Control (RBAC)
- **user** – Regular player (default)
- **admin** – Full platform control
- **moderator** – Marketplace moderation, user reports

---

## Pagination

List endpoints support pagination with these query parameters:

```
GET /listings?page=1&limit=20&sort=price_asc
```

Response includes pagination metadata:

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1523,
    "pages": 77,
    "has_next": true,
    "has_prev": false
  }
}
```

---

# AUTH ENDPOINTS

## POST /auth/register
**Public** – No authentication required

Register a new user account.

**Request Body:**
```json
{
  "username": "player_name",
  "email": "player@example.com",
  "password": "secure_password_min_12_chars",
  "country_code": "BD"
}
```

**Validation Rules:**
- `username`: 3-32 alphanumeric chars, unique
- `email`: Valid email format, unique
- `password`: Min 12 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
- `country_code`: ISO 3166-1 alpha-2 code (e.g., "BD")

**Success Response (201 Created):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "player_name",
  "email": "player@example.com",
  "created_at": "2025-11-01T12:34:56Z"
}
```

**Error Response Examples:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email already registered",
    "details": [{"field": "email", "message": "Already in use"}]
  }
}
```

---

## POST /auth/login
**Public** – No authentication required

Authenticate user with email and password.

**Request Body:**
```json
{
  "email": "player@example.com",
  "password": "secure_password"
}
```

**Success Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "player_name",
    "email": "player@example.com",
    "role": "user",
    "balance_bdt": 50000,
    "avatar_url": "https://..."
  }
}
```

**Note:** Refresh token sent as HTTP-only, secure cookie (Set-Cookie header)

**Error Response Examples:**
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid email or password"
  }
}
```

---

## POST /auth/refresh
**Protected** – Requires valid refresh token (via cookie)

Refresh access token without re-entering credentials.

**Request Body:** (empty)

**Success Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

## POST /auth/logout
**Protected** – Requires valid JWT token

Invalidate current session and refresh token.

**Request Body:** (empty)

**Success Response (204 No Content):**
(empty body)

---

# USER ENDPOINTS

## GET /users/{user_id}
**Protected** – Requires JWT token

Retrieve user profile information.

**Path Parameters:**
- `user_id` (UUID) – User ID

**Query Parameters:**
- `include_stats` (boolean, optional) – Include gameplay statistics

**Success Response (200 OK):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "player_name",
  "email": "player@example.com",
  "role": "user",
  "created_at": "2025-01-15T10:20:30Z",
  "balance_bdt": 50000,
  "avatar_url": "https://...",
  "bio": "Land collector and adventurer",
  "verified": true,
  "stats": {
    "lands_owned": 42,
    "total_spent_bdt": 250000,
    "total_earned_bdt": 120000,
    "friend_count": 15,
    "achievements": ["landowner_10", "millionaire"]
  }
}
```

---

## PUT /users/{user_id}
**Protected** – Requires JWT token (user can only edit own profile)

Update user profile information.

**Path Parameters:**
- `user_id` (UUID) – User ID

**Request Body:**
```json
{
  "username": "new_username",
  "bio": "Updated bio",
  "avatar_url": "https://..."
}
```

**Success Response (200 OK):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "new_username",
  "bio": "Updated bio",
  "avatar_url": "https://...",
  "updated_at": "2025-11-01T12:45:00Z"
}
```

---

## GET /users/{user_id}/balance
**Protected** – Requires JWT token

Get user's current BDT balance.

**Success Response (200 OK):**
```json
{
  "balance_bdt": 50000,
  "currency": "BDT",
  "updated_at": "2025-11-01T12:34:56Z"
}
```

---

## POST /users/{user_id}/topup
**Protected** – Requires JWT token

Initiate BDT top-up via payment gateway.

**Request Body:**
```json
{
  "amount_bdt": 5000,
  "payment_gateway": "bkash",
  "phone_number": "01700000000"
}
```

**Success Response (201 Created):**
```json
{
  "transaction_id": "txn-uuid-1234",
  "amount_bdt": 5000,
  "status": "pending",
  "payment_url": "https://payment-gateway.com/checkout?txn=...",
  "created_at": "2025-11-01T12:34:56Z"
}
```

---

# LAND ENDPOINTS

## GET /lands/{land_id}
**Public** – No authentication required

Retrieve land information by ID.

**Path Parameters:**
- `land_id` (UUID) – Land ID

**Success Response (200 OK):**
```json
{
  "land_id": "land-uuid-1234",
  "owner_id": "user-uuid-5678",
  "coordinates": {
    "x": 120,
    "y": 340,
    "z": 0
  },
  "biome": "forest",
  "color_hex": "#2d5016",
  "fenced": true,
  "passcode_required": true,
  "public_message": "Welcome to my forest!",
  "price_base_bdt": 1000,
  "created_at": "2025-01-15T10:20:30Z",
  "status": "owned",
  "for_sale": false,
  "listed_price_bdt": null
}
```

---

## POST /lands/{land_id}/fence
**Protected** – Requires JWT token (owner only)

Enable or disable fencing on owned land.

**Request Body:**
```json
{
  "fenced": true,
  "passcode": "1234"
}
```

**Validation:**
- `passcode`: 4-digit numeric code

**Success Response (200 OK):**
```json
{
  "land_id": "land-uuid-1234",
  "fenced": true,
  "passcode_updated_at": "2025-11-01T12:34:56Z"
}
```

---

## GET /lands/search
**Public** – No authentication required

Search and filter lands by criteria.

**Query Parameters:**
- `biome` (string) – Filter by biome: forest, desert, grassland, water, snow
- `min_price_bdt` (integer) – Minimum listing price
- `max_price_bdt` (integer) – Maximum listing price
- `for_sale` (boolean) – Only lands listed for sale
- `owner_id` (UUID, optional) – Lands owned by specific user
- `latitude` (float, optional) – Latitude (for proximity search)
- `longitude` (float, optional) – Longitude (for proximity search)
- `radius_km` (float, optional) – Search radius in kilometers
- `page` (integer, default: 1) – Page number
- `limit` (integer, default: 20, max: 100) – Results per page
- `sort` (string, default: created_at_desc) – Sort by: price_asc, price_desc, created_at_asc, created_at_desc

**Success Response (200 OK):**
```json
{
  "data": [
    {
      "land_id": "land-uuid-1234",
      "owner_id": "user-uuid-5678",
      "coordinates": {"x": 120, "y": 340, "z": 0},
      "biome": "forest",
      "color_hex": "#2d5016",
      "price_base_bdt": 1000,
      "for_sale": true,
      "listed_price_bdt": 1200,
      "created_at": "2025-01-15T10:20:30Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 523,
    "pages": 27,
    "has_next": true
  }
}
```

---

## POST /lands/{land_id}/transfer
**Protected** – Requires JWT token (owner only)

Transfer ownership of land to another user (no payment involved).

**Request Body:**
```json
{
  "new_owner_id": "user-uuid-new-owner",
  "message": "Here's some land for you!"
}
```

**Success Response (200 OK):**
```json
{
  "land_id": "land-uuid-1234",
  "previous_owner_id": "user-uuid-5678",
  "new_owner_id": "user-uuid-new-owner",
  "transfer_completed_at": "2025-11-01T12:34:56Z"
}
```

---

## GET /lands/{land_id}/heatmap
**Public** – No authentication required

Get pricing heatmap data for region around land.

**Success Response (200 OK):**
```json
{
  "center_land_id": "land-uuid-1234",
  "price_range": {
    "min_bdt": 500,
    "max_bdt": 5000,
    "avg_bdt": 2100
  },
  "nearby_lands": [
    {
      "land_id": "land-uuid-5678",
      "distance_m": 150,
      "price_bdt": 1200,
      "biome": "forest"
    }
  ],
  "generated_at": "2025-11-01T12:34:56Z"
}
```

---

# CHUNK ENDPOINTS

## GET /chunks/{chunk_id}
**Public** – No authentication required

Retrieve chunk mesh data (world generation data).

**Path Parameters:**
- `chunk_id` (string) – Chunk ID (format: "chunk_{x}_{y}")

**Query Parameters:**
- `format` (string, default: json) – Response format: json, msgpack, binary

**Success Response (200 OK):**
```json
{
  "chunk_id": "chunk_120_340",
  "coordinates": {"x": 120, "y": 340},
  "size": 32,
  "triangles": [
    {
      "id": 0,
      "vertices": [[0, 0, 0], [1, 0, 0], [0.5, 1, 0]],
      "biome": "forest",
      "height": 0.5,
      "color_hex": "#2d5016"
    }
  ],
  "generation_time_ms": 45,
  "cache_ttl_seconds": 3600,
  "generated_at": "2025-11-01T12:00:00Z"
}
```

**Cache Strategy:**
- Cloudflare CDN caches for 1 hour
- Redis caches for 1 hour
- ETag support for conditional requests (HTTP 304 Not Modified)

---

## POST /chunks/batch
**Public** – No authentication required

Retrieve multiple chunks in single request (for efficient loading).

**Request Body:**
```json
{
  "chunk_ids": ["chunk_120_340", "chunk_121_340", "chunk_120_341"]
}
```

**Success Response (200 OK):**
```json
{
  "chunks": {
    "chunk_120_340": {...},
    "chunk_121_340": {...},
    "chunk_120_341": {...}
  },
  "count": 3
}
```

---

## GET /chunks/heatmap
**Public** – No authentication required

Get world heatmap showing land prices and density by region.

**Query Parameters:**
- `zoom_level` (integer, 1-10) – Granularity of heatmap
- `region` (string, optional) – Specific region filter

**Success Response (200 OK):**
```json
{
  "heatmap": [
    {
      "region_id": "region_120_340",
      "avg_price_bdt": 2100,
      "land_count": 523,
      "biome_distribution": {
        "forest": 0.40,
        "grassland": 0.35,
        "water": 0.15,
        "desert": 0.08,
        "snow": 0.02
      }
    }
  ],
  "generated_at": "2025-11-01T12:34:56Z"
}
```

---

# MARKETPLACE ENDPOINTS

## POST /listings
**Protected** – Requires JWT token (owner only)

Create a new land listing for sale.

**Request Body:**
```json
{
  "land_id": "land-uuid-1234",
  "price_bdt": 2500,
  "auction_enabled": true,
  "auction_duration_hours": 24,
  "reserve_price_bdt": 2000,
  "buy_now_enabled": true,
  "description": "Beautiful forest land near city center",
  "images": ["https://..."]
}
```

**Success Response (201 Created):**
```json
{
  "listing_id": "listing-uuid-1234",
  "land_id": "land-uuid-1234",
  "seller_id": "user-uuid-5678",
  "type": "auction",
  "price_bdt": 2500,
  "status": "active",
  "auction_end_time": "2025-11-02T12:34:56Z",
  "created_at": "2025-11-01T12:34:56Z"
}
```

---

## GET /listings
**Public** – No authentication required

List all active land listings.

**Query Parameters:**
- `status` (string) – active, expired, sold, cancelled
- `sort_by` (string) – price_asc, price_desc, created_at_asc, created_at_desc
- `page` (integer, default: 1)
- `limit` (integer, default: 20)

**Success Response (200 OK):**
```json
{
  "data": [
    {
      "listing_id": "listing-uuid-1234",
      "land_id": "land-uuid-1234",
      "seller_id": "user-uuid-5678",
      "type": "auction",
      "price_bdt": 2500,
      "status": "active",
      "current_bid_bdt": 2300,
      "bid_count": 5,
      "auction_end_time": "2025-11-02T12:34:56Z",
      "created_at": "2025-11-01T12:34:56Z"
    }
  ],
  "pagination": {...}
}
```

---

## GET /listings/{listing_id}
**Public** – No authentication required

Get details of specific listing.

**Success Response (200 OK):**
```json
{
  "listing_id": "listing-uuid-1234",
  "land_id": "land-uuid-1234",
  "seller_id": "user-uuid-5678",
  "seller_username": "seller_name",
  "type": "auction",
  "price_bdt": 2500,
  "status": "active",
  "description": "Beautiful forest land",
  "images": ["https://..."],
  "auction_details": {
    "start_price_bdt": 2000,
    "reserve_price_bdt": 2000,
    "current_bid_bdt": 2300,
    "current_bidder_id": "user-uuid-bidder",
    "bid_count": 5,
    "auction_start_time": "2025-11-01T12:34:56Z",
    "auction_end_time": "2025-11-02T12:34:56Z",
    "auto_extend_enabled": true,
    "auto_extend_minutes": 5
  },
  "buy_now_enabled": true,
  "buy_now_price_bdt": 3000,
  "created_at": "2025-11-01T12:34:56Z"
}
```

---

## PUT /listings/{listing_id}
**Protected** – Requires JWT token (seller only)

Update active listing.

**Request Body:**
```json
{
  "price_bdt": 2600,
  "description": "Updated description",
  "reserve_price_bdt": 2100
}
```

**Success Response (200 OK):**
```json
{
  "listing_id": "listing-uuid-1234",
  "updated_at": "2025-11-01T12:50:00Z"
}
```

---

## DELETE /listings/{listing_id}
**Protected** – Requires JWT token (seller only)

Cancel active listing (only if no bids).

**Success Response (204 No Content):**
(empty body)

---

## POST /listings/{listing_id}/bids
**Protected** – Requires JWT token

Place bid on auction listing.

**Request Body:**
```json
{
  "amount_bdt": 2400
}
```

**Validation:**
- Bid amount must exceed current highest bid by minimum increment (e.g., 50 BDT)
- Bid amount must be >= reserve price
- User must have sufficient balance
- Cannot bid on own listing

**Success Response (201 Created):**
```json
{
  "bid_id": "bid-uuid-1234",
  "listing_id": "listing-uuid-1234",
  "bidder_id": "user-uuid-bidder",
  "amount_bdt": 2400,
  "status": "active",
  "created_at": "2025-11-01T12:45:00Z"
}
```

---

## GET /listings/{listing_id}/bids
**Public** – No authentication required

Get all bids on a listing.

**Success Response (200 OK):**
```json
{
  "bids": [
    {
      "bid_id": "bid-uuid-1234",
      "bidder_username": "bidder_name",
      "amount_bdt": 2400,
      "created_at": "2025-11-01T12:45:00Z"
    }
  ],
  "count": 5
}
```

---

## POST /listings/{listing_id}/buy-now
**Protected** – Requires JWT token

Purchase land at buy-now price (instant).

**Request Body:** (empty)

**Success Response (201 Created):**
```json
{
  "transaction_id": "txn-uuid-1234",
  "listing_id": "listing-uuid-1234",
  "buyer_id": "user-uuid-buyer",
  "seller_id": "user-uuid-seller",
  "land_id": "land-uuid-1234",
  "price_bdt": 3000,
  "status": "completed",
  "ownership_transferred_at": "2025-11-01T12:35:00Z",
  "created_at": "2025-11-01T12:34:56Z"
}
```

---

# PAYMENT ENDPOINTS

## POST /payments/webhook/bkash
**Public** – Webhook receiver (verified by HMAC signature)

Receive payment completion notification from bKash.

**Request Header:**
```
X-Signature: HMAC-SHA256(payload, secret)
```

**Request Body:**
```json
{
  "trxID": "bkash_transaction_id",
  "status": "Completed",
  "amount": 5000,
  "currency": "BDT",
  "orderID": "txn-uuid-1234",
  "createTime": "2025-11-01T12:34:56Z"
}
```

**Processing:**
1. Verify HMAC signature against webhook secret
2. Check if transaction already processed (idempotency check via orderID)
3. Update user balance in database (atomic transaction)
4. Send confirmation to user
5. Log to audit trail

**Success Response (200 OK):**
```json
{
  "status": "accepted",
  "order_id": "txn-uuid-1234"
}
```

---

## POST /payments/webhook/nagad
**Public** – Webhook receiver

Similar structure to bKash webhook.

---

## POST /payments/webhook/rocket
**Public** – Webhook receiver

Similar structure to bKash webhook.

---

## POST /payments/webhook/sslcommerz
**Public** – Webhook receiver

Similar structure to bKash webhook.

---

## GET /payments/status/{transaction_id}
**Protected** – Requires JWT token

Get status of payment transaction.

**Success Response (200 OK):**
```json
{
  "transaction_id": "txn-uuid-1234",
  "status": "completed",
  "amount_bdt": 5000,
  "payment_gateway": "bkash",
  "gateway_transaction_id": "bkash_txn_123",
  "created_at": "2025-11-01T12:34:56Z",
  "completed_at": "2025-11-01T12:36:00Z"
}
```

---

# ADMIN ENDPOINTS

## GET /admin/users
**Protected** – Requires admin role

List all users with filtering and pagination.

**Query Parameters:**
- `search` (string) – Search by username or email
- `role` (string) – Filter by role: user, admin, moderator
- `status` (string) – active, suspended, deleted
- `sort_by` (string) – created_at_desc, balance_desc, username_asc

**Success Response (200 OK):**
```json
{
  "data": [
    {
      "user_id": "user-uuid-1234",
      "username": "player_name",
      "email": "player@example.com",
      "role": "user",
      "status": "active",
      "balance_bdt": 50000,
      "lands_owned": 42,
      "created_at": "2025-01-15T10:20:30Z",
      "last_login": "2025-11-01T10:00:00Z"
    }
  ],
  "pagination": {...}
}
```

---

## PUT /admin/users/{user_id}
**Protected** – Requires admin role

Suspend, unsuspend, or delete user account.

**Request Body:**
```json
{
  "status": "suspended",
  "reason": "Violation of terms of service",
  "suspension_until": "2025-12-01T00:00:00Z"
}
```

**Success Response (200 OK):**
```json
{
  "user_id": "user-uuid-1234",
  "status": "suspended",
  "updated_at": "2025-11-01T12:34:56Z"
}
```

---

## POST /admin/world/config
**Protected** – Requires admin role

Update world generation configuration.

**Request Body:**
```json
{
  "seed": 12345,
  "biome_distribution": {
    "forest": 0.35,
    "grassland": 0.30,
    "water": 0.20,
    "desert": 0.10,
    "snow": 0.05
  },
  "noise_frequency": 0.05,
  "noise_octaves": 6,
  "noise_persistence": 0.6,
  "noise_lacunarity": 2.0
}
```

**Success Response (200 OK):**
```json
{
  "config_id": "config-uuid-1234",
  "seed": 12345,
  "updated_at": "2025-11-01T12:34:56Z",
  "note": "Changes will apply to newly generated chunks only"
}
```

---

## PUT /admin/pricing
**Protected** – Requires admin role

Update land pricing configuration.

**Request Body:**
```json
{
  "base_price_bdt": 1000,
  "biome_multipliers": {
    "forest": 1.0,
    "grassland": 0.8,
    "water": 1.2,
    "desert": 0.7,
    "snow": 1.5
  },
  "proximity_bonus": {
    "enabled": true,
    "distance_km": 5,
    "percentage_increase": 15
  }
}
```

**Success Response (200 OK):**
```json
{
  "updated_at": "2025-11-01T12:34:56Z"
}
```

---

## GET /admin/analytics
**Protected** – Requires admin role

Get platform analytics and metrics.

**Query Parameters:**
- `date_from` (ISO 8601) – Start date for metrics
- `date_to` (ISO 8601) – End date for metrics
- `metrics` (string[]) – Comma-separated list: sales_volume, user_growth, active_users, avg_price

**Success Response (200 OK):**
```json
{
  "period": {
    "from": "2025-10-01",
    "to": "2025-11-01"
  },
  "metrics": {
    "sales_volume_bdt": 5230000,
    "transaction_count": 1523,
    "new_users": 342,
    "active_users_daily_avg": 4521,
    "avg_land_price_bdt": 2150,
    "richest_player": {
      "user_id": "user-uuid-1234",
      "username": "player_name",
      "balance_bdt": 5000000
    },
    "top_biome": {
      "biome": "forest",
      "transactions": 423,
      "avg_price_bdt": 2400
    }
  }
}
```

---

## GET /admin/audit-logs
**Protected** – Requires admin role

View immutable audit log of all transactions and admin actions.

**Query Parameters:**
- `type` (string) – land_transfer, price_change, user_suspension, payment_processed
- `user_id` (UUID, optional) – Filter by user
- `date_from` (ISO 8601) – Start date
- `date_to` (ISO 8601) – End date

**Success Response (200 OK):**
```json
{
  "logs": [
    {
      "log_id": "log-uuid-1234",
      "type": "land_transfer",
      "actor_id": "user-uuid-seller",
      "actor_username": "seller_name",
      "resource": "land-uuid-1234",
      "action": "transferred to user-uuid-buyer",
      "amount_bdt": 2500,
      "status": "completed",
      "created_at": "2025-11-01T12:34:56Z"
    }
  ],
  "pagination": {...}
}
```

---

# WEBSOCKET API

## Connection
```
WebSocket URL: wss://api.virtuallandworld.com/ws/{user_id}
Authorization: ?token={jwt_token}
```

### Connection Lifecycle
1. Client establishes WebSocket connection with JWT token
2. Server verifies token and subscribes user to relevant channels
3. User receives presence notifications as others join/leave
4. Connection persists for real-time communication
5. Client disconnect triggers automatic cleanup

---

## WebSocket Message Format

All WebSocket messages follow this format:

```json
{
  "type": "message_type",
  "timestamp": "2025-11-01T12:34:56Z",
  "data": {...}
}
```

---

## Chat Messages

### Client → Server: chat.send
User sends chat message to land-based chat room.

```json
{
  "type": "chat.send",
  "data": {
    "room_id": "land_uuid_1234",
    "message": "Hello everyone!",
    "encrypted": true,
    "encryption_version": "1.0"
  }
}
```

### Server → Client: chat.receive
Server broadcasts chat message to all users in room.

```json
{
  "type": "chat.receive",
  "timestamp": "2025-11-01T12:34:56Z",
  "data": {
    "message_id": "msg-uuid-1234",
    "room_id": "land_uuid_1234",
    "sender_id": "user-uuid-1234",
    "sender_username": "player_name",
    "message": "encrypted_payload",
    "sent_at": "2025-11-01T12:34:56Z"
  }
}
```

---

## Presence & Proximity

### Server → Client: presence.update
Notifies client when other players enter/leave proximity.

```json
{
  "type": "presence.update",
  "data": {
    "room_id": "land_uuid_1234",
    "action": "user_joined",
    "user_id": "user-uuid-1234",
    "username": "player_name",
    "online_count": 5
  }
}
```

---

## Voice/Video Calling

### Client → Server: call.initiate
Initiate voice or video call with users in same proximity.

```json
{
  "type": "call.initiate",
  "data": {
    "room_id": "land_uuid_1234",
    "call_type": "audio",
    "call_id": "call-uuid-1234",
    "initiator_id": "user-uuid-1234",
    "participants": ["user-uuid-5678", "user-uuid-9012"]
  }
}
```

### Client ↔ Server: call.signal
Exchange WebRTC offer/answer/candidate signals.

```json
{
  "type": "call.signal",
  "data": {
    "call_id": "call-uuid-1234",
    "from_id": "user-uuid-1234",
    "to_id": "user-uuid-5678",
    "signal_type": "offer",
    "signal_data": {
      "type": "offer",
      "sdp": "v=0\r\n..."
    }
  }
}
```

---

## Land Ownership Updates

### Server → Client: land.ownership_changed
Broadcast when land changes ownership (marketplace transaction).

```json
{
  "type": "land.ownership_changed",
  "data": {
    "land_id": "land-uuid-1234",
    "previous_owner_id": "user-uuid-seller",
    "new_owner_id": "user-uuid-buyer",
    "transaction_id": "txn-uuid-1234",
    "price_bdt": 2500,
    "timestamp": "2025-11-01T12:34:56Z"
  }
}
```

---

## Error Handling

### WebSocket Error Format

```json
{
  "type": "error",
  "data": {
    "code": "PERMISSION_DENIED",
    "message": "You are not allowed to chat in this room",
    "request_id": "req-uuid-1234"
  }
}
```

---

## Rate Limiting

All API endpoints are rate-limited per user:

- **REST API:** 100 requests per minute per user
- **WebSocket:** 10 messages per second per user
- **File Uploads:** 100 MB per day per user
- **Marketplace Bids:** 1 bid per 5 seconds per listing

Responses include rate limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1698829200
```

---

**Resume Token:** `✓ PHASE_2_API_SPEC_COMPLETE`
