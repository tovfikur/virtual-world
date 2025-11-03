# Virtual Land World - Hierarchical TODO Roadmap

## Project Overview
Building a persistent 2D virtual world with FastAPI backend and PixiJS frontend. This document outlines 7 execution phases with specific deliverables, dependencies, and checkpoint tests.

---

# PHASE 1: Requirements & Planning
**Duration:** 0.5 hours | **Status:** IN PROGRESS

## Input Requirements
- ✓ Project specification document (provided)
- ✓ Technology stack decisions (FastAPI, PixiJS, PostgreSQL)
- ✓ Legal/compliance context (Bangladesh)

## Deliverables
- [ ] `01_REQUIREMENTS_SUMMARY.md` – Complete project requirements ✓ DONE
- [ ] `02_TODO_PLAN.md` – Hierarchical roadmap (this file) ✓ IN PROGRESS
- [ ] `03_RUN_PLAN.md` – Execution controller guide

## Output Size
**SMALL** (~3-5 KB per file, 15-20 KB total)

## Checkpoint Test
✓ All three files exist and are readable
✓ Requirements are comprehensive and unambiguous
✓ Phase 2 input requirements are clearly stated

## Resume Token
```
✓ PHASE_1_COMPLETE
```

---

# PHASE 2: Architecture & System Design
**Duration:** 2-3 hours | **Status:** PENDING

## Input Requirements
- ✓ PHASE_1_COMPLETE token
- ✓ Requirements summary from Phase 1
- ✓ Technology stack decisions

## Deliverables
- [ ] `04_SYSTEM_ARCHITECTURE.md` – High-level system design, component relationships, data flow
- [ ] `05_API_SPECIFICATION.md` – Complete REST API endpoints (auth, users, lands, marketplace, admin)
- [ ] `06_DATABASE_SCHEMA.md` – PostgreSQL DDL, relationships, indexes, JSON fields
- [ ] `07_PROCEDURAL_GENERATION_SPEC.md` – World generation algorithm, chunk structure, biomes
- [ ] `08_SECURITY_ARCHITECTURE.md` – Auth flow, encryption, payment security, audit trail

## Output Size
**LARGE** (~20-30 KB per file, 100-150 KB total)

## Key Decisions to Make
- [ ] Chunk size and LOD strategy
- [ ] Biome distribution algorithm
- [ ] Payment webhook idempotency mechanism
- [ ] Message encryption at-rest vs. in-transit only
- [ ] Cache invalidation strategy

## Checkpoint Test
```bash
# Verify all files exist
ls -la 04_* 05_* 06_* 07_* 08_*

# Verify API spec completeness
# Check: GET/POST/PUT/DELETE endpoints for all resources
# Check: WebSocket message types documented
# Check: Error response formats defined

# Verify DB schema completeness
# Check: All tables have primary keys
# Check: Foreign keys defined
# Check: Indexes for query performance listed
# Check: Audit trail columns (created_at, updated_at, deleted_at)

# Verify procedural generation spec
# Check: OpenSimplex configuration documented
# Check: Chunk ID generation formula explicit
# Check: Biome threshold values defined
```

## Resume Token
```
✓ PHASE_2_COMPLETE
```

---

# PHASE 3: Backend Core Implementation
**Duration:** 4-5 hours | **Status:** PENDING

## Input Requirements
- ✓ PHASE_2_COMPLETE token
- ✓ API specification from Phase 2
- ✓ Database schema from Phase 2

## Deliverables
- [ ] `09_BACKEND_PROJECT_STRUCTURE.md` – FastAPI project layout, package organization
- [ ] `10_DATABASE_MODELS.md` – SQLAlchemy ORM models with relationships and constraints
- [ ] `11_AUTHENTICATION_SYSTEM.md` – JWT implementation, token refresh logic, password hashing
- [ ] `12_WORLD_GENERATION_API.md` – Chunk generation endpoints, caching strategy, CDN integration
- [ ] `13_LAND_OWNERSHIP_API.md` – Land CRUD, transfer logic, fencing, passcode verification
- [ ] `14_CACHING_STRATEGY.md` – Redis key patterns, TTLs, cache invalidation rules

## Output Size
**LARGE** (~15-25 KB per file, 90-150 KB total)

## Implementation Checkpoints
- [ ] FastAPI application initialization with async/await
- [ ] PostgreSQL connection pooling configured
- [ ] Redis cache layer integrated
- [ ] JWT token generation and validation working
- [ ] World generation algorithm produces deterministic output
- [ ] Land ownership queries optimized with spatial indexing

## Test Coverage Required
```
- Unit tests: Authentication, JWT validation
- Unit tests: World generation (determinism verification)
- Unit tests: Land ownership transfer logic
- Integration tests: Payment transaction isolation
- Integration tests: Cache invalidation on land updates
- Load test: 1000 concurrent chunk requests
```

## Checkpoint Test
```bash
# Run backend tests
pytest tests/test_auth.py -v
pytest tests/test_world_gen.py -v
pytest tests/test_land_ownership.py -v

# Verify deterministic world generation
python scripts/test_world_gen.py --seed=12345 --verify

# Verify database constraints
python scripts/validate_schema.py

# Test cache layer
pytest tests/test_cache.py -v
```

## Resume Token
```
✓ PHASE_3_COMPLETE
```

---

# PHASE 4: Frontend Engine & World Rendering
**Duration:** 4-5 hours | **Status:** PENDING

## Input Requirements
- ✓ PHASE_3_COMPLETE token
- ✓ World generation specification from Phase 2
- ✓ API specification from Phase 2

## Deliverables
- [ ] `15_FRONTEND_PROJECT_STRUCTURE.md` – PixiJS application architecture, build system
- [ ] `16_CHUNK_STREAMING_SYSTEM.md` – Client-side chunk loading, LRU cache, mesh generation
- [ ] `17_RENDERING_ENGINE.md` – PixiJS rendering pipeline, biome textures, animations
- [ ] `18_CAMERA_MOVEMENT.md` – Player movement, camera following, viewport management
- [ ] `19_UI_COMPONENTS.md` – Tailwind UI overlays, HUD design, responsive layout

## Output Size
**LARGE** (~15-25 KB per file, 75-125 KB total)

## Implementation Checkpoints
- [ ] PixiJS renderer initializes at 60 FPS
- [ ] Chunk streaming requests chunks as player moves
- [ ] LRU cache retains 3×3 or 5×5 chunk grid
- [ ] Biome colors and textures render correctly
- [ ] Camera follows player smoothly
- [ ] Mobile touch controls functional
- [ ] UI responsiveness verified on mobile/desktop

## Test Coverage Required
```
- Unit tests: Chunk coordinate calculation
- Unit tests: LRU cache eviction
- Integration tests: Chunk streaming API calls
- Performance tests: 60 FPS at 1920×1080
- Visual tests: Biome rendering accuracy
- Mobile tests: Touch input responsiveness
```

## Checkpoint Test
```bash
# Run frontend tests
npm test -- tests/chunk-streaming.test.js
npm test -- tests/camera.test.js
npm test -- tests/rendering.test.js

# Visual verification
# 1. Load http://localhost:3000
# 2. Player can move in all directions
# 3. Chunks load seamlessly as player moves
# 4. Biome colors match specification
# 5. FPS counter shows 55-60 FPS

# Mobile test
# Load on mobile device / mobile browser dev tools
# Verify touch controls responsive
# Verify UI legible on small screens
```

## Resume Token
```
✓ PHASE_4_COMPLETE
```

---

# PHASE 5: Marketplace & Payment System
**Duration:** 2-3 hours | **Status:** PENDING

## Input Requirements
- ✓ PHASE_3_COMPLETE and PHASE_4_COMPLETE tokens
- ✓ Land ownership system from Phase 3
- ✓ UI framework from Phase 4

## Deliverables
- [ ] `20_MARKETPLACE_API.md` – Land listing, auction bidding, buy-now endpoints
- [ ] `21_PAYMENT_INTEGRATION.md` – bKash/Nagad/SSLCommerz integration, webhook handling
- [ ] `22_TRANSACTION_SYSTEM.md` – Atomic transactions, double-spend prevention, audit logs
- [ ] `23_PRICING_ALGORITHM.md` – Dynamic pricing calculation, base prices, biome modifiers
- [ ] `24_MARKETPLACE_UI_SPEC.md` – Marketplace dashboard, listing creation, bidding UI

## Output Size
**MEDIUM** (~12-20 KB per file, 60-100 KB total)

## Implementation Checkpoints
- [ ] Payment gateway sandbox integration working
- [ ] Webhook signature validation implemented
- [ ] Idempotent transaction handling (duplicate webhook protection)
- [ ] Database locks prevent race conditions in land transfer
- [ ] Pricing algorithm produces expected results
- [ ] Marketplace UI displays all listings
- [ ] Bidding logic enforces minimum bid increments

## Test Coverage Required
```
- Unit tests: Pricing algorithm calculations
- Unit tests: Bid validation (minimum increments, reserve prices)
- Integration tests: Payment webhook processing
- Integration tests: Atomic transaction commits/rollbacks
- Integration tests: Duplicate webhook idempotency
- Load test: 100 concurrent bid placements on same land
```

## Checkpoint Test
```bash
# Run marketplace tests
pytest tests/test_marketplace.py -v
pytest tests/test_payments.py -v

# Test payment webhook handling
python scripts/test_payment_webhook.py --gateway=bkash

# Verify pricing algorithm
python scripts/test_pricing.py --biome=forest --proximity=center

# Load test concurrent bids
locust -f tests/locustfile_bids.py --users=100 --spawn-rate=10
```

## Resume Token
```
✓ PHASE_5_COMPLETE
```

---

# PHASE 6: Communication & Social Features
**Duration:** 2-3 hours | **Status:** PENDING

## Input Requirements
- ✓ PHASE_3_COMPLETE and PHASE_4_COMPLETE tokens
- ✓ WebSocket API from Phase 2
- ✓ UI framework from Phase 4

## Deliverables
- [ ] `25_CHAT_SYSTEM_API.md` – WebSocket chat, room management, message persistence
- [ ] `26_WEBRTC_INTEGRATION.md` – Voice/video calling, STUN/TURN signaling, peer discovery
- [ ] `27_ENCRYPTION_SPEC.md` – WebCrypto E2EE implementation, key exchange, message format
- [ ] `28_PROXIMITY_LOGIC.md` – Spatial queries, auto-join chat/call groups, presence tracking
- [ ] `29_MESSAGING_UI_SPEC.md` – Chat interface, call UI, presence indicators

## Output Size
**MEDIUM** (~12-20 KB per file, 60-100 KB total)

## Implementation Checkpoints
- [ ] WebSocket server handles 1000+ concurrent connections
- [ ] Chat messages encrypted and decrypted client-side
- [ ] Message history persisted (encrypted at-rest)
- [ ] WebRTC STUN servers configured
- [ ] Voice/video calling initiates within 2 seconds
- [ ] Proximity detection updates in real-time
- [ ] Auto-join chat/call on land entry working

## Test Coverage Required
```
- Unit tests: WebCrypto encryption/decryption
- Unit tests: Proximity detection queries
- Integration tests: WebSocket connection lifecycle
- Integration tests: Message encryption/persistence
- Integration tests: WebRTC peer signaling
- Load test: 100 concurrent chat sessions
- Load test: 10 concurrent voice calls
```

## Checkpoint Test
```bash
# Run communication tests
pytest tests/test_chat.py -v
pytest tests/test_webrtc.py -v

# Test E2EE
python scripts/test_encryption.py

# Load test WebSocket
locust -f tests/locustfile_chat.py --users=100 --spawn-rate=10

# Manual testing
# 1. Open 2 browser windows as different players
# 2. Navigate to same land
# 3. Verify chat message appears encrypted
# 4. Verify auto-join chat room working
# 5. Attempt voice call, verify audio/video
```

## Resume Token
```
✓ PHASE_6_COMPLETE
```

---

# PHASE 7: Admin Panel, Testing & Deployment
**Duration:** 3-4 hours | **Status:** PENDING

## Input Requirements
- ✓ PHASE_3_COMPLETE, PHASE_4_COMPLETE, PHASE_5_COMPLETE, PHASE_6_COMPLETE tokens
- ✓ All core systems from previous phases
- ✓ Deployment infrastructure plan

## Deliverables
- [ ] `30_ADMIN_PANEL_SPEC.md` – Admin dashboard, user management, world controls, price settings
- [ ] `31_ANALYTICS_SYSTEM.md` – Sales metrics, user statistics, regional heatmaps, audit logs
- [ ] `32_TESTING_STRATEGY.md` – Comprehensive test plan, coverage targets, CI/CD pipeline
- [ ] `33_DOCKER_SETUP.md` – Dockerfile, Docker Compose configuration, multi-stage builds
- [ ] `34_DEPLOYMENT_GUIDE.md` – Production deployment steps, database migrations, secrets management
- [ ] `35_MONITORING_LOGGING.md` – Prometheus metrics, Grafana dashboards, ELK stack logging
- [ ] `36_PERFORMANCE_OPTIMIZATION.md` – Caching strategies, database query optimization, load balancing

## Output Size
**LARGE** (~15-25 KB per file, 105-175 KB total)

## Implementation Checkpoints
- [ ] Admin panel accessible only to authenticated admins
- [ ] User suspension/unsuspension working
- [ ] World generation parameters editable by admin
- [ ] Land price modifiers adjustable
- [ ] Analytics dashboard loads historical data
- [ ] Docker images build without errors
- [ ] Docker Compose spins up full stack locally
- [ ] Database migrations run successfully
- [ ] Prometheus scrapes metrics from FastAPI
- [ ] Grafana dashboards display live metrics
- [ ] All tests pass with >80% code coverage

## Test Coverage Required
```
- Unit tests: All services (auth, land, marketplace, chat)
- Integration tests: Multi-step workflows (sign up → buy land → chat)
- End-to-end tests: Full user journeys
- Load tests: 1000 concurrent users, sustained for 10 minutes
- Security tests: SQL injection, XSS, CSRF prevention
- Performance tests: Chunk delivery <200ms, chat latency <500ms
```

## Checkpoint Test
```bash
# Run all tests with coverage
pytest tests/ --cov=app --cov-report=html
npm test -- --coverage

# Build Docker images
docker-compose build

# Start full stack
docker-compose up -d
sleep 30

# Verify stack health
curl http://localhost:8000/health
curl http://localhost:3000/

# Verify database
docker exec virtualworld_db psql -U postgres -d virtualworld -c "SELECT COUNT(*) FROM users;"

# Load test
locust -f tests/locustfile_full.py --users=1000 --spawn-rate=50 --run-time=10m

# Verify monitoring
# 1. Open http://localhost:9090 (Prometheus)
# 2. Open http://localhost:3001 (Grafana)
# 3. Verify metrics being collected
```

## Resume Token
```
✓ PHASE_7_COMPLETE
✓ PROJECT_COMPLETE
```

---

## Cross-Phase Dependencies

```
Phase 1 (Requirements)
    ↓
Phase 2 (Architecture & Design)
    ↓
Phase 3 (Backend Core) + Phase 4 (Frontend Engine) [Parallel]
    ↓
Phase 5 (Marketplace) [Depends on 3 & 4]
    ↓
Phase 6 (Communication) [Depends on 3 & 4]
    ↓
Phase 7 (Admin & Deploy) [Depends on 3, 4, 5, 6]
```

---

## Progress Tracking

| Phase | Status | Token | Output Size | Est. Duration |
|-------|--------|-------|-------------|---|
| 1 | IN PROGRESS | ✓ PHASE_1_COMPLETE | SMALL | 0.5 hrs |
| 2 | PENDING | ✓ PHASE_2_COMPLETE | LARGE | 2-3 hrs |
| 3 | PENDING | ✓ PHASE_3_COMPLETE | LARGE | 4-5 hrs |
| 4 | PENDING | ✓ PHASE_4_COMPLETE | LARGE | 4-5 hrs |
| 5 | PENDING | ✓ PHASE_5_COMPLETE | MEDIUM | 2-3 hrs |
| 6 | PENDING | ✓ PHASE_6_COMPLETE | MEDIUM | 2-3 hrs |
| 7 | PENDING | ✓ PROJECT_COMPLETE | LARGE | 3-4 hrs |
| **TOTAL** | - | - | **HUGE (~500 KB)** | **18-25 hrs** |

---

## Resumption Protocol

If execution is interrupted mid-phase:

1. **Check current token** – Look for the last Resume Token in project files
2. **Skip completed phases** – Resume from first incomplete phase
3. **Review phase input requirements** – Ensure all prerequisites are met
4. **Verify checkpoint tests** – Confirm previous phase deliverables are correct
5. **Continue from phase start** – Begin with next incomplete task

**Example:** If Phase 3 was interrupted at "Land Ownership API":
- Phase 1 & 2: Already complete (skip)
- Phase 3: Resume from "Land Ownership API" task
- Verify Phase 2 outputs exist and are correct
- Continue with Phase 3 remaining tasks

---

**Document Generated:** 2025-11-01
**Last Updated:** 2025-11-01
**Status:** ✓ PHASE_1_TODO_PLAN_COMPLETE
