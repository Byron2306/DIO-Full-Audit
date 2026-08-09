# Seraph AI Defense System - Deployment Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Configuration](#configuration)
4. [Deployment Options](#deployment-options)
5. [VPN Setup](#vpn-setup)
6. [Agent Deployment](#agent-deployment)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Droplet Reinstall](#droplet-reinstall)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Linux server (Ubuntu 22.04+ recommended)
- 4GB+ RAM, 2+ CPU cores
- Kernel 5.6+ (for WireGuard VPN)

### 3-Step Deployment

```bash
# 1. Clone the repository
git clone https://github.com/your-org/seraph-ai-defense.git
cd seraph-ai-defense

# 2. Configure environment
cp .env.example .env
nano .env  # Set JWT_SECRET and VPN_SERVER_ENDPOINT

# 3. Deploy
docker-compose up -d
```

**Access Points:**
- 🖥️ **Web UI**: http://your-server:3000
- 🔌 **API**: http://your-server:8001/api
- 🔐 **VPN**: your-server:51820/udp

---

## System Requirements

### Minimum Requirements
| Component | Requirement |
|-----------|-------------|
| OS | Linux (Ubuntu 22.04+, Debian 12+, CentOS 9+) |
| RAM | 4 GB |
| CPU | 2 cores |
| Disk | 20 GB |
| Kernel | 5.6+ (WireGuard support) |

### Recommended for Production
| Component | Requirement |
|-----------|-------------|
| RAM | 8+ GB |
| CPU | 4+ cores |
| Disk | 100+ GB SSD |
| Network | 100+ Mbps |

### Required Ports
| Port | Protocol | Service |
|------|----------|---------|
| 3000 | TCP | Frontend UI |
| 8001 | TCP | Backend API |
| 27017 | TCP | MongoDB (internal) |
| 51820 | UDP | WireGuard VPN |

---

## Configuration

### Essential Settings (.env)

```bash
# REQUIRED - Generate with: openssl rand -base64 64
JWT_SECRET=your-64-character-random-secret-key

# REQUIRED - Your server's public IP or domain
VPN_SERVER_ENDPOINT=vpn.yourdomain.com

# Optional - Number of VPN client configs to generate
VPN_PEERS=10

# Optional - For production with custom domain
REACT_APP_BACKEND_URL=https://api.yourdomain.com
```

### Elasticsearch Integration (Optional)

```bash
ELASTICSEARCH_URL=https://your-elastic-cluster:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=your-password
```

### Notification Services (Optional)

```bash
# Slack alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz

# Email via SendGrid
SENDGRID_API_KEY=your-api-key
SENDGRID_FROM_EMAIL=alerts@yourdomain.com

# SMS via Twilio
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_FROM_NUMBER=+1234567890
```

---

## Deployment Options

### Option 1: Docker Compose (Development)

```bash
# Start all services (no SSL)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option 2: Production with SSL/TLS (Recommended)

Seraph AI includes a pre-configured Nginx reverse proxy with SSL support.

#### Quick SSL Setup

```bash
# 1. Generate self-signed certificate (for testing)
./scripts/setup_ssl.sh --self-signed localhost

# OR for production with Let's Encrypt:
./scripts/setup_ssl.sh --letsencrypt seraph.yourdomain.com admin@yourdomain.com

# 2. Start with SSL enabled
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### Manual SSL Setup

1. **Generate certificates:**

```bash
# For testing (self-signed)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/privkey.pem \
    -out nginx/ssl/fullchain.pem \
    -subj "/CN=yourdomain.com"

# For production (Let's Encrypt)
sudo certbot certonly --standalone -d yourdomain.com
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
```

2. **Update environment:**

```bash
# In .env file
REACT_APP_BACKEND_URL=https://yourdomain.com
```

3. **Deploy with SSL:**

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### SSL Configuration Files

| File | Purpose |
|------|---------|
| `nginx/nginx.conf` | Main Nginx configuration |
| `nginx/conf.d/default.conf` | Server blocks with SSL settings |
| `nginx/ssl/fullchain.pem` | SSL certificate chain |
| `nginx/ssl/privkey.pem` | SSL private key |

#### SSL Features Included

- **TLS 1.2/1.3** with modern cipher suites
- **HTTP to HTTPS** automatic redirect
- **Rate limiting** on API and login endpoints
- **WebSocket support** for agent communication
- **Security headers** (XSS, CSRF, Content-Security-Policy)
- **OCSP Stapling** for certificate validation
- **Gzip compression** for performance

#### Certificate Auto-Renewal (Let's Encrypt)

```bash
# Set up automatic renewal
./scripts/setup_ssl.sh --letsencrypt yourdomain.com your@email.com

# Manual renewal
sudo certbot renew
cp /etc/letsencrypt/live/yourdomain.com/*.pem nginx/ssl/
docker-compose exec nginx nginx -s reload
```

### Option 3: Custom Nginx Configuration

If you have an existing Nginx installation:

```nginx
# /etc/nginx/sites-available/seraph-ai
server {
    listen 80;
    server_name seraph.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seraph.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/seraph.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seraph.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_read_timeout 300;
    }

    location /api/agent-commands/ws {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

2. Enable and get SSL certificate:

```bash
sudo ln -s /etc/nginx/sites-available/seraph-ai /etc/nginx/sites-enabled/
sudo certbot --nginx -d seraph.yourdomain.com
sudo systemctl reload nginx
```

---

## VPN Setup

### Server Configuration

The WireGuard VPN is automatically configured when you start the stack. Client configs are generated based on `VPN_PEERS` setting.

```bash
# View generated client configs
docker exec seraph-wireguard ls /config

# Get a specific peer config
docker exec seraph-wireguard cat /config/peer1/peer1.conf
```

### Client Setup

1. **Download client config** from Seraph AI UI → VPN → Download Config
2. **Install WireGuard** on client:
   - Windows/Mac: Download from https://wireguard.com/install
   - Linux: `sudo apt install wireguard`
3. **Import config** and connect

### VPN Network

- **Subnet**: 10.200.200.0/24
- **Server**: 10.200.200.1
- **Clients**: 10.200.200.2-254
- **DNS**: 1.1.1.1, 8.8.8.8

---

## Agent Deployment

### Download Agent

1. Go to Seraph AI UI → Agent Center → Download Agent
2. Select agent type:
   - **Basic**: Lightweight monitoring
   - **Advanced**: Full security suite with CLI monitoring

### Deploy on Endpoints

```bash
# Linux/macOS
chmod +x advanced_agent.py
python3 advanced_agent.py --api-url https://your-server:8001 --monitor

# Windows (PowerShell)
python advanced_agent.py --api-url https://your-server:8001 --monitor
```

### Agent Features
- Process monitoring
- CLI command tracking (AI-Agentic detection)
- USB device monitoring
- Credential theft detection
- WebSocket real-time communication

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check all services
docker-compose ps

# Check backend health
curl http://localhost:8001/api/health

# Check MongoDB
docker exec seraph-mongodb mongosh --eval "db.adminCommand('ping')"

# View CCE Worker status
docker logs seraph-backend | grep "CCE Worker"
```

### Logs

```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f wireguard

# Backend errors only
docker-compose logs backend 2>&1 | grep -i error
```

### Backup

```bash
# Backup MongoDB
docker exec seraph-mongodb mongodump --out /backup
docker cp seraph-mongodb:/backup ./mongodb-backup-$(date +%Y%m%d)

# Backup VPN configs
docker cp seraph-wireguard:/config ./wireguard-backup-$(date +%Y%m%d)
```

### Updates

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Clean up old images
docker image prune -f
```

---

## Droplet Reinstall

Use this when you need to wipe and rebuild Seraph on an existing droplet (DigitalOcean, Linode, Vultr, etc.) from a clean state without reprovisioning the VM itself.

### Full Reinstall Command

Run the following as root on the droplet:

```bash
curl -fsSL https://raw.githubusercontent.com/Byron2306/Metatron/main/scripts/seraph_builder.sh | sudo bash -s -- --reinstall
```

Or, if you have already cloned the repository on the droplet:

```bash
sudo bash scripts/seraph_builder.sh --reinstall
```

### What `--reinstall` Does

1. Stops and disables the `seraph-backend`, `seraph-frontend`, and `seraph-agent` systemd services
2. Removes all Seraph Docker containers (`seraph-mongodb`, `seraph-redis`, `seraph-elasticsearch`, `seraph-kibana`, `seraph-cuckoo`)
3. Deletes named Docker volumes (`seraph-mongodb-data`, `seraph-elasticsearch-data`)
4. Removes the `seraph-network` Docker network
5. Wipes the application directory (`/opt/seraph-ai` by default)
6. Runs a complete fresh full installation identical to `--full`

> **Warning:** All existing data (database records, VPN configs, logs) will be permanently deleted. Take a backup before running this command if you need to preserve data.

### Backup Before Reinstall (Recommended)

```bash
# Backup MongoDB data
docker exec seraph-mongodb mongodump --out /backup
docker cp seraph-mongodb:/backup ./mongodb-backup-$(date +%Y%m%d)

# Backup WireGuard VPN configs
docker cp seraph-wireguard:/config ./wireguard-backup-$(date +%Y%m%d)
```

---

## Troubleshooting

### Common Issues

#### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common fixes:
# 1. MongoDB not ready - wait and retry
docker-compose restart backend

# 2. Port conflict
sudo lsof -i :8001
```

#### VPN not connecting
```bash
# Check WireGuard status
docker exec seraph-wireguard wg show

# Verify kernel module
lsmod | grep wireguard

# Check firewall
sudo ufw allow 51820/udp
```

#### Database connection issues
```bash
# Check MongoDB status
docker-compose logs mongodb

# Restart MongoDB
docker-compose restart mongodb

# If persistent, clear volumes
docker-compose down -v
docker-compose up -d
```

#### CCE Worker not running
```bash
# Check backend logs for CCE Worker
docker-compose logs backend | grep -i "cce"

# Should see: "CCE Worker started successfully"
```

### Getting Help

- **Documentation**: Check `/app/memory/PRD.md` for full feature documentation
- **Logs**: Always check `docker-compose logs` first
- **Issues**: https://github.com/your-org/seraph-ai-defense/issues

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SERAPH AI                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Frontend │◄──►│ Backend  │◄──►│ MongoDB  │    │WireGuard │  │
│  │  :3000   │    │  :8001   │    │  :27017  │    │  :51820  │  │
│  │  (React) │    │ (FastAPI)│    │          │    │  (VPN)   │  │
│  └──────────┘    └────┬─────┘    └──────────┘    └──────────┘  │
│                       │                                         │
│                 ┌─────┴─────┐                                   │
│                 │CCE Worker │  Real-time CLI Analysis           │
│                 │  (Async)  │  AI-Agentic Detection             │
│                 └───────────┘                                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                     ENDPOINT AGENTS                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Agent 1 │  │ Agent 2 │  │ Agent 3 │  │ Agent N │            │
│  │(Windows)│  │ (Linux) │  │ (macOS) │  │   ...   │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       │            │            │            │                  │
│       └────────────┴────────────┴────────────┘                  │
│                     WebSocket / HTTPS                           │
└─────────────────────────────────────────────────────────────────┘
```

---

**Seraph AI Defense System v5.0.0** | Built for the AI-Agentic Era
