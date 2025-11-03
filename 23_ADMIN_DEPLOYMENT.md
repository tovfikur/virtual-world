# Virtual Land World - Admin Panel & Deployment

## Admin Dashboard API

```python
# app/api/v1/endpoints/admin.py

@router.get("/admin/dashboard")
async def admin_dashboard(
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard overview."""
    today = datetime.utcnow().date()

    daily_sales = await db.query(
        func.sum(Transaction.amount_bdt)
    ).filter(
        func.date(Transaction.created_at) == today
    ).scalar()

    active_users = await db.query(User).filter(
        User.created_at > datetime.utcnow() - timedelta(days=30)
    ).count()

    total_transactions = await db.query(Transaction).count()

    return {
        "daily_sales_bdt": daily_sales or 0,
        "active_users": active_users,
        "total_transactions": total_transactions,
        "platform_fee_percent": 5
    }

@router.put("/admin/world/config")
async def update_world_config(
    config: dict,
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Update world generation configuration."""
    admin_config = await db.query(AdminConfig).first()

    admin_config.world_seed = config.get("world_seed")
    admin_config.noise_frequency = config.get("noise_frequency")
    admin_config.noise_octaves = config.get("noise_octaves")

    await db.commit()

    # Invalidate chunk cache
    await cache_service.delete("chunk:*")

    return {"message": "World config updated"}

@router.put("/admin/pricing")
async def update_pricing(
    pricing: dict,
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Update land pricing."""
    config = await db.query(AdminConfig).first()

    config.base_land_price_bdt = pricing.get("base_price", 1000)
    config.transaction_fee_percent = pricing.get("fee_percent", 5.0)

    await db.commit()
    return {"message": "Pricing updated"}

@router.get("/admin/analytics")
async def get_analytics(
    date_from: str = Query(...),
    date_to: str = Query(...),
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Get platform analytics."""
    from_date = datetime.fromisoformat(date_from).date()
    to_date = datetime.fromisoformat(date_to).date()

    total_sales = await db.query(
        func.sum(Transaction.amount_bdt)
    ).filter(
        Transaction.created_at.between(from_date, to_date)
    ).scalar()

    new_users = await db.query(User).filter(
        User.created_at.between(from_date, to_date)
    ).count()

    return {
        "period": {"from": str(from_date), "to": str(to_date)},
        "total_sales_bdt": total_sales or 0,
        "new_users": new_users,
        "average_transaction": (total_sales or 0) // max(1, new_users)
    }

@router.get("/admin/audit-logs")
async def get_audit_logs(
    limit: int = Query(100),
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Get immutable audit logs."""
    logs = await db.query(AuditLog).order_by(
        AuditLog.created_at.desc()
    ).limit(limit).all()

    return {
        "logs": [
            {
                "event": log.event_type,
                "actor": log.actor_id,
                "resource": log.resource_type,
                "action": log.action,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
    }
```

## Docker Deployment

```dockerfile
# Dockerfile (backend)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml (production)

version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: virtualworld
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db/virtualworld
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

volumes:
  postgres_data:
```

## Monitoring & Logging

```python
# Prometheus metrics endpoint

from prometheus_client import Counter, Histogram, Gauge

request_count = Counter('requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('request_duration_seconds', 'Request duration', ['endpoint'])
active_connections = Gauge('websocket_connections_active', 'Active WebSocket connections')

# Add to FastAPI
@app.middleware("http")
async def add_prometheus_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    request_count.labels(request.method, request.url.path).inc()
    request_duration.labels(request.url.path).observe(duration)
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest())
```

```yaml
# prometheus.yml

global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'virtualworld'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

## Database Migrations

```bash
# Initialize migrations
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Downgrade
alembic downgrade -1
```

## Testing

```bash
# Backend tests
pytest tests/ --cov=app

# Frontend tests
npm test -- --coverage

# Load testing
locust -f locustfile.py --users=1000 --spawn-rate=50
```

## Deployment Checklist

- [ ] Database initialized with migrations
- [ ] Redis configured and running
- [ ] Environment variables set (.env)
- [ ] SSL certificates installed
- [ ] Backup strategy configured
- [ ] Monitoring (Prometheus/Grafana) active
- [ ] Logging (ELK stack) configured
- [ ] Rate limiting enabled
- [ ] CORS configured
- [ ] Admin user created
- [ ] Payment gateways configured
- [ ] CDN configured (Cloudflare)
- [ ] Health check endpoints verified
- [ ] Load testing completed
- [ ] Security audit completed

**Resume Token:** `✓ PHASE_7_COMPLETE`
**✓ PROJECT_COMPLETE** - All 23 specification documents generated successfully!
