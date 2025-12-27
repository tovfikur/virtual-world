# Admin Controls Implementation Tracker

Statuses: ✅ Done · 🔄 In Progress · ⏳ Not Started

## Completed (72)

- ✅ Biome trade fee configuration (AdminConfig + API + services)
- ✅ Market volatility control (max price move per cycle)
- ✅ Max transaction size control (% of market cap)
- ✅ Redistribution pool percentage control
- ✅ Emergency circuit breaker controls (pause trading, freeze prices)
- ✅ Biome-specific base land prices (7 biomes)
- ✅ Elevation price factor control
- ✅ Marketplace fee tier configuration
- ✅ Auction duration limits (min/max hours)
- ✅ Auction minimum bid increment enforcement
- ✅ IP blocking/whitelisting admin controls (tables, admin endpoints, middleware stub)
- ✅ Rate limiting controls (configurable per category via admin API)
- ✅ Payment gateway toggles/modes and top-up limits
- ✅ Marketplace listing limits (max lands per listing, max duration days, listing cooldown, min reserve %)
- ✅ Auction anti-sniping config (enable + threshold/extend minutes)
- ✅ Rate limiting enforcement (API + marketplace + chat + biome trades)
- ✅ Token expiration configuration (admin-controlled access/refresh lifetimes)
- ✅ Password policy controls (length and complexity enforced on registration)
- ✅ Login attempt limits & lockout duration (admin-configurable)
- ✅ Session management (max sessions per user)
- ✅ Gateway fee handling (absorb vs pass-through with percent/flat fee)
- ✅ Payment monitoring (webhook event logs endpoint)
- ✅ Payment monitoring alerts & reconciliation summary
- ✅ Cache management tools (clear all/by prefix)
- ✅ Email system controls (enable/disable, SMTP config, rate limits)
- ✅ Log management (log level toggle)
- ✅ Push notification toggles by type/frequency
- ✅ Quiet hours + push daily limits
- ✅ Chat moderation controls (length, profanity, keywords, retention, PM toggle, group limits)
- ✅ Announcement priority levels and rate limits
- ✅ Database maintenance triggers (vacuum/analyze)
- ✅ Migration tools (run pending, rollback last, view history)
- ✅ Backup/restore controls (manual pg_dump/pg_restore triggers)
- ✅ Database index maintenance (REINDEX database/table)
- ✅ Service monitoring (DB pool stats, cache/websocket health)
- ✅ World seed + noise/biome distribution controls
- ✅ Chunk cache TTL controls
- ✅ Chunk cache invalidation tools (chunk/all)
- ✅ Chunk cache invalidation scheduling (interval + max age)
- ✅ Minimum reserve price requirements
- ✅ Listing creation fee / premium listing fee
- ✅ Success fee vs flat fee toggle
- ✅ Max price deviation detection / fraud flags
- ✅ Parcel size limit
- ✅ Cooldown between listings
- ✅ Max listing duration (days) beyond auctions
- ✅ Economic reports (money supply, revenue summary)
- ✅ Market health metrics (success rate, time to sale, active inventory)
- ✅ User behavior metrics (DAU window)
- ✅ System performance metrics (pool/cache/ws snapshot)
- ✅ Economic reports (Gini, top balances)
- ✅ Market health price trends (avg listing/txn price window)
- ✅ User retention/churn snapshot
- ✅ API latency probes (DB/cache)
- ✅ Economic velocity (volume/money supply)
- ✅ Top earners (seller revenue window)
- ✅ Query performance telemetry (key table timings)
- ✅ Fraud detection thresholds (wash trading, related accounts, price deviation auto-reject)
- ✅ Biome market initialization (initial cash, shares, starting price, update frequency, algorithm version)
- ✅ Attention-weight algorithm controls (version + 5 parameter fields)
- ✅ Market manipulation detection thresholds (price spikes, order clustering, pump-and-dump)
- ✅ Emergency market reset controls (8 configuration fields for comprehensive recovery)
- ✅ Price formula toggle (dynamic vs fixed pricing with influence factors)
- ✅ Fencing cost controls (enable/cost/maintenance/durability)
- ✅ Parcel rules toggles (connectivity, diagonal allowed, min/max size)
- ✅ Ownership limits (max lands per user/biome, contiguous size, cooldown)
- ✅ Exploration incentives (first-discover bonus, rare land spawn rate, bonus multipliers)
- ✅ Wash trading detection enforcement (toggle + optional temp suspend)
- ✅ Related account linkage detection enforcement (toggle)
- ✅ Auto-reject transaction rules based on price deviation (toggle)
- ✅ Admin audit logging coverage (20+ endpoints with create_audit_log)
- ✅ Confirmation/preview flows for high-risk actions (market reset, user ban, fraud enforcement)

## In Progress (0)

- None right now.

## Not Started / Pending (~55)

### Biome Trading & Market Stability

- COMPLETED

### World Generation

- COMPLETED (all, including optional cache invalidation scheduling)

### Land Pricing & Mechanics

- COMPLETED

### Communication & Notifications

### Analytics & Reporting

### Maintenance & Operations

- ⏳ Worker restart trigger (if/when background workers are introduced)

### Testing & Debugging

- ⏳ Test data generation (users, lands, listings, market activity)
- ⏳ Feature flags / A/B testing controls
- ⏳ Debugging tools (session inspect, Redis inspect, WS connections)
- ⏳ Performance/load testing triggers

### Payment & Fraud

// COMPLETED IN THIS PASS

### Misc Governance

// COMPLETED IN THIS PASS

## Notes

- Completed items are already backed by migrations, services, and admin API endpoints.
- Remaining items will be implemented sequentially with migrations, service logic, and admin API exposure.
