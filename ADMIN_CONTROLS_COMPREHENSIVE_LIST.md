# Admin Control Panel - Comprehensive Requirements List

## Executive Summary

This document outlines ALL controls that should be available in the admin panel to manage the Virtual Land World and its connected trading systems. Every parameter that affects gameplay, economy, security, or user experience must be controllable.

---

## ✅ CURRENTLY IMPLEMENTED (Existing in Admin Panel)

### 1. Dashboard & Analytics

- ✅ Total users / Active users today
- ✅ Total lands / Owned lands
- ✅ Total listings / Active listings
- ✅ Total transactions / Transactions today
- ✅ Total revenue (BDT)
- ✅ Active chat sessions / Total messages
- ✅ Revenue analytics (daily breakdown, customizable days)
- ✅ User registration trends
- ✅ Land analytics (by biome distribution)

### 2. User Management

- ✅ Search/filter users (pagination, role filter)
- ✅ View user details (profile, balance, lands, transactions)
- ✅ Update user role (admin/user)
- ✅ Adjust user balance (manual BDT adjustment)
- ✅ Suspend user account
- ✅ Unsuspend user account
- ✅ Ban user (with reason & duration)
- ✅ Unban user
- ✅ View user activity history (purchases, sales, lands)

### 3. Marketplace Moderation

- ✅ View all marketplace listings (with filters)
- ✅ Delete/remove listings
- ✅ View all transactions
- ✅ Refund transactions (with reason)
- ✅ Export transactions (CSV/JSON)

### 4. Economy Configuration (Partial)

- ✅ Transaction fee percentage (platform commission)
- ✅ Base land price (BDT)
- ✅ Max/min land price limits
- ✅ Auction bid increment
- ✅ Auction auto-extend minutes

### 5. Feature Toggles

- ✅ Enable/disable land trading
- ✅ Enable/disable chat
- ✅ Enable/disable registration
- ✅ Maintenance mode toggle

### 6. System Limits

- ✅ Max lands per user
- ✅ Max listings per user
- ✅ Auction bid increment
- ✅ Auction extend minutes

### 7. Moderation Tools

- ✅ View chat messages (search, filter by user)
- ✅ Delete messages
- ✅ Mute users (temporary chat ban)
- ✅ View user reports
- ✅ Update report status (pending/reviewed/resolved)

### 8. Announcements & Communication

- ✅ Create system announcements
- ✅ Update announcements
- ✅ Delete announcements
- ✅ Broadcast real-time messages to all users

### 9. Security & Audit

- ✅ View audit logs (filter by category, user, date)
- ✅ View active bans
- ✅ Security event logs
- ✅ System health check (DB, Redis, cache)

### 10. Starter Land Allocation

- ✅ Enable/disable starter land
- ✅ Starter land size (min/max)
- ✅ Buffer units (spacing)
- ✅ Shape variation toggle

---

## ❌ MISSING CRITICAL CONTROLS (Must Be Added)

### 🌍 A. World Generation Controls

**Current Issue:** World seed and generation parameters are in config.py but NOT controllable via admin panel.

#### Required Controls:

- ❌ **World Seed**: Change seed to regenerate world (HIGH RISK - needs migration)
- ❌ **Noise Parameters**:
  - Scale (currently hardcoded: 0.01)
  - Octaves (currently hardcoded: 4)
  - Persistence (currently hardcoded: 0.5)
  - Lacunarity (currently hardcoded: 2.0)
- ❌ **Chunk Generation**:
  - Chunk cache TTL (seconds)
  - Max chunks in memory
  - Cache invalidation controls

#### Impact:

Without these controls, admins cannot:

- Fine-tune terrain appearance
- Adjust world smoothness/detail
- Optimize performance by adjusting cache
- Recover from bad world generation

---

### 💰 B. Land Pricing Controls (Hardcoded in WorldGenerationService)

**Current Issue:** Base prices per biome are hardcoded in `world_service.py` lines 190-200.

#### Hardcoded Values (Should Be Configurable):

```python
base_prices = {
    Biome.PLAINS: 125,   # ❌ Not controllable
    Biome.FOREST: 100,   # ❌ Not controllable
    Biome.BEACH: 90,     # ❌ Not controllable
    Biome.MOUNTAIN: 80,  # ❌ Not controllable
    Biome.DESERT: 55,    # ❌ Not controllable
    Biome.SNOW: 45,      # ❌ Not controllable
    Biome.OCEAN: 30      # ❌ Not controllable
}
```

#### Required Controls:

- ❌ **Base Price per Biome** (7 values)
- ❌ **Elevation Price Factor** (currently ±20%, hardcoded)
- ❌ **Price Formula Toggle** (enable dynamic pricing vs fixed)
- ❌ **Price History/Analytics** per biome

#### Impact:

Admins cannot:

- Adjust economy based on player behavior
- Make rare biomes more expensive
- Run promotions/events (discount certain lands)
- Balance supply/demand

---

### 📊 C. Biome Trading System Controls

**Current Issue:** Critical parameters are hardcoded in service files.

#### Hardcoded Values in `biome_trading_service.py`:

- ❌ **BIOME_TRADE_FEE_PERCENT** = 2.0% (line 23) - NOT controllable
- ❌ Starting market cash per biome = 1,000,000 BDT (line 52)
- ❌ Starting share price = 100.0 BDT (line 54)
- ❌ Starting total shares = 10,000 (line 55)

#### Hardcoded Values in `biome_market_service.py`:

- ❌ **MAX_PRICE_MOVE_PER_CYCLE** = 5% (line 21)
- ❌ **MAX_SINGLE_TRANSACTION_PERCENT** = 10% (line 22)
- ❌ **Redistribution pool** = 25% of TMC (line 134)
- ❌ **Update interval** = 500ms (in worker, needs verification)

#### Required Controls:

- ❌ Biome trade fee percentage (separate from marketplace fee)
- ❌ Max price volatility per cycle (prevent crashes)
- ❌ Max transaction size (% of market cap)
- ❌ Redistribution percentage (currently 25%)
- ❌ Update frequency (how often prices refresh)
- ❌ Market initialization values (cash, shares, starting price)
- ❌ **Emergency Circuit Breakers**:
  - Pause all biome trading
  - Freeze prices
  - Emergency market reset
- ❌ **Attention Weight Algorithm** controls
- ❌ **Market manipulation detection** thresholds

#### Impact:

Without these, admins cannot:

- Prevent market manipulation
- Respond to economic crashes
- Adjust fees based on volume
- Run market events/promotions
- Control price stability

---

### 🏪 D. Marketplace Advanced Controls

**Current Issue:** Many marketplace rules are hardcoded or missing.

#### Required Controls:

- ❌ **Auction Rules**:
  - Minimum auction duration (hours)
  - Maximum auction duration (hours)
  - Minimum bid increment (% or fixed BDT)
  - Anti-sniping extension rules (configurable)
  - Reserve price requirements
- ❌ **Listing Limits**:
  - Max listing duration (days)
  - Max lands per listing (parcel size limit)
  - Cooldown between listings (per user)
- ❌ **Fee Structure**:
  - Listing creation fee (optional)
  - Success fee vs flat fee toggle
  - Tiered fees (by listing value)
  - Premium listing fee (featured placement)
- ❌ **Fraud Prevention**:
  - Max price deviation detection (flag suspicious prices)
  - Auto-reject listings below minimum
  - Wash trading detection threshold
  - Related-account transaction flagging

#### Impact:

Admins cannot:

- Prevent auction manipulation
- Control market velocity
- Detect fraud automatically
- Adjust fees for fairness

---

### 🔐 E. Security & Rate Limiting Controls

**Current Issue:** Security parameters are in config.py but not dynamically controllable.

#### Hardcoded in `config.py`:

- ❌ **JWT_ACCESS_TOKEN_EXPIRE_MINUTES** = 60 (line 52)
- ❌ **JWT_REFRESH_TOKEN_EXPIRE_DAYS** = 7 (line 53)
- ❌ **BCRYPT_ROUNDS** = 12 (line 56)
- ❌ **PASSWORD_MIN_LENGTH** = 12 (line 57)
- ❌ **MAX_LOGIN_ATTEMPTS** = 5 (line 58)
- ❌ **LOCKOUT_DURATION_MINUTES** = 15 (line 59)

#### Required Controls:

- ❌ Token expiration times (access & refresh)
- ❌ Password requirements (length, complexity)
- ❌ Login attempt limits
- ❌ Account lockout duration
- ❌ **Rate Limits** (per endpoint):
  - API requests per minute (per user/IP)
  - Marketplace actions per hour
  - Chat messages per minute
  - Biome trades per minute
  - Land purchases per hour
- ❌ **IP Blocking**:
  - Temporary IP ban (with duration)
  - Permanent IP ban
  - Whitelist/blacklist management
- ❌ **Session Management**:
  - Force logout all users
  - Force logout specific user
  - Max concurrent sessions per user

#### Impact:

Without these:

- Cannot respond to DDoS attacks
- Cannot prevent brute-force login
- Cannot enforce password policies dynamically
- Cannot combat spam/abuse in real-time

---

### 💳 F. Payment Gateway Controls

**Current Issue:** Payment gateway credentials are env-only, no runtime controls.

#### Required Controls:

- ❌ Enable/disable each payment provider:
  - bKash (toggle + test/live mode)
  - Nagad (toggle + test/live mode)
  - Rocket (toggle + test/live mode)
  - SSLCommerz (toggle + test/live mode)
- ❌ **Top-up Limits**:
  - Minimum top-up amount (BDT)
  - Maximum top-up amount (BDT)
  - Daily top-up limit per user
  - Monthly top-up limit per user
- ❌ **Gateway Fees**:
  - Display gateway fees to users
  - Absorb fees vs pass-through toggle
- ❌ **Transaction Monitoring**:
  - Failed payment alerts
  - Suspicious transaction flagging
  - Gateway webhook logs
  - Reconciliation reports

#### Impact:

Admins cannot:

- Switch providers during outages
- Test new payment methods safely
- Control spending limits
- Detect payment fraud

---

### 📧 G. Communication & Notification Controls

#### Required Controls:

- ❌ **Email System**:
  - Enable/disable email notifications
  - Email templates management
  - SMTP configuration (test connection)
  - Email rate limits (prevent spam)
- ❌ **Push Notifications**:
  - Enable/disable by type (chat/trade/land)
  - Notification frequency limits
- ❌ **Chat System Advanced**:
  - Max message length
  - Profanity filter toggle
  - Auto-moderation keywords list
  - Message retention period (days)
  - Private message toggle
  - Group chat limits
- ❌ **Announcement Priority Levels**:
  - Critical (red, force-show)
  - Warning (yellow, dismissible)
  - Info (blue, optional)

---

### 📈 H. Analytics & Reporting (Missing)

#### Required Controls:

- ❌ **Economic Reports**:
  - Money supply tracking (total BDT in system)
  - Wealth distribution (Gini coefficient)
  - Transaction velocity (BDT per day)
  - Top earners/spenders (leaderboard)
- ❌ **Market Health**:
  - Listing success rate (%)
  - Average time to sale
  - Price trends per biome
  - Inventory turnover
- ❌ **User Behavior**:
  - Average session length
  - Retention rate (daily/weekly/monthly)
  - Churn analysis
  - Feature usage stats
- ❌ **System Performance**:
  - API response times (per endpoint)
  - Database query performance
  - Cache hit/miss rates
  - Chunk generation time
  - WebSocket connection stats

---

### 🎮 I. Game Mechanics Controls

#### Required Controls:

- ❌ **Land Fencing**:
  - Fencing cost (per land unit)
  - Fence durability (if implemented)
  - Fence visualization toggle
- ❌ **Parcel Rules**:
  - Max parcel size (total lands)
  - Parcel connectivity rules toggle
  - Allow diagonal connections toggle
- ❌ **Ownership Limits**:
  - Max lands per biome (per user)
  - Max contiguous parcel size
  - Ownership cooldown (time between purchases)
- ❌ **Exploration Incentives**:
  - First-discover bonus (BDT)
  - Rare land spawn rate (%)
  - Special event lands (toggle)

---

### 🔄 J. System Maintenance Controls

#### Required Controls:

- ❌ **Database Maintenance**:
  - Manual cache clear (all/by key pattern)
  - Database vacuum/optimize trigger
  - Index rebuild trigger
  - Orphaned record cleanup
- ❌ **Backup & Recovery**:
  - Manual backup trigger
  - Backup schedule configuration
  - Point-in-time restore interface
- ❌ **Migration Tools**:
  - Run pending migrations
  - Rollback last migration
  - View migration history
- ❌ **Service Monitoring**:
  - Restart backend worker (biome market)
  - WebSocket connection stats
  - Redis connection pool status
  - Database connection pool status
- ❌ **Log Management**:
  - Change log level (dynamically)
  - Download logs (last N lines)
  - Search logs by keyword/timestamp

---

### 🧪 K. Testing & Debugging Tools

#### Required Controls:

- ❌ **Test Data Generation**:
  - Create N test users
  - Generate test lands/listings
  - Simulate market activity
- ❌ **Feature Flags** (A/B Testing):
  - Toggle experimental features
  - Per-user feature access
  - Rollout percentage controls
- ❌ **Debugging Tools**:
  - View user session data
  - Inspect Redis cache keys
  - View WebSocket connections
  - Simulate user actions (impersonation)
- ❌ **Performance Testing**:
  - Stress test chunk generation
  - Load test marketplace
  - Simulate concurrent users

---

## 🎯 PRIORITIZATION MATRIX

### 🔴 CRITICAL (Implement First - Security & Stability)

1. **Biome Trading Circuit Breakers** (prevent market crash)
2. **Rate Limiting Controls** (prevent abuse/DDoS)
3. **Payment Gateway Toggles** (operational necessity)
4. **Emergency Market Reset** (disaster recovery)
5. **IP Blocking** (security)

### 🟠 HIGH PRIORITY (Economic & User Experience)

6. **Biome-specific Land Pricing** (economy balance)
7. **Biome Trade Fee Configuration** (separate from marketplace)
8. **Max Transaction Size (Biome Markets)** (manipulation prevention)
9. **Marketplace Fee Tiers** (fairness)
10. **Auction Duration Limits** (prevent abuse)

### 🟡 MEDIUM PRIORITY (Operational Efficiency)

11. **World Generation Parameters** (terrain tuning)
12. **Cache Management Controls** (performance)
13. **Token Expiration Configuration** (security flexibility)
14. **Email/Notification System** (communication)
15. **Analytics Dashboard Enhancement** (insights)

### 🟢 LOW PRIORITY (Nice to Have)

16. **Test Data Generation** (convenience)
17. **Feature Flags** (experimentation)
18. **A/B Testing Tools** (optimization)
19. **Advanced Debugging** (troubleshooting)

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Security & Economic Stability (Week 1-2)

- [ ] Add biome trade fee configuration (separate from marketplace)
- [ ] Add max price volatility control (biome markets)
- [ ] Add max transaction size control (% of market cap)
- [ ] Add emergency circuit breakers (pause trading, freeze prices)
- [ ] Add rate limiting controls (per endpoint type)
- [ ] Add IP blocking/whitelisting interface
- [ ] Add payment gateway enable/disable toggles

### Phase 2: Economic Controls (Week 3-4)

- [ ] Add biome-specific base prices (7 biomes)
- [ ] Add elevation price factor control
- [ ] Add marketplace fee tier configuration
- [ ] Add auction duration min/max limits
- [ ] Add listing limit cooldown controls
- [ ] Add top-up amount limits (min/max/daily/monthly)

### Phase 3: World Generation (Week 5-6)

- [ ] Add noise parameter controls (scale, octaves, persistence, lacunarity)
- [ ] Add chunk cache TTL control
- [ ] Add cache invalidation tools
- [ ] Add world seed control (WITH MIGRATION WARNING)

### Phase 4: Advanced Features (Week 7-8)

- [ ] Add token expiration configuration
- [ ] Add password policy controls
- [ ] Add email/notification system controls
- [ ] Add chat moderation controls (length, filters, retention)
- [ ] Add analytics dashboard enhancements

### Phase 5: Maintenance & Debugging (Week 9-10)

- [ ] Add cache management tools
- [ ] Add database maintenance triggers
- [ ] Add log management interface
- [ ] Add service monitoring dashboard
- [ ] Add test data generation tools

---

## 🚨 VALIDATION REQUIREMENTS

Every admin control MUST have:

1. **Input Validation** (min/max ranges, type checking)
2. **Authorization** (admin-only, no exceptions)
3. **Audit Logging** (who changed what, when)
4. **Rollback Capability** (undo dangerous changes)
5. **Preview/Dry-Run** (show impact before applying)
6. **Confirmation Modal** (for destructive actions)
7. **Rate Limiting** (prevent admin abuse)
8. **Documentation** (tooltip explaining impact)

---

## 📊 IMPACT ASSESSMENT

### High-Risk Controls (Require Extra Safeguards):

- World seed change (regenerates entire world)
- Market cash reset (wipes economy)
- Ban all users (disaster)
- Delete all listings (irreversible)
- Database vacuum (locks tables)
- Cache clear all (performance hit)

### Medium-Risk Controls:

- Price adjustments (affects fairness)
- Fee changes (affects revenue)
- Rate limit changes (affects UX)
- Feature toggles (breaks functionality)

### Low-Risk Controls:

- UI text changes
- Analytics view filters
- Log level changes
- Announcement creation

---

## 🔗 DEPENDENCIES & INTEGRATION

### Frontend Requirements:

- Add 50+ new form controls in admin panel
- Real-time validation feedback
- Confirmation modals for risky actions
- Audit log viewer component
- Analytics chart components

### Backend Requirements:

- Migrate hardcoded values to database (AdminConfig table)
- Add validation endpoints for each control
- Implement audit logging for all changes
- Add API endpoints for new controls (estimated 40+ new endpoints)
- Add background jobs for system maintenance actions

### Database Requirements:

- Extend AdminConfig table with ~30 new columns
- Add tables: IPBlacklist, RateLimitConfig, PaymentGatewayConfig
- Add audit log retention policy
- Add indexes for performance

---

## 📝 CONCLUSION

**Total Missing Controls: ~80+**

**Critical Gap:** The system currently exposes only ~30% of necessary admin controls. Most economic parameters, security settings, and operational tools are hardcoded or inaccessible via UI.

**Recommendation:** Prioritize Phase 1 (Security & Economic Stability) immediately. Without circuit breakers and rate limiting, the system is vulnerable to market manipulation and abuse.

**Estimated Effort:**

- Phase 1: 2 weeks (critical)
- Phase 2: 2 weeks (high priority)
- Phase 3-5: 6 weeks (complete coverage)
- **Total: 10 weeks for full admin control coverage**
