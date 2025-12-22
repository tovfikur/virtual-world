# Admin System Architecture Diagram

## System Component Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application                        │
│                     /api/v1/admin/trading/* Routes                 │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│                      API Endpoint Layer (25+)                       │
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ Instrument Ctrl  │  │ Market Controls  │  │ Risk/Fee Config │  │
│  │      (4 pts)     │  │      (3 pts)     │  │      (4 pts)    │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ Broker Mgmt      │  │ Surveillance     │  │ Admin Users     │  │
│  │      (3 pts)     │  │      (5 pts)     │  │      (3+ pts)   │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│                    Service Layer (3 Services)                       │
├──────────────────────┬──────────────────────┬─────────────────────┤
│   AdminService       │   BrokerService      │ SurveillanceService │
│   (450+ lines)       │   (350+ lines)       │   (380+ lines)      │
├──────────────────────┼──────────────────────┼─────────────────────┤
│ ✓ Permissions        │ ✓ Broker Accounts    │ ✓ Spoofing Detect   │
│ ✓ Instrument Ctrl    │ ✓ Sub-Accounts       │ ✓ Wash Trading Det  │
│ ✓ Market Controls    │ ✓ A/B-Book Routing   │ ✓ Front-Run Detect  │
│ ✓ Risk Config        │ ✓ Commission Mgmt    │ ✓ Volume Anomaly    │
│ ✓ Fee Config         │ ✓ Credit Mgmt        │ ✓ Alert Management  │
│ ✓ Audit Logging      │ ✓ Exposure Hedging   │ ✓ Resolution Track  │
└──────────────────────┴──────────────────────┴─────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│                  SQLAlchemy ORM Model Layer (10)                    │
├────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│ │ AdminUser       │  │ InstrumentControl│  │ MarketControl    │   │
│ │ • role          │  │ • is_halted      │  │ • market_open    │   │
│ │ • is_active     │  │ • limits         │  │ • order_rate     │   │
│ └─────────────────┘  │ • circuit_brk    │  │ • circuit_brk    │   │
│                      └──────────────────┘  └──────────────────┘   │
│ ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│ │ RiskConfigurable│  │ FeeConfig        │  │ BrokerAccount    │   │
│ │ • margin        │  │ • maker_fee      │  │ • broker_id      │   │
│ │ • liquidation   │  │ • taker_fee      │  │ • book_type      │   │
│ │ • max_position  │  │ • funding_fee    │  │ • credit_limit   │   │
│ └─────────────────┘  └──────────────────┘  │ • api_key        │   │
│                                             └──────────────────┘   │
│ ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│ │ SurveillanceAlrt│  │ AuditAction      │  │ ComplianceReport │   │
│ │ • anomaly_type  │  │ • action_type    │  │ • report_type    │   │
│ │ • severity      │  │ • old_values     │  │ • findings       │   │
│ │ • evidence      │  │ • new_values     │  │ • period         │   │
│ │ • is_resolved   │  │ • approval_status│  └──────────────────┘   │
│ └─────────────────┘  └──────────────────┘                          │
└────────────────────────────────────────────────────────────────────┘
                                    ↓
┌────────────────────────────────────────────────────────────────────┐
│              PostgreSQL Database Layer (10 Tables)                  │
├────────────────────────────────────────────────────────────────────┤
│ admin_users | instrument_controls | market_controls | risk_config  │
│ fee_config | broker_accounts | surveillance_alerts | audit_actions │
│ compliance_reports | regulatory_exemptions                         │
└────────────────────────────────────────────────────────────────────┘
```

## Request Flow Diagram

```
Client Request
       ↓
┌─────────────────────────────────────┐
│ Authenticate & Verify Admin Role    │
│ (get_current_user dependency)       │
└─────────────────────────────────────┘
       ↓ (Role check fails)      (Pass)
    Error 403                      ↓
                      ┌───────────────────────┐
                      │ Route to API Endpoint │
                      │ (Instrument/Market)   │
                      └───────────────────────┘
                              ↓
            ┌─────────────────────────────────┐
            │ Call Service Method             │
            │ (AdminService/BrokerService)    │
            └─────────────────────────────────┘
                      ↓
         ┌────────────────────────────┐
         │ Query/Update Database      │
         │ (SQLAlchemy ORM)           │
         └────────────────────────────┘
                      ↓
         ┌────────────────────────────┐
         │ Create Audit Log Entry     │
         │ (Record all changes)       │
         └────────────────────────────┘
                      ↓
         ┌────────────────────────────┐
         │ Format JSON Response       │
         │ (Status, data, timestamps) │
         └────────────────────────────┘
                      ↓
               Client Response
```

## Role Hierarchy & Permissions

```
┌──────────────────────────────────────────────────────────────┐
│                        SUPER_ADMIN (4)                        │
│                                                               │
│  • Create admin users of any role                            │
│  • Modify role hierarchy                                     │
│  • System-wide configuration                                 │
│  + All ADMIN, OPERATOR, VIEWER permissions                   │
└──────────────────────────────────────────────────────────────┘
                            ↑
                    (hierarchy inheritance)
                            ↑
┌──────────────────────────────────────────────────────────────┐
│                        ADMIN (3)                              │
│                                                               │
│  • Halt/resume entire market                                 │
│  • Update risk configuration                                 │
│  • Update fee configuration                                  │
│  • Create broker accounts                                    │
│  + All OPERATOR and VIEWER permissions                       │
└──────────────────────────────────────────────────────────────┘
                            ↑
                    (hierarchy inheritance)
                            ↑
┌──────────────────────────────────────────────────────────────┐
│                        OPERATOR (2)                           │
│                                                               │
│  • Halt/resume individual instruments                        │
│  • Update instrument limits                                  │
│  • Create/manage broker accounts                             │
│  • Resolve surveillance alerts                               │
│  • Create broker sub-accounts                                │
│  + All VIEWER permissions                                    │
└──────────────────────────────────────────────────────────────┘
                            ↑
                    (hierarchy inheritance)
                            ↑
┌──────────────────────────────────────────────────────────────┐
│                        VIEWER (1)                             │
│                                                               │
│  • View market status                                        │
│  • View instrument controls                                  │
│  • View risk configuration                                   │
│  • View fee configuration                                    │
│  • View surveillance alerts                                  │
│  • View broker details                                       │
│                                                               │
│  (Read-only access to all controls)                          │
└──────────────────────────────────────────────────────────────┘
```

## Data Model Relationships

```
AdminUser ─────┬──────→ Account
               │
               └──────→ AuditAction

InstrumentControl ───→ Instrument

BrokerAccount ──┬──────→ Account (multiple sub-accounts)
                │
                └──────→ BrokerSubAccount

SurveillanceAlert ─┬──────→ Account
                   ├──────→ Instrument
                   ├──────→ Trade[] (evidence)
                   └──────→ Order[] (evidence)

AuditAction ────────→ AdminUser
                 or
                 → Account (who took action)

ComplianceReport ──┬──────→ Account
                   ├──────→ Instrument
                   └──────→ Trade[]

Trade ───────────────→ SurveillanceAlert (if suspected)

Order ───────────────→ SurveillanceAlert (if suspected)
```

## Anomaly Detection Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│              Real-Time Market Data Stream                     │
│       (Orders, Trades, Market Data Updates)                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │  Surveillance Pattern Matcher         │
        │  (SurveillanceService)                │
        └───────────────────────────────────────┘
                    ↓
     ┌──────────────┼──────────────┐
     ↓              ↓              ↓
┌─────────┐   ┌──────────┐   ┌───────────┐
│ Spoofing│   │Wash Trade│   │Front-Run  │
│Detector │   │ Detector │   │ Detector  │
├─────────┤   ├──────────┤   ├───────────┤
│>80% cancel  │buy/sell  │   │trades b4  │
│without fill │within 5m │   │large order│
└─────────┘   └──────────┘   └───────────┘
     ↓              ↓              ↓
     └──────────────┼──────────────┘
                    ↓
        ┌───────────────────────────────────┐
        │   Create SurveillanceAlert        │
        │   • anomaly_type                  │
        │   • severity (critical/high/med)  │
        │   • evidence data                 │
        │   • timestamp                     │
        └───────────────────────────────────┘
                    ↓
        ┌───────────────────────────────────┐
        │  Store in Database & Alert Admin  │
        │  (Admin reviews & resolves)       │
        └───────────────────────────────────┘
```

## Fee Configuration Application Flow

```
Current Time ──→ Check Effective Dates
                        ↓
         ┌──────────────────────────────┐
         │ Find Active FeeConfig Entry  │
         │ (where effective_from ≤ now) │
         └──────────────────────────────┘
                        ↓
         ┌──────────────────────────────┐
         │ Load Fee Parameters          │
         │ • maker_fee: 0.02%           │
         │ • taker_fee: 0.05%           │
         │ • funding_fee: 0.015%        │
         │ • swap_fee: 0.02%            │
         └──────────────────────────────┘
                        ↓
         ┌──────────────────────────────┐
         │ Check Volume Tiers           │
         │ • <100k: base fee            │
         │ • 100k-1m: 90% of base       │
         │ • >1m: 80% of base           │
         └──────────────────────────────┘
                        ↓
         ┌──────────────────────────────┐
         │ Calculate Fee Amount         │
         │ = order_value × adjusted_fee │
         └──────────────────────────────┘
                        ↓
         ┌──────────────────────────────┐
         │ Deduct from Account Balance  │
         │ Update PnL & Fee Accrual     │
         └──────────────────────────────┘
```

## Broker Credit Management Cycle

```
┌──────────────────────────────────────────┐
│ Create Broker with $1,000,000 Credit     │
│ • credit_limit = 1,000,000               │
│ • credit_utilized = 0                    │
│ • available = 1,000,000                  │
└──────────────────────────────────────────┘
                    ↓
         Trade Executes (500k notional)
                    ↓
┌──────────────────────────────────────────┐
│ Broker Credit In Use                     │
│ • utilize_credit(500,000)                │
│ • credit_utilized = 500,000              │
│ • available = 500,000                    │
│ • Margin Check: PASS ✓                   │
└──────────────────────────────────────────┘
                    ↓
         Another Trade (600k notional)
                    ↓
┌──────────────────────────────────────────┐
│ Insufficient Credit!                     │
│ • Request: 600,000                       │
│ • Available: 500,000                     │
│ • Action: REJECT ORDER ✗                 │
│ • Notify broker to free up credit        │
└──────────────────────────────────────────┘
                    ↓
         Broker closes positions (300k)
                    ↓
┌──────────────────────────────────────────┐
│ Credit Released                          │
│ • release_credit(300,000)                │
│ • credit_utilized = 200,000              │
│ • available = 800,000                    │
│ • Can retry order: YES ✓                 │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│ Commission Payment                       │
│ • accrue_commission(5,000)               │
│ • payout_commission(3,000)               │
│ • commission_accrued = 2,000             │
└──────────────────────────────────────────┘
```

---

This architecture provides:

- ✅ Scalable design with clear separation of concerns
- ✅ Flexible role-based access control
- ✅ Real-time anomaly detection
- ✅ Comprehensive audit trail
- ✅ Dynamic fee and risk configuration
- ✅ Broker partner management with credit enforcement
