# Virtual Land World - System Architecture

## Executive Summary

Virtual Land World is a distributed, scalable system combining procedural world generation, real-time communication, and transactional land marketplace. The architecture uses a classic three-tier model with decoupled frontend, backend, and persistent data layers, enhanced with caching, CDN distribution, and real-time WebSocket communication for social features.

---

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER (Browser)                       │
├─────────────────────────────────────────────────────────────────────┤
│  PixiJS Engine  │  UI Overlays  │  WebSocket Client │  WebRTC Peer  │
│  - Rendering    │  - Tailwind   │  - Chat           │  - Audio/Video│
│  - Input        │  - HUD        │  - Presence       │  - Signaling  │
│  - Caching      │  - Modals     │  - Encryption     │  - NAT Trav.  │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS/WSS
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY & LOAD BALANCER                       │
├─────────────────────────────────────────────────────────────────────┤
│  Nginx Reverse Proxy                                                 │
│  - SSL/TLS Termination                                              │
│  - Request Routing (REST / WebSocket)                               │
│  - Rate Limiting & DDoS Protection (Cloudflare)                     │
│  - GZIP Compression                                                 │
│  - Load Balancing (Round-robin / Least connections)                 │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER (FastAPI)                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ API Routers                                                  │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ - /auth         (Login, Register, Refresh Token)           │   │
│  │ - /users        (Profile, Balance, Settings)               │   │
│  │ - /lands        (CRUD, Transfer, Fence)                    │   │
│  │ - /chunks       (World Gen, Cache, Stream)                 │   │
│  │ - /marketplace  (Listings, Bids, Auctions)                 │   │
│  │ - /payments     (Webhook receivers, Status)                │   │
│  │ - /admin        (Management, Analytics, Config)            │   │
│  │ - /ws           (WebSocket: Chat, Voice, Presence)         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Business Logic Services                                      │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ - AuthService       (JWT, Tokens, Permissions)             │   │
│  │ - WorldGenService   (Procedural Generation, Determinism)   │   │
│  │ - LandService       (Ownership, Transfer, Fencing)         │   │
│  │ - MarketplaceService(Listings, Auction Logic)              │   │
│  │ - PaymentService    (Gateway Integration, Webhooks)        │   │
│  │ - ChatService       (Rooms, Encryption, History)           │   │
│  │ - ProximityService  (Spatial Queries, Auto-join)           │   │
│  │ - AnalyticsService  (Metrics, Reporting, Audit)            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Infrastructure Services                                      │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ - DatabasePool      (PostgreSQL Connection Pooling)        │   │
│  │ - CacheManager      (Redis Integration)                    │   │
│  │ - FileStorage       (S3 / CDN Integration)                 │   │
│  │ - JobQueue          (Background Tasks, Celery/APScheduler) │   │
│  │ - Logger            (Structured Logging)                   │   │
│  │ - Metrics           (Prometheus Integration)               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA LAYER (Persistence & Cache)                  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PostgreSQL (Primary Datastore)                              │   │
│  │ - Users & Accounts                                          │   │
│  │ - Lands & Ownership                                         │   │
│  │ - Transactions & Audit Logs                                 │   │
│  │ - Marketplace (Listings, Bids, Auctions)                    │   │
│  │ - Chat Sessions & Messages (Encrypted)                      │   │
│  │ - Admin Configuration                                       │   │
│  │ - Spatial Indexes for Performance                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Redis (Cache & Session Store)                               │   │
│  │ - Session Storage (JWT + Refresh Tokens)                    │   │
│  │ - Chunk Cache (LRU, TTL-based)                              │   │
│  │ - Rate Limiting Counters                                    │   │
│  │ - Distributed Locks (Atomic Operations)                     │   │
│  │ - User Presence (Online Status)                             │   │
│  │ - Message Queue (for async operations)                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Object Storage (S3 / DigitalOcean Spaces)                   │   │
│  │ - Generated Chunk Assets (serialized meshes)                │   │
│  │ - Static UI Assets (later)                                  │   │
│  │ - Backup Data                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INTEGRATIONS                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │ Payment Gateways (Bangladesh) │  │ WebRTC Infrastructure        │ │
│  │ - bKash API                   │  │ - STUN Servers              │ │
│  │ - Nagad API                   │  │ - TURN Servers              │ │
│  │ - Rocket API                  │  │ - Signaling (WebSocket)     │ │
│  │ - SSLCommerz API              │  │ - Media Server (optional)   │ │
│  │ - Webhook Receivers           │  │ - NAT Traversal             │ │
│  └──────────────────────────────┘  └──────────────────────────────┘ │
│                                                                      │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │ CDN & Security               │  │ Monitoring & Observability   │ │
│  │ - Cloudflare CDN             │  │ - Prometheus (Metrics)       │ │
│  │ - DDoS Protection            │  │ - Grafana (Dashboards)       │ │
│  │ - WAF (Web Application FW)   │  │ - ELK Stack (Logging)        │ │
│  │ - Edge Caching               │  │ - Sentry (Error Tracking)    │ │
│  └──────────────────────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Frontend Layer (PixiJS + Tailwind)
**Responsibility:** Render world, handle input, display UI, real-time communication

**Subcomponents:**
- **Rendering Engine (PixiJS):** Converts chunk data into WebGL triangles, applies biome textures, animates effects
- **Chunk Streaming System:** Requests chunks as player moves, maintains LRU cache (3×3 or 5×5 grid)
- **Player Controller:** Translates keyboard/mouse/touch input into movement, delegates to server
- **WebSocket Client:** Maintains persistent connection for chat, voice signaling, presence updates
- **WebRTC Peer Manager:** Handles P2P audio/video with STUN/TURN negotiation
- **UI Overlay (Tailwind):** HUD, menus, marketplace UI, chat interface, voice call UI
- **Encryption Engine (WebCrypto):** E2EE for messages using AES-256-GCM

**Key Characteristics:**
- Single-page application (SPA) using Vite
- Async loading (doesn't block on chunk download)
- Mobile-responsive design
- Graceful degradation (works with slower networks)

---

### 2. API Gateway & Load Balancing
**Responsibility:** Route requests, terminate TLS, apply security rules, distribute load

**Subcomponents:**
- **Nginx Reverse Proxy:** Accepts client connections, forwards to FastAPI instances
- **SSL/TLS Termination:** HTTPS/WSS encryption/decryption
- **Rate Limiting:** Per-IP, per-user throttling (Cloudflare)
- **Gzip Compression:** Reduce bandwidth for JSON responses

**Load Balancing Strategy:**
- Round-robin for stateless REST endpoints
- Sticky sessions (or Redis-backed sessions) for WebSocket connections
- Health checks on backend instances

**Cloudflare Integration:**
- DDoS mitigation
- WAF (Web Application Firewall)
- Edge caching for static assets
- Geographic load balancing

---

### 3. FastAPI Application Layer
**Responsibility:** Business logic, API endpoints, WebSocket handling, transaction management

**Subcomponents:**

#### API Routers
- **AuthRouter:** JWT generation, token refresh, login/register
- **UsersRouter:** Profile management, balance queries
- **LandsRouter:** CRUD operations, ownership transfer, fencing
- **ChunksRouter:** World generation, chunk retrieval, caching
- **MarketplaceRouter:** Listings, bids, auctions, search
- **PaymentsRouter:** Webhook receivers for payment gateways
- **AdminRouter:** User management, world config, analytics
- **WebSocketRouter:** Chat, presence, voice signaling

#### Business Logic Services
- **AuthService:** JWT/refresh token validation, password hashing (bcrypt), role checks
- **WorldGenService:** OpenSimplex procedural generation, deterministic seed handling, biome calculation
- **LandService:** Ownership queries, transfer logic, fencing verification, spatial indexing
- **MarketplaceService:** Listing creation/deletion, bid validation, auction logic, price calculations
- **PaymentService:** Webhook signature validation, idempotency checks, transaction processing
- **ChatService:** Room management, message encryption, history persistence
- **ProximityService:** Spatial queries (R-tree), land-based room detection, auto-join logic
- **AnalyticsService:** Metrics aggregation, audit log queries, reporting

#### Infrastructure Services
- **DatabasePool:** PgBouncer or SQLAlchemy connection pooling to PostgreSQL
- **CacheManager:** Redis wrapper with TTL management, atomic operations
- **FileStorage:** S3/DigitalOcean Spaces integration for chunk assets
- **JobQueue:** Async task processing (Celery or APScheduler) for expensive operations
- **Logger:** Structured logging to ELK stack or CloudWatch
- **MetricsExporter:** Prometheus metrics collection (request latency, error rates)

---

### 4. Data Layer

#### PostgreSQL (Primary Database)
**Schema Structure:**
- **users** – Accounts, roles, balances, verification status
- **lands** – Ownership, biome, coordinates, fencing settings
- **transactions** – All land purchases, transfers (immutable audit trail)
- **bids** – Auction bids with timestamps, amounts, status
- **chunks** – Metadata about generated chunks (storage paths, generation time)
- **chat_sessions** – Room metadata, creation time, participants
- **messages** – Chat messages, encrypted payloads, timestamps
- **audit_logs** – All admin actions, price changes, user suspensions (immutable)
- **admin_config** – World generation settings, price multipliers, fee percentages

**Key Features:**
- ACID transactions prevent double-spending
- Spatial indexes (GiST/BRIN) for land coordinate queries
- Row-level security (RLS) for multi-tenant isolation (future)
- JSON fields for flexible metadata
- Partition by date for large tables (messages, transactions)

#### Redis (Cache & Session Store)
**Key Patterns:**
- **Session Storage:** `session:{user_id}` → JWT payload + expiry
- **Chunk Cache:** `chunk:{chunk_id}` → serialized mesh data (TTL: 1 hour)
- **Rate Limiting:** `rate_limit:{user_id}:{endpoint}` → counter (TTL: 1 minute)
- **User Presence:** `presence:{land_id}` → set of online user IDs
- **Distributed Locks:** `lock:{resource_id}` → mutex for atomic operations

**Eviction Policy:** LRU (Least Recently Used) with 10GB max memory

#### Object Storage (S3 / DigitalOcean Spaces)
**Stored Assets:**
- Generated chunk meshes (serialized as JSON/MessagePack)
- PNG/WebP textures for biomes
- Avatar sprite sheets
- Backup archives (daily)

**Durability:** Replicated across multiple availability zones

---

## Data Flow Diagrams

### 1. User Login & Session Flow

```
Client                  Nginx                 FastAPI               PostgreSQL    Redis
  │                       │                      │                      │           │
  ├─POST /auth/login──────>                      │                      │           │
  │                       ├──forward──────────────>                      │           │
  │                       │                      ├──query user───────────>          │
  │                       │                      <──return user──────────┤           │
  │                       │                      ├─generate JWT & refresh────────────>
  │                       │                      <──store session────────────────────┤
  │                       <──response─────────────┤                      │           │
  │<──tokens + user────────┤                      │                      │           │
  │                       │                      │                      │           │
  (Request with JWT as Bearer token)             │                      │           │
  │                       │                      │                      │           │
  ├─GET /users/me (JWT)──>                       │                      │           │
  │                       ├──forward──────────────>                      │           │
  │                       │                      ├──check Redis session──────────────>
  │                       │                      <──session valid────────────────────┤
  │                       │                      ├──return user data─────>           │
  │                       │                      <──return data──────────┤           │
  │                       <──response─────────────┤                      │           │
  │<──user profile────────>                      │                      │           │
```

### 2. Land Purchase Transaction Flow

```
Client                  FastAPI               PostgreSQL            Payment Gateway
  │                       │                      │                      │
  ├─POST /listings/{id}/purchase────────────────>                      │
  │                       ├─BEGIN TRANSACTION─────>                     │
  │                       │                      ├─acquire lock (lands)─┤
  │                       │                      <──lock granted────────┤
  │                       ├──verify land exists──>                      │
  │                       <──land data──────────┤                       │
  │                       ├──initiate payment────────────────────────────>
  │                       │                      │                      ├─process
  │                       │<──payment success────────────────────────────┤
  │                       ├──update land owner──>                       │
  │                       │                      ├─UPDATE lands────────>│
  │                       │                      <──update done────────┤│
  │                       ├──record transaction─>                       │
  │                       │                      ├─INSERT transactions──>│
  │                       │                      <──insert done────────┤│
  │                       ├─COMMIT────────────────>                     │
  │                       │                      <──transaction done───┤│
  │<──success response─────┤                      │                    ││
  │                       │                      │                    ││
(WebSocket notification to other players about ownership change)
  │<──land.ownership.changed event              │                      │
```

### 3. Chat Message Flow with E2EE

```
Client A               Nginx              FastAPI              Redis         Client B
  │                     │                   │                    │             │
  ├─encrypt msg with    │                   │                    │             │
  │ shared key (client) │                   │                    │             │
  │                     │                   │                    │             │
  ├─WebSocket/send──────>                   │                    │             │
  │                     ├──forward message──>                    │             │
  │                     │                   ├─store encrypted───>│             │
  │                     │                   │ in Redis           │             │
  │                     │                   ├─broadcast to──────────────────────>
  │                     │                   │ all clients in room│             │
  │                     │                   │                    │             │
  │                     │<──delivery ack────┤                    │             │
  │<──ack received──────>                   │                    │             │
  │                     │                   │                    │             │
  │                     │                   │      receive────────────────────┤
  │                     │                   │      encrypted msg │             │
  │                     │                   │                    │  decrypt    │
  │                     │                   │                    │  & display  │
  │                     │                   │                    │             │
```

---

## Scalability Considerations

### Horizontal Scaling

**Frontend:**
- Stateless SPA served via CDN (Cloudflare)
- No per-server state required
- Auto-scaling: deploy more instances behind load balancer

**Backend:**
- Stateless REST endpoints (sessions stored in Redis)
- WebSocket connections use sticky sessions (hash of user ID)
- Auto-scaling: deploy more FastAPI instances
- Database connection pooling (PgBouncer) handles high concurrency

**Database:**
- Read replicas for analytics queries
- Partitioning by date for large tables (messages, transactions)
- Connection pooling (PgBouncer: 1000+ concurrent connections)

**Cache:**
- Redis cluster mode for data replication
- Automatic failover if master fails
- Pub/Sub for real-time broadcasting

### Vertical Scaling
- Increase database server RAM/CPU
- Increase Redis memory limit
- Increase FastAPI instance resource allocation

### Performance Optimization
- CDN caching for static chunks (Cloudflare)
- Chunk pre-generation on background workers
- Database query optimization with indexes
- Connection pooling throughout
- Gzip compression for API responses

---

## Security Architecture

### Transport Security
- **HTTPS/WSS:** All connections encrypted with TLS 1.3
- **Nginx SSL Termination:** Offload encryption from app servers
- **Cloudflare WAF:** Block malicious requests at edge

### Authentication & Authorization
- **JWT Bearer Tokens:** Stateless authentication
- **Refresh Tokens:** Rotate tokens periodically
- **Role-Based Access Control:** User, Admin, Moderator roles
- **Password Security:** bcrypt hashing with cost factor 12

### Data Protection
- **E2EE for Chat:** WebCrypto AES-256-GCM encryption
- **Database Encryption:** Sensitive fields encrypted at-rest (future)
- **Audit Logs:** Immutable, tamper-proof transaction history

### Payment Security
- **Webhook Validation:** HMAC signature verification
- **Idempotency Keys:** Prevent duplicate transactions
- **PCI Compliance:** No credit cards stored locally (gateway-handled)
- **Rate Limiting:** Prevent brute-force attacks

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Docker Compose / Kubernetes                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │  FastAPI   │  │  FastAPI   │  │  FastAPI   │       │
│  │ Instance 1 │  │ Instance 2 │  │ Instance 3 │       │
│  └────────────┘  └────────────┘  └────────────┘       │
│         ▲              ▲              ▲                 │
│         └──────────────┴──────────────┘                 │
│                      │                                  │
│                      ▼                                  │
│              ┌────────────────┐                         │
│              │ Nginx Reverse  │                         │
│              │ Proxy / LB     │                         │
│              └────────────────┘                         │
│                      │                                  │
│        ┌─────────────┼─────────────┐                    │
│        ▼             ▼             ▼                    │
│   ┌─────────┐ ┌─────────┐ ┌──────────┐               │
│   │ PostgreSQL           │ │  Redis   │               │
│   │ (Primary + Replica)  │ │ (Cluster)│               │
│   └─────────┘ └─────────┘ └──────────┘               │
│                                                         │
│   ┌──────────────────────────────────────┐             │
│   │  Worker Processes (Async Tasks)      │             │
│   └──────────────────────────────────────┘             │
│                                                         │
│   ┌──────────────────────────────────────┐             │
│   │  Monitoring Agents                   │             │
│   │  - Prometheus (metrics export)       │             │
│   │  - Filebeat (log shipping)           │             │
│   └──────────────────────────────────────┘             │
│                                                         │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
       External: Cloudflare, Payment Gateways
```

---

## Disaster Recovery & High Availability

### Backup Strategy
- **Database Backups:** Daily snapshots to S3
- **Point-in-Time Recovery:** WAL archiving (7-day retention)
- **Cross-Region Replication:** PostgreSQL standby in different region

### Failover Mechanisms
- **Database Failover:** Auto-promotion of replica if primary fails
- **Redis Failover:** Sentinel or cluster mode for automatic failover
- **Application Failover:** Load balancer detects unhealthy instances, routes elsewhere

### Recovery Time Objectives (RTO) & Recovery Point Objectives (RPO)
- **RTO:** < 5 minutes (expected)
- **RPO:** < 1 minute (transaction commit lag)

---

## Monitoring & Observability

### Metrics (Prometheus)
- HTTP request latency and error rates
- Database query performance
- Redis hit/miss ratios
- WebSocket connection count
- Payment transaction volume
- Chunk generation latency

### Logs (ELK Stack)
- Application logs (structured JSON)
- Access logs (Nginx)
- Database slow query logs
- Payment webhook logs

### Alerting (AlertManager)
- Error rate spike (>1% of requests)
- Database connection pool exhaustion
- Redis memory usage >80%
- Payment gateway timeout

---

## Cost Optimization

1. **CDN Caching:** Reduce origin bandwidth costs
2. **Database Indexing:** Faster queries, fewer resources
3. **Connection Pooling:** Reduce database overhead
4. **Chunk Pre-generation:** Spread load to off-peak hours
5. **Spot Instances:** Use auto-scaling groups with spot pricing (if cloud-hosted)

---

## Technology Stack Justification

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend Framework | FastAPI | Async/await support, built-in WebSocket, automatic API docs, high performance |
| Async Worker | Celery/APScheduler | Background job processing, distributed task queue |
| Database | PostgreSQL | ACID transactions, JSON support, spatial indexes, excellent concurrency |
| Cache | Redis | Sub-millisecond latency, atomic operations, Pub/Sub for broadcasting |
| Frontend Engine | PixiJS | Lightweight 2D rendering, WebGL, good for streaming architecture |
| UI Framework | Tailwind CSS | Utility-first CSS, responsive design, rapid prototyping |
| Deployment | Docker + K8s | Container consistency, orchestration, auto-scaling |
| Load Balancer | Nginx | Reverse proxy, load balancing, compression, rate limiting |
| CDN | Cloudflare | Edge caching, DDoS protection, WAF, global reach |
| Monitoring | Prometheus + Grafana | Open-source, industry standard, excellent dashboards |
| Logging | ELK Stack | Elasticsearch for indexing, Logstash for processing, Kibana for visualization |

---

## API Communication Patterns

### REST (Stateless Requests)
Used for CRUD operations, queries, admin functions.

```
GET /lands/{land_id}
POST /listings
PUT /listings/{id}/bid
DELETE /auctions/{id}
```

### WebSocket (Persistent, Bidirectional)
Used for real-time communication.

```
WebSocket: /ws/{user_id}

Message Types:
- chat.send
- chat.receive
- presence.update
- call.initiate
- call.signal
- land.ownership_changed
```

### Webhooks (Async Callbacks)
Used for payment gateway notifications.

```
POST /payments/webhook/bkash
POST /payments/webhook/nagad
POST /payments/webhook/rocket
POST /payments/webhook/sslcommerz
```

---

## Conclusion

Virtual Land World's architecture is designed for **scalability**, **reliability**, and **security**. The separation of concerns across frontend, API gateway, application layer, and data layer enables independent scaling and maintenance. Real-time features (WebSocket, WebRTC) are integrated seamlessly with traditional REST endpoints. The caching and CDN strategy ensures low latency and high availability globally.

**Resume Token:** `✓ PHASE_2_ARCHITECTURE_COMPLETE`
