# Virtual Land World - Deployment Guide

Complete guide for deploying the Virtual Land World platform to production.

## 🚀 Quick Start (Docker Compose)

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Domain name (for SSL)
- 4GB+ RAM
- 20GB+ disk space

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/yourusername/virtual-land-world.git
cd virtual-land-world

# Copy environment template
cp .env.production .env

# Edit .env with your production values
nano .env
```

**Required Changes in .env:**

- `DB_PASSWORD` - Strong database password
- `REDIS_PASSWORD` - Strong Redis password
- `JWT_SECRET_KEY` - Generate with `openssl rand -hex 32`
- `ENCRYPTION_KEY` - Generate with `openssl rand -hex 32`
- `CORS_ORIGINS` - Your production domain(s)

### 2. Build and Start

```bash
# Build images
docker compose pull
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 3. Initialize Database

```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Create initial admin user (optional)
docker compose exec backend python -c "
from app.models.user import User
from app.db.session import SessionLocal
import bcrypt

db = SessionLocal()
admin = User(
    username='admin',
    email='admin@example.com',
    password_hash=bcrypt.hashpw('ChangeMe123!'.encode(), bcrypt.gensalt()).decode(),
    role='admin',
    balance_bdt=1000000
)
db.add(admin)
db.commit()
print('Admin user created!')
"
```

### 4. Frontend Build & Serve

Handled by Docker Compose via the `frontend` service. If you need to build locally for debugging:

```bash
cd frontend
npm install
npm run build
# Outputs to frontend/dist/ (containers normally handle serving)
```

### 5. Access Application

- Frontend: `http://localhost`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/api/docs`
- Health Check: `http://localhost:8000/health`

---

## 🔧 Manual Setup (Without Docker)

Note: Native/manual setup is provided for reference and development-only. Production and standard local usage should use Docker Compose.

### Backend Setup

#### 1. Install Dependencies

```bash
# Install Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip postgresql-15 redis-server

# Create virtual environment
cd backend
python3.11 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

#### 2. Configure PostgreSQL

```bash
# Create database and user
sudo -u postgres psql

CREATE DATABASE virtualworld;
CREATE USER virtualworld WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE virtualworld TO virtualworld;
\q
```

#### 3. Configure Environment

```bash
# Copy and edit .env
cp .env.example .env
nano .env

# Update DATABASE_URL and other settings
```

#### 4. Run Migrations

```bash
alembic upgrade head
```

#### 5. Start Backend

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (with Gunicorn)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Frontend Setup

#### 1. Install Node.js

```bash
# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

#### 2. Build Frontend

```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Serve with a static server
npx serve -s dist -l 3000
```

### Nginx Setup

#### 1. Install Nginx

```bash
sudo apt install nginx
```

#### 2. Configure Nginx

```bash
# Copy nginx config
sudo cp nginx/nginx.conf /etc/nginx/nginx.conf

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 🔒 SSL/TLS Setup (HTTPS)

### Using Let's Encrypt (Certbot)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is enabled by default
# Test renewal
sudo certbot renew --dry-run
```

### Manual SSL Certificate

```bash
# Create SSL directory
mkdir -p nginx/ssl

# Copy your certificates
cp your_domain.crt nginx/ssl/
cp your_domain.key nginx/ssl/

# Update nginx.conf to use SSL
```

---

## 📊 Monitoring & Logs

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Health Checks

```bash
# Application health
curl http://localhost/health

# Database health
curl http://localhost/health/db

# Redis health
curl http://localhost/health/cache
```

### Monitoring Stack (Optional)

Add to `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  depends_on:
    - prometheus
```

---

## 🔄 Updates & Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head
```

### Backup Database

```bash
# Create backup
docker-compose exec postgres pg_dump -U virtualworld virtualworld > backup_$(date +%Y%m%d).sql

# Restore from backup
docker-compose exec -T postgres psql -U virtualworld virtualworld < backup_20231201.sql
```

### Backup Redis

```bash
# Redis automatically creates dump.rdb
# Copy from container
docker cp virtualworld-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

---

## 🐛 Troubleshooting

### Backend Won't Start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Database connection - check DATABASE_URL
# 2. Redis connection - check REDIS_URL
# 3. Missing migrations - run: alembic upgrade head
# 4. Port conflict - check if 8000 is available
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U virtualworld -d virtualworld

# Reset database (CAUTION: deletes all data)
docker-compose down -v
docker-compose up -d postgres
docker-compose exec backend alembic upgrade head
```

### Redis Connection Failed

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# With password
docker-compose exec redis redis-cli -a your_password ping
```

### Frontend Not Loading

```bash
# Check if built
ls frontend/dist/

# Rebuild
cd frontend
npm run build

# Check Nginx logs
docker-compose logs nginx
```

### WebSocket Connection Failed

```bash
# Check Nginx WebSocket configuration
# Ensure these headers are set:
# - Upgrade: websocket
# - Connection: Upgrade

# Test WebSocket
wscat -c ws://localhost/api/v1/ws/connect?token=YOUR_TOKEN
```

---

## ⚡ Performance Tuning

### Database Optimization

```sql
-- Add indexes (if not exists)
CREATE INDEX idx_lands_owner ON lands(owner_id);
CREATE INDEX idx_lands_coordinates ON lands(x, y);
CREATE INDEX idx_listings_status ON listings(status);

-- Analyze tables
ANALYZE;
```

### Redis Configuration

```bash
# Edit redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

### Nginx Tuning

```nginx
# In nginx.conf http block
worker_processes auto;
worker_connections 2048;
keepalive_timeout 65;
client_max_body_size 20M;
```

### Backend Scaling

```bash
# Increase workers in docker-compose.yml
environment:
  - WORKERS=4  # 2 * CPU cores

# Or with Gunicorn
gunicorn app.main:app --workers 8 --worker-class uvicorn.workers.UvicornWorker
```

---

## 🔐 Security Checklist

- [ ] Change all default passwords
- [ ] Generate strong JWT_SECRET_KEY and ENCRYPTION_KEY
- [ ] Enable SSL/TLS (HTTPS)
- [ ] Configure firewall (allow 80, 443, block 8000, 5432, 6379)
- [ ] Set CORS_ORIGINS to your domain only
- [ ] Enable rate limiting in Nginx
- [ ] Regular security updates: `apt update && apt upgrade`
- [ ] Regular backups (database + Redis)
- [ ] Monitor logs for suspicious activity
- [ ] Use secrets manager for production (AWS Secrets, Vault, etc.)

---

## 📈 Scaling to Multiple Servers

### Load Balancer Setup

```nginx
upstream backend_servers {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

server {
    location /api/ {
        proxy_pass http://backend_servers;
    }
}
```

### Redis Cluster

```bash
# Use Redis Cluster or Redis Sentinel for HA
# Update REDIS_URL to cluster endpoints
```

### Database Replication

```bash
# Setup PostgreSQL primary-replica
# Point read queries to replicas
# Keep writes on primary
```

---

## 📝 Environment Variables Reference

See `.env.production` for full list. Key variables:

| Variable             | Required | Description                   |
| -------------------- | -------- | ----------------------------- |
| `DATABASE_URL`       | Yes      | PostgreSQL connection string  |
| `REDIS_URL`          | Yes      | Redis connection string       |
| `JWT_SECRET_KEY`     | Yes      | JWT signing key (32+ chars)   |
| `ENCRYPTION_KEY`     | Yes      | Message encryption key        |
| `CORS_ORIGINS`       | Yes      | Allowed origins for CORS      |
| `DEFAULT_WORLD_SEED` | No       | World generation seed         |
| `LOG_LEVEL`          | No       | Logging level (default: INFO) |

---

## 🌐 Domain & DNS Configuration

### DNS Records

```
A     yourdomain.com          -> YOUR_SERVER_IP
A     www.yourdomain.com      -> YOUR_SERVER_IP
CNAME api.yourdomain.com      -> yourdomain.com
CNAME ws.yourdomain.com       -> yourdomain.com
```

### Update CORS

```bash
# In .env
CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
```

---

## 📞 Support

- **Documentation:** See README.md
- **Issues:** Create issue on GitHub
- **Logs:** Check `docker-compose logs`

---

**Deployment Complete! 🎉**

Your Virtual Land World is now running in production.
