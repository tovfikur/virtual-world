# Virtual Land World - Database Schema

## Database Overview

Virtual Land World uses PostgreSQL as the primary data store. The schema is designed for ACID compliance, supporting complex transactions, spatial queries, and audit trails. All tables include timestamps (created_at, updated_at) for tracking changes.

---

## Schema Diagram

```
┌──────────────────┐
│     users        │
├──────────────────┤
│ user_id (PK)     │
│ username         │
│ email            │
│ password_hash    │
│ role             │
│ balance_bdt      │
│ avatar_url       │
│ bio              │
│ verified         │
│ created_at       │
│ updated_at       │
│ deleted_at       │
└────┬─────────────┘
     │ (1:N)
     │
     ├─────────────┬────────────────┬───────────────────┬─────────────┐
     │             │                │                   │             │
     ▼             ▼                ▼                   ▼             ▼
┌──────────┐ ┌──────────┐  ┌──────────────┐  ┌──────────────┐ ┌─────────┐
│  lands   │ │   bids   │  │ transactions │  │chat_sessions │ │messages │
└──────────┘ └──────────┘  └──────────────┘  └──────────────┘ └─────────┘

┌──────────────┐
│  listings    │──→ lands
└──────────────┘

┌──────────────┐
│  audit_logs  │
└──────────────┘
```

---

## Core Tables

### users

Stores user account information and balance.

```sql
CREATE TABLE users (
  user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(32) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user'
    CHECK (role IN ('user', 'admin', 'moderator')),
  balance_bdt BIGINT NOT NULL DEFAULT 0 CHECK (balance_bdt >= 0),
  avatar_url TEXT,
  bio TEXT,
  verified BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP WITH TIME ZONE,

  CONSTRAINT unique_email_active CHECK (deleted_at IS NULL OR email IS NULL)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_created_at ON users(created_at DESC);
```

**Columns:**
- `user_id` – Unique user identifier (UUID)
- `username` – Display name (3-32 alphanumeric chars)
- `email` – Email address (unique when not deleted)
- `password_hash` – bcrypt hash (never store plaintext)
- `role` – User role (user, admin, moderator)
- `balance_bdt` – Account balance in Bangladeshi Taka (>= 0)
- `avatar_url` – URL to avatar image
- `bio` – User bio or profile text
- `verified` – Whether email is verified
- `created_at` – Account creation timestamp
- `updated_at` – Last profile update
- `deleted_at` – Soft delete timestamp (NULL = active)

---

### lands

Stores individual land triangles and ownership.

```sql
CREATE TABLE lands (
  land_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES users(user_id),

  -- Geographic coordinates
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  z INTEGER NOT NULL DEFAULT 0,

  -- World generation data
  biome VARCHAR(20) NOT NULL
    CHECK (biome IN ('forest', 'desert', 'grassland', 'water', 'snow')),
  elevation FLOAT NOT NULL DEFAULT 0.5,
  color_hex VARCHAR(7) NOT NULL,

  -- Access control
  fenced BOOLEAN NOT NULL DEFAULT false,
  passcode_hash VARCHAR(255),
  passcode_updated_at TIMESTAMP WITH TIME ZONE,

  -- Messaging
  public_message TEXT,

  -- Pricing
  price_base_bdt INTEGER NOT NULL DEFAULT 1000,

  -- Status
  for_sale BOOLEAN NOT NULL DEFAULT false,

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP WITH TIME ZONE,

  UNIQUE(x, y, z),
  CONSTRAINT valid_coordinates CHECK (x >= 0 AND y >= 0)
);

CREATE INDEX idx_lands_owner_id ON lands(owner_id);
CREATE INDEX idx_lands_coordinates ON lands(x, y, z);
CREATE INDEX idx_lands_biome ON lands(biome);
CREATE INDEX idx_lands_for_sale ON lands(for_sale) WHERE for_sale = true;
CREATE INDEX idx_lands_created_at ON lands(created_at DESC);

-- Spatial index for proximity queries
CREATE INDEX idx_lands_spatial ON lands USING BRIN (x, y);
```

**Columns:**
- `land_id` – Unique land identifier
- `owner_id` – User who owns this land (FK)
- `x, y, z` – 3D global coordinates (z always 0 for 2D)
- `biome` – Terrain type (forest, desert, etc.)
- `elevation` – Height value (0-1 normalized)
- `color_hex` – Hex color for rendering (#RRGGBB)
- `fenced` – Whether access is restricted
- `passcode_hash` – Hash of 4-digit passcode (if fenced)
- `passcode_updated_at` – When passcode was last set
- `public_message` – Message displayed on land
- `price_base_bdt` – Base price (used for marketplace)
- `for_sale` – Whether currently listed
- `created_at`, `updated_at`, `deleted_at` – Timestamps

---

### chunks

Metadata about generated world chunks (for caching and optimization).

```sql
CREATE TABLE chunks (
  chunk_id VARCHAR(50) PRIMARY KEY,

  -- Chunk coordinates
  chunk_x INTEGER NOT NULL,
  chunk_y INTEGER NOT NULL,

  -- Generation metadata
  generation_seed BIGINT NOT NULL,
  generation_time_ms INTEGER NOT NULL,
  size INTEGER NOT NULL DEFAULT 32,

  -- Storage location
  storage_path TEXT,
  storage_type VARCHAR(20) NOT NULL
    CHECK (storage_type IN ('memory', 's3', 'local')),

  -- Cache control
  cached BOOLEAN NOT NULL DEFAULT true,
  cache_expires_at TIMESTAMP WITH TIME ZONE,

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

  CONSTRAINT valid_chunk_coords CHECK (chunk_x >= 0 AND chunk_y >= 0)
);

CREATE INDEX idx_chunks_coordinates ON chunks(chunk_x, chunk_y);
CREATE INDEX idx_chunks_created_at ON chunks(created_at DESC);
CREATE INDEX idx_chunks_expires_at ON chunks(cache_expires_at);
```

**Columns:**
- `chunk_id` – Format: "chunk_{x}_{y}"
- `chunk_x, chunk_y` – Chunk grid coordinates
- `generation_seed` – Seed used for deterministic generation
- `generation_time_ms` – Time to generate chunk
- `size` – Triangles per dimension (typically 32)
- `storage_path` – S3 or file system path
- `storage_type` – Where chunk is stored
- `cached` – Whether currently in Redis cache
- `cache_expires_at` – When cache expires (TTL)

---

### listings

Land marketplace listings.

```sql
CREATE TABLE listings (
  listing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  land_id UUID NOT NULL REFERENCES lands(land_id) UNIQUE,
  seller_id UUID NOT NULL REFERENCES users(user_id),

  -- Listing details
  type VARCHAR(20) NOT NULL
    CHECK (type IN ('auction', 'fixed_price', 'buy_now')),
  description TEXT,
  images TEXT[], -- Array of image URLs

  -- Pricing
  price_bdt INTEGER NOT NULL,
  reserve_price_bdt INTEGER,

  -- Auction details (if type = 'auction')
  auction_start_time TIMESTAMP WITH TIME ZONE,
  auction_end_time TIMESTAMP WITH TIME ZONE,
  auto_extend BOOLEAN NOT NULL DEFAULT false,
  auto_extend_minutes INTEGER DEFAULT 5,

  -- Buy now (if enabled)
  buy_now_enabled BOOLEAN NOT NULL DEFAULT false,
  buy_now_price_bdt INTEGER,

  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'sold', 'expired', 'cancelled')),

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  sold_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_listings_seller_id ON listings(seller_id);
CREATE INDEX idx_listings_land_id ON listings(land_id);
CREATE INDEX idx_listings_status ON listings(status) WHERE status = 'active';
CREATE INDEX idx_listings_auction_end ON listings(auction_end_time)
  WHERE status = 'active' AND type = 'auction';
CREATE INDEX idx_listings_created_at ON listings(created_at DESC);
```

**Columns:**
- `listing_id` – Unique listing identifier
- `land_id` – Land being sold (FK, unique = only one active listing per land)
- `seller_id` – User selling the land (FK)
- `type` – Listing type (auction, fixed_price, or buy_now)
- `description` – Seller's description
- `images` – Array of image URLs for preview
- `price_bdt` – Base price or starting bid
- `reserve_price_bdt` – Minimum acceptable price (for auctions)
- `auction_*` – Auction-specific fields
- `auto_extend` – Auto-extend auction if bids near end
- `buy_now_enabled` – Whether instant purchase is allowed
- `buy_now_price_bdt` – Fixed price for instant purchase
- `status` – Current listing status

---

### bids

Individual auction bids.

```sql
CREATE TABLE bids (
  bid_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id UUID NOT NULL REFERENCES listings(listing_id),
  bidder_id UUID NOT NULL REFERENCES users(user_id),

  -- Bid details
  amount_bdt INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'outbid', 'cancelled', 'won')),

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

  -- Ensure chronological order by creation time
  CHECK (created_at IS NOT NULL)
);

CREATE INDEX idx_bids_listing_id ON bids(listing_id, created_at DESC);
CREATE INDEX idx_bids_bidder_id ON bids(bidder_id);
CREATE INDEX idx_bids_status ON bids(status) WHERE status = 'active';
CREATE UNIQUE INDEX idx_bids_highest_per_listing ON listings(listing_id)
  WHERE status = 'active';
```

**Columns:**
- `bid_id` – Unique bid identifier
- `listing_id` – Listing being bid on (FK)
- `bidder_id` – User placing bid (FK)
- `amount_bdt` – Bid amount
- `status` – Bid status (active, outbid, cancelled, won)
- `created_at` – When bid was placed

---

### transactions

Immutable transaction history (payment and transfers).

```sql
CREATE TABLE transactions (
  transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  land_id UUID NOT NULL REFERENCES lands(land_id),

  -- Parties involved
  seller_id UUID NOT NULL REFERENCES users(user_id),
  buyer_id UUID NOT NULL REFERENCES users(user_id),
  listing_id UUID REFERENCES listings(listing_id),

  -- Payment details
  amount_bdt BIGINT NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'BDT',

  -- Transaction status
  status VARCHAR(20) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),

  -- Payment gateway info
  gateway_name VARCHAR(50),
  gateway_transaction_id VARCHAR(255),

  -- Fees
  platform_fee_bdt BIGINT NOT NULL DEFAULT 0,
  gateway_fee_bdt BIGINT NOT NULL DEFAULT 0,
  seller_receives_bdt BIGINT NOT NULL
    GENERATED ALWAYS AS (amount_bdt - platform_fee_bdt - gateway_fee_bdt) STORED,

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP WITH TIME ZONE,

  -- Immutability: no updates allowed after creation
  CONSTRAINT immutable_transaction CHECK (created_at IS NOT NULL)
);

CREATE INDEX idx_transactions_seller ON transactions(seller_id, created_at DESC);
CREATE INDEX idx_transactions_buyer ON transactions(buyer_id, created_at DESC);
CREATE INDEX idx_transactions_land ON transactions(land_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_created_at ON transactions(created_at DESC);
```

**Columns:**
- `transaction_id` – Unique transaction ID
- `land_id` – Land involved in transaction
- `seller_id`, `buyer_id` – Parties (FKs)
- `listing_id` – Associated marketplace listing (FK, nullable for transfers)
- `amount_bdt` – Transaction amount
- `currency` – Always BDT
- `status` – Transaction status
- `gateway_name` – Payment gateway used (bkash, nagad, etc.)
- `gateway_transaction_id` – External transaction ID
- `platform_fee_bdt` – Platform commission
- `gateway_fee_bdt` – Payment processor fee
- `seller_receives_bdt` – Amount seller gets (auto-calculated)
- `created_at`, `completed_at` – Timestamps
- **IMMUTABLE:** Transactions cannot be updated after creation

---

### chat_sessions

Chat room metadata for land-based conversations.

```sql
CREATE TABLE chat_sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  land_id UUID NOT NULL REFERENCES lands(land_id),

  -- Session tracking
  status VARCHAR(20) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'archived', 'deleted')),
  participant_count INTEGER NOT NULL DEFAULT 0,

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

  UNIQUE(land_id) -- Only one active session per land
);

CREATE INDEX idx_chat_sessions_land_id ON chat_sessions(land_id);
CREATE INDEX idx_chat_sessions_status ON chat_sessions(status)
  WHERE status = 'active';
```

**Columns:**
- `session_id` – Unique chat room ID
- `land_id` – Land where chat occurs (FK)
- `status` – Session status (active, archived, deleted)
- `participant_count` – Number of people in chat
- `created_at`, `updated_at` – Timestamps

---

### messages

Encrypted chat messages.

```sql
CREATE TABLE messages (
  message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES chat_sessions(session_id),
  sender_id UUID NOT NULL REFERENCES users(user_id),

  -- Message content (encrypted)
  encrypted_payload TEXT NOT NULL, -- AES-256-GCM encrypted
  encryption_version VARCHAR(10) NOT NULL DEFAULT '1.0',
  iv VARCHAR(255) NOT NULL, -- Initialization vector

  -- Message metadata
  message_type VARCHAR(20) NOT NULL DEFAULT 'text'
    CHECK (message_type IN ('text', 'image', 'attachment')),

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP WITH TIME ZONE
);

-- Partition by month for large table
CREATE TABLE messages_2025_11 PARTITION OF messages
  FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE INDEX idx_messages_session_id ON messages(session_id, created_at DESC);
CREATE INDEX idx_messages_sender_id ON messages(sender_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
```

**Columns:**
- `message_id` – Unique message ID
- `session_id` – Chat room (FK)
- `sender_id` – Who sent message (FK)
- `encrypted_payload` – Encrypted message text (never decrypted on server)
- `encryption_version` – Version of encryption scheme used
- `iv` – Initialization vector for AES-GCM
- `message_type` – text, image, or attachment
- `created_at`, `deleted_at` – Timestamps

---

### audit_logs

Immutable log of all significant events (transactions, admin actions, price changes).

```sql
CREATE TABLE audit_logs (
  log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Event details
  event_type VARCHAR(50) NOT NULL,
  event_category VARCHAR(50) NOT NULL
    CHECK (event_category IN ('land_transfer', 'payment', 'admin', 'marketplace', 'user', 'system')),

  -- Actor (who triggered the event)
  actor_id UUID REFERENCES users(user_id), -- NULL for system events
  actor_role VARCHAR(20),

  -- Resource
  resource_type VARCHAR(50),
  resource_id VARCHAR(255),

  -- Details
  action VARCHAR(255),
  details JSONB, -- Flexible additional data

  -- Result
  status VARCHAR(20) NOT NULL DEFAULT 'success'
    CHECK (status IN ('success', 'failure')),
  error_message TEXT,

  -- Monetary (if applicable)
  amount_bdt BIGINT,

  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

  -- Immutability
  CONSTRAINT immutable_audit_log CHECK (created_at IS NOT NULL)
);

-- Partition by month
CREATE TABLE audit_logs_2025_11 PARTITION OF audit_logs
  FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE INDEX idx_audit_logs_actor_id ON audit_logs(actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(created_at)
  WHERE status = 'failure'; -- Often queried for failures
```

**Columns:**
- `log_id` – Unique log entry ID
- `event_type` – Specific event (land_transfer, payment_received, user_suspended, etc.)
- `event_category` – Category for filtering
- `actor_id` – User who triggered event (NULL for system)
- `actor_role` – Role of actor
- `resource_type` – What was affected (land, user, listing, etc.)
- `resource_id` – Which resource
- `action` – Description of action
- `details` – JSONB for flexible additional data
- `status` – success or failure
- `error_message` – If failed
- `amount_bdt` – If monetary event
- `created_at` – Immutable timestamp
- **IMMUTABLE:** Cannot be updated or deleted

---

### admin_config

World generation and platform configuration (mutable only by admins).

```sql
CREATE TABLE admin_config (
  config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- World generation
  world_seed BIGINT NOT NULL,

  -- Noise parameters
  noise_frequency FLOAT NOT NULL DEFAULT 0.05,
  noise_octaves INTEGER NOT NULL DEFAULT 6 CHECK (noise_octaves >= 1 AND noise_octaves <= 8),
  noise_persistence FLOAT NOT NULL DEFAULT 0.6 CHECK (noise_persistence > 0 AND noise_persistence < 1),
  noise_lacunarity FLOAT NOT NULL DEFAULT 2.0 CHECK (noise_lacunarity > 1),

  -- Biome distribution (as percentages, must sum to 1.0)
  biome_forest_percent FLOAT NOT NULL DEFAULT 0.35 CHECK (biome_forest_percent BETWEEN 0 AND 1),
  biome_grassland_percent FLOAT NOT NULL DEFAULT 0.30 CHECK (biome_grassland_percent BETWEEN 0 AND 1),
  biome_water_percent FLOAT NOT NULL DEFAULT 0.20 CHECK (biome_water_percent BETWEEN 0 AND 1),
  biome_desert_percent FLOAT NOT NULL DEFAULT 0.10 CHECK (biome_desert_percent BETWEEN 0 AND 1),
  biome_snow_percent FLOAT NOT NULL DEFAULT 0.05 CHECK (biome_snow_percent BETWEEN 0 AND 1),

  -- Pricing
  base_land_price_bdt INTEGER NOT NULL DEFAULT 1000,
  forest_multiplier FLOAT NOT NULL DEFAULT 1.0,
  grassland_multiplier FLOAT NOT NULL DEFAULT 0.8,
  water_multiplier FLOAT NOT NULL DEFAULT 1.2,
  desert_multiplier FLOAT NOT NULL DEFAULT 0.7,
  snow_multiplier FLOAT NOT NULL DEFAULT 1.5,

  -- Fees
  transaction_fee_percent FLOAT NOT NULL DEFAULT 5.0 CHECK (transaction_fee_percent BETWEEN 0 AND 100),

  -- Meta
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_by UUID NOT NULL REFERENCES users(user_id)
);

CREATE INDEX idx_admin_config_updated_at ON admin_config(updated_at DESC);
```

**Columns:**
- `config_id` – Config record ID
- `world_seed` – Seed for procedural generation (same seed = same world)
- `noise_*` – OpenSimplex noise parameters
- `biome_*_percent` – Distribution of biomes (must sum to 1.0)
- `base_land_price_bdt` – Base price per triangle
- `*_multiplier` – Price multiplier per biome
- `transaction_fee_percent` – Platform commission (% of sale price)
- `updated_by` – Admin who made the change
- `created_at`, `updated_at` – Timestamps

---

## Constraints & Rules

### Data Integrity

1. **Unique Coordinates:** Each (x, y, z) tuple is unique (lands are not shared)
2. **Unique Email:** Only one user per email (deleted accounts don't block)
3. **Unique Land Listing:** Only one active listing per land
4. **Positive Balance:** User balance cannot go negative
5. **Biome Distribution:** Percentages in admin_config must sum to 1.0

### Transaction Isolation

- **Serializable Isolation Level** for payment transactions to prevent race conditions
- **Distributed Locks** in Redis for coordinating concurrent land purchases

### Audit Trail

- Transactions and audit logs are **immutable** (INSERT-only, no UPDATE/DELETE)
- Provides compliance with financial regulations

---

## Indexes for Performance

### Hot Queries (Optimized with Indexes)

1. **Find lands by owner:** `lands.owner_id`
2. **Find lands by coordinates:** `lands(x, y, z)` – Spatial BRIN index
3. **Find active listings:** `listings(status)` – Partial index where status='active'
4. **Find bids on listing:** `bids(listing_id, created_at DESC)` – Reverse chronological
5. **Find recent transactions:** `transactions(seller_id, created_at DESC)`
6. **Find messages in session:** `messages(session_id, created_at DESC)` – Partitioned by month
7. **Audit log queries:** `audit_logs(actor_id, created_at DESC)` – Partitioned by month

---

## Migrations Strategy

Use Alembic (for SQLAlchemy) or Django ORM migrations for version control:

```sql
-- Initial schema
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head

-- Adding new columns
alembic revision --autogenerate -m "Add user preferences"
alembic upgrade head
```

---

## Backup & Recovery

1. **Daily backups** to AWS S3/backup service
2. **WAL archiving** for point-in-time recovery
3. **Replication to standby** for high availability
4. **Test recovery monthly** to ensure viability

---

## Connection Pooling

```python
# PgBouncer configuration for connection pooling
# (detailed in backend implementation phase)

database_url = "postgresql://user:password@pgbouncer:6432/virtualworld"
# PgBouncer pools connections, supports 1000+ concurrent clients
```

---

## Performance Monitoring

Monitor slow queries:

```sql
-- Log slow queries (queries taking >1s)
log_statement = 'all'
log_min_duration_statement = 1000

-- Check slow query log
SELECT query, mean_time, stddev_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 20;
```

---

**Resume Token:** `✓ PHASE_2_DATABASE_SCHEMA_COMPLETE`
