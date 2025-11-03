# Virtual Land World - Backend

FastAPI-based backend for the Virtual Land World platform.

## Features

- ✅ **FastAPI Framework** - High-performance async Python web framework
- ✅ **PostgreSQL Database** - ACID-compliant data storage with SQLAlchemy ORM
- ✅ **Redis Caching** - High-speed caching and session management
- ✅ **JWT Authentication** - Secure token-based authentication with refresh tokens
- ✅ **Async/Await** - Full async support for maximum performance
- ✅ **Type Safety** - Pydantic models for request/response validation
- ✅ **Comprehensive Models** - All 8 core database models implemented
- ✅ **Security** - OWASP best practices, bcrypt password hashing, E2EE support

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py            # Database base classes
│   │   └── session.py         # Async session management
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py           # User model with auth
│   │   ├── land.py           # Land ownership
│   │   ├── listing.py        # Marketplace listings
│   │   ├── bid.py            # Auction bids
│   │   ├── transaction.py    # Transaction history
│   │   ├── chat.py           # Chat sessions & messages
│   │   ├── audit_log.py      # Immutable audit trail
│   │   └── admin_config.py   # Platform configuration
│   └── services/              # Business logic
│       ├── __init__.py
│       ├── auth_service.py   # JWT token management
│       └── cache_service.py  # Redis caching
├── requirements.txt           # Python dependencies
├── .env.example              # Environment configuration template
└── README.md                 # This file
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+

### Installation

1. **Clone and navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database:**
   ```bash
   # Create PostgreSQL database
   createdb virtualworld

   # Run migrations (or let FastAPI auto-create tables)
   python -m app.main
   ```

6. **Start development server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Database Models

### Core Models Implemented

| Model | Description | Key Features |
|-------|-------------|--------------|
| **User** | User accounts and authentication | JWT auth, bcrypt passwords, account lockout, balance management |
| **Land** | Virtual land parcels | Coordinates, biome, fencing with passcode, ownership tracking |
| **Listing** | Marketplace listings | Auctions, fixed price, buy-now options, auto-extend |
| **Bid** | Auction bids | Status tracking, chronological ordering |
| **Transaction** | Payment history | Immutable audit trail, fee calculation, gateway integration |
| **ChatSession** | Land-based chat rooms | One per land, participant tracking |
| **Message** | Encrypted messages | E2EE payload, initialization vectors |
| **AuditLog** | Event logging | Immutable compliance logs |
| **AdminConfig** | Platform settings | World generation, pricing, fees |

## API Endpoints

### Planned Endpoints (to be implemented)

#### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Logout

#### Users
- `GET /users/{user_id}` - Get user profile
- `PUT /users/{user_id}` - Update profile
- `GET /users/{user_id}/balance` - Get balance
- `POST /users/{user_id}/topup` - Top up balance

#### Lands
- `GET /lands/{land_id}` - Get land details
- `GET /lands` - Search lands
- `POST /lands/{land_id}/fence` - Enable/disable fence
- `POST /lands/{land_id}/transfer` - Transfer ownership

#### Chunks (World Generation)
- `GET /chunks/{chunk_id}` - Get generated chunk
- `POST /chunks/batch` - Batch chunk retrieval

#### Marketplace
- `POST /listings` - Create listing
- `GET /listings` - Browse listings
- `POST /listings/{id}/bids` - Place bid
- `POST /listings/{id}/buy-now` - Instant purchase

#### Admin
- `GET /admin/dashboard` - Dashboard overview
- `PUT /admin/world/config` - Update world config
- `GET /admin/analytics` - Platform analytics

## Development

### Running Tests

```bash
pytest tests/ --cov=app
```

### Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Environment Variables

See `.env.example` for all configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `JWT_SECRET_KEY` - Secret key for JWT tokens (CHANGE IN PRODUCTION!)
- `BKASH_API_KEY`, etc. - Payment gateway credentials

## Security

- ✅ JWT tokens with refresh token rotation
- ✅ bcrypt password hashing (12 rounds)
- ✅ Account lockout after 5 failed attempts
- ✅ CORS configuration
- ✅ Rate limiting support (Redis-based)
- ✅ Input validation with Pydantic
- ✅ Parameterized SQL queries (SQLAlchemy ORM)
- ✅ E2EE message encryption support

## Performance

- Async/await throughout for concurrent operations
- Redis caching for frequently accessed data
- Database connection pooling
- Lazy loading and pagination
- Optimized indexes on hot queries

## License

Proprietary - Virtual Land World Team

## Status

**Phase 1 Backend Foundation: 60% Complete**

✅ Completed:
- Project structure
- Configuration management
- All database models (User, Land, Listing, Bid, Transaction, Chat, Audit, Config)
- Authentication service (JWT)
- Cache service (Redis)
- FastAPI main application
- Health check endpoints
- Error handling
- Logging setup

🔄 In Progress:
- API routers and endpoints
- World generation service
- Payment gateway integration
- WebSocket communication
- Admin services

⏳ Pending:
- API endpoint implementation
- WebSocket manager
- Background workers
- Integration tests
- Docker deployment

**Next Steps:** Implement API routers (auth, users, lands, chunks, marketplace)
