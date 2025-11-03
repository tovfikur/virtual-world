# Virtual Land World - Requirements Summary

## Project Vision
A persistent, 2D browser-based virtual world where players explore procedurally generated terrain, own virtual land through BDT transactions, and interact with other players via chat and voice communication. The platform combines real estate mechanics with social networking in an infinite, deterministic world.

---

## Core Project Requirements

### 1. **World Generation & Persistence**
- Procedurally generated infinite 2D world using OpenSimplex/Perlin noise
- Chunk-based architecture (32×32 triangles per chunk, ~500m² per triangle)
- Deterministic generation: same seed always produces identical output
- Five biome types: Forest, Desert, Grassland, Water, Snow
- Server-side chunk persistence with Redis caching and CDN distribution
- Client-side LRU cache (3×3 or 5×5 chunk loading radius)

### 2. **Land Ownership System**
- Triangular land units as smallest purchasable property
- Each triangle has unique global ID derived from coordinates
- Persistent ownership tracking in PostgreSQL
- Land transfer through marketplace or direct trading
- Fencing system with passcode protection for privacy
- Customizable land messages and metadata

### 3. **Player Movement & Exploration**
- 2D top-down RPG-style camera and movement controls
- Real-time position synchronization via WebSocket
- Smooth camera following with viewport boundaries
- Mobile and desktop support
- Avatar customization (simple shapes/icons)

### 4. **Real-time Communication**
- Proximity-based social zones tied to land parcels
- Auto-joining chat/call groups when entering land
- Text chat with encryption support
- WebRTC-based voice and video calling
- End-to-end encryption for messages using WebCrypto API
- Message history persistence (optional, encrypted)
- Active player presence indicators

### 5. **Marketplace & Auction System**
- Land listing with reserve prices and auction mechanics
- Bidding system with auto-accept options
- Buy Now instant purchase functionality
- Dynamic pricing suggestions based on biome, proximity, and market
- Search and filter by location, biome, price range
- Pricing heatmap visualization
- Transaction ledger and audit trail
- Leaderboards: richest players, most valuable holdings

### 6. **Payment Processing**
- Bangladesh Taka (BDT) only—no cryptocurrency
- Integration with 4 gateways: bKash, Nagad, Rocket, SSLCommerz
- Webhook-based payment verification and async processing
- Transaction fee management (platform takes percentage)
- Atomic database transactions to prevent double-spending
- Payment audit trail with immutable records

### 7. **Admin & Control Panel**
- World generation control (seed, biome distribution, resource spawning)
- User account management (suspension, verification, balance adjustment)
- Land price configuration (base prices, biome multipliers)
- Transaction fee settings
- Marketplace moderation (remove fraudulent listings)
- Analytics dashboard (sales volume, user statistics, regional activity)
- Immutable audit logs for compliance

### 8. **Security & Authentication**
- JWT + Refresh token authentication
- Secure password hashing (bcrypt)
- Role-based access control (User, Admin, Moderator)
- Database-level transaction locks for atomic operations
- Immutable audit ledger
- Passcode hashing for land access
- WebCrypto API for E2EE messaging
- HTTPS/TLS enforcement

### 9. **Performance & Optimization**
- Redis caching for frequently accessed chunks
- CDN distribution for static chunk assets (S3/DigitalOcean Spaces)
- Delta updates for ownership changes (only send deltas, not full state)
- Async background jobs for expensive operations
- Lazy texture loading and streaming
- Dynamic Level of Detail (LOD) for distant terrains
- Spatial indexing (R-tree or Quad-tree) for ownership queries

### 10. **Visual Design**
- 2D flat polygonal or soft-gradient rendering style
- Distinct color palettes per biome for visual clarity
- Simple idle animations (wind effects, water flow)
- Customizable player avatars (simple shapes or icons)
- UI overlays using Tailwind CSS
- Responsive design for mobile and desktop

### 11. **Database Requirements**
- **Primary DB:** PostgreSQL (ACID transactions, JSON support, spatial indexing)
- **Cache:** Redis (session storage, chunk caching, rate limiting)
- **Tables needed:** users, lands, transactions, bids, chunks, chat_sessions, messages, audit_logs
- **Relationships:** Multi-owner support, transaction history, message threading

### 12. **API Architecture**
- RESTful endpoints for CRUD operations
- WebSocket for real-time communication (chat, voice signaling, presence)
- Version-controlled API (v1, v2 for future compatibility)
- Pagination for list endpoints
- Comprehensive error responses with HTTP status codes

### 13. **Deployment & Infrastructure**
- Dockerized application (FastAPI backend, PixiJS frontend)
- Nginx reverse proxy with gzip compression
- Cloudflare CDN for edge delivery
- STUN/TURN servers for WebRTC NAT traversal
- Background job queue (Celery or APScheduler)
- Database backups and recovery procedures

### 14. **Legal & Compliance (Bangladesh)**
- Comply with Bangladesh digital service regulations
- Clearly state that land is virtual digital property only (not real estate)
- Income tax and VAT compliance for transactions
- Use only legally approved BDT payment gateways
- No blockchain, cryptocurrency, or NFT elements
- User Terms of Service and Privacy Policy

### 15. **Future-Ready Extensions**
- Friend system (add, follow, visit)
- Land events (public gatherings/meetups)
- Gift cards and vouchers for BDT top-ups
- In-game news feed
- Mobile AR integration (camera overlay)
- Educational zones for learning platforms

---

## System Actors

| Actor | Role | Responsibilities |
|-------|------|------------------|
| **Player / User** | Primary user | Explore world, buy/sell/trade land, chat, voice call, customize profile |
| **Land Owner** | Player subset | Enable fences, set passcodes, list for sale/auction, host events |
| **Admin** | System operator | Control world generation, set pricing, moderate marketplace, audit logs |
| **Payment Gateway** | External service | Process BDT payments (bKash, Nagad, Rocket, SSLCommerz) |
| **WebRTC Server** | Infrastructure | STUN/TURN services for P2P voice/video |
| **CDN / Storage** | Infrastructure | Serve static chunks, store assets (S3 / DigitalOcean Spaces) |

---

## Critical Success Factors

1. **Deterministic World Generation** – Players must see consistent world state across restarts
2. **Atomic Transactions** – Prevent race conditions in land purchases and transfers
3. **Real-time Synchronization** – WebSocket must handle 10,000+ concurrent players at scale
4. **Chunk Caching Strategy** – Minimize database and computation load via Redis + CDN
5. **Payment Security** – Implement webhook validation, idempotency, audit trails
6. **E2EE Messaging** – Use WebCrypto correctly to prevent server-side message interception
7. **Performance** – Chunk streaming must support 60 FPS on mid-range devices

---

## Technology Stack Summary

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Frontend Engine** | PixiJS + HTML5 Canvas | Lightweight 2D rendering, good for streaming architecture |
| **UI Framework** | Tailwind CSS | Rapid prototyping, responsive design |
| **Backend Framework** | Python FastAPI | Fast async performance, WebSocket support, auto-docs |
| **Database** | PostgreSQL | ACID, JSON support, spatial indexing, replication |
| **Cache / Session** | Redis | Sub-millisecond access, atomic operations |
| **Real-time** | WebSocket (FastAPI native) | Bidirectional communication for chat/voice signaling |
| **Voice/Video** | WebRTC + STUN/TURN | P2P media, NAT traversal, minimal latency |
| **Encryption** | WebCrypto API (client) | E2EE for messages without server decryption |
| **Payment** | bKash, Nagad, Rocket, SSLCommerz APIs | Bangladesh-specific gateways |
| **Storage** | AWS S3 or DigitalOcean Spaces | Scalable asset hosting |
| **CDN** | Cloudflare | Edge caching, DDoS protection, low latency |
| **Containerization** | Docker + Docker Compose | Reproducible deployments |
| **Web Server** | Nginx | Reverse proxy, load balancing, compression |
| **Monitoring** | Prometheus + Grafana + ELK Stack | Application metrics, logging, alerting |
| **Testing** | pytest (backend), jest (frontend) | Comprehensive test coverage |

---

## Project Scope & Constraints

### In Scope
- ✅ Procedurally generated 2D world
- ✅ Land ownership and marketplace
- ✅ Real-time chat and WebRTC calling
- ✅ BDT payment processing
- ✅ Admin panel and analytics
- ✅ Mobile-responsive UI
- ✅ Docker deployment

### Out of Scope (Phase 1)
- ❌ 3D graphics or 3D upgrade path
- ❌ Blockchain / NFT / Cryptocurrency
- ❌ Single Sign-On (OAuth2 integration deferred)
- ❌ Mobile native apps (web-based only for now)
- ❌ AI-driven NPCs or bots
- ❌ In-game economy simulation

---

## Estimated Effort

| Phase | Duration | Deliverables | Notes |
|-------|----------|--------------|-------|
| **1. Requirements** | 0.5 hr | Planning docs | Planning only |
| **2. Architecture** | 2-3 hrs | API, DB schema, design docs | Design & specification |
| **3. Backend Core** | 4-5 hrs | FastAPI models, auth, world gen | Core backend systems |
| **4. Frontend Engine** | 4-5 hrs | PixiJS engine, chunk streaming | Rendering & streaming |
| **5. Marketplace** | 2-3 hrs | Payment API, auction system | Monetization |
| **6. Communication** | 2-3 hrs | Chat, WebRTC, encryption | Social features |
| **7. Admin & Deploy** | 3-4 hrs | Admin panel, testing, docker | DevOps & ops |
| **TOTAL** | **18-25 hrs** | 36 detailed specification documents | Full specification output |

---

## Assumptions & Dependencies

### Assumptions
- Bangladesh legal/regulatory environment is stable
- Players have reliable internet connectivity
- Database can handle 100K+ concurrent connections with proper pooling
- Payment gateways will provide reliable webhooks

### Dependencies
- **External APIs:** bKash, Nagad, Rocket, SSLCommerz (payment)
- **Infrastructure:** STUN/TURN servers, CDN access, S3/storage bucket
- **Libraries:** FastAPI, PixiJS, PostgreSQL, Redis, WebRTC libraries
- **Skills:** Full-stack JavaScript/Python, DevOps, security, database design

---

## Next Steps

1. **Phase 2:** Create detailed system architecture and API specification
2. **Phase 3:** Implement FastAPI backend with ORM models
3. **Phase 4:** Build PixiJS rendering engine and chunk streaming
4. **Phase 5:** Integrate payment system and marketplace
5. **Phase 6:** Add chat and WebRTC calling
6. **Phase 7:** Deploy with Docker and monitoring

---

**Document Generated:** 2025-11-01
**Status:** ✓ PHASE_1_REQUIREMENTS_COMPLETE
