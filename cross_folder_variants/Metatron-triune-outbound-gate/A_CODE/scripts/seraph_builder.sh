#!/bin/bash
#===============================================================================
# SERAPH AI DEFENSE SYSTEM - COMPLETE INFRASTRUCTURE BUILDER
#===============================================================================
# This script sets up the complete Seraph AI infrastructure including:
# - Docker containers for all services
# - Cuckoo Sandbox malware analysis
# - liboqs quantum-resistant cryptography
# - WireGuard VPN
# - Elasticsearch & Kibana SIEM
# - MongoDB database
# - All Python and Node.js dependencies
#
# Requirements:
# - Ubuntu 20.04+ or Debian 11+
# - Minimum 16GB RAM, 100GB disk space
# - Root access
# - Internet connection
#
# Usage: sudo ./seraph_builder.sh [--full|--minimal|--dev|--reinstall]
#
#   --full       Full installation of all components (default)
#   --minimal    Install core services only (no SIEM, no sandbox)
#   --dev        Install core + Redis for local development
#   --reinstall  Wipe existing Seraph installation and reinstall from scratch.
#                Full one-liner for a droplet:
#                  curl -fsSL https://raw.githubusercontent.com/Byron2306/Metatron/main/scripts/seraph_builder.sh | sudo bash -s -- --reinstall
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SERAPH_HOME="${SERAPH_HOME:-/opt/seraph-ai}"
SERAPH_USER="${SERAPH_USER:-seraph}"
SERAPH_VERSION="6.3.0"
DOCKER_NETWORK="seraph-network"
INSTALL_MODE="${1:-full}"

# Logging
LOG_FILE="/var/log/seraph-builder.log"
exec 1> >(tee -a "$LOG_FILE") 2>&1

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }

banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════╗
║   ███████╗███████╗██████╗  █████╗ ██████╗ ██╗  ██╗     █████╗ ██╗        ║
║   ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║  ██║    ██╔══██╗██║        ║
║   ███████╗█████╗  ██████╔╝███████║██████╔╝███████║    ███████║██║        ║
║   ╚════██║██╔══╝  ██╔══██╗██╔══██║██╔═══╝ ██╔══██║    ██╔══██║██║        ║
║   ███████║███████╗██║  ██║██║  ██║██║     ██║  ██║    ██║  ██║██║        ║
║   ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝        ║
║                                                                           ║
║           INFRASTRUCTURE BUILDER v6.3.0                                   ║
║           Ultimate Agentic Anti-AI Agent Defense System                   ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

check_system() {
    log "Checking system requirements..."
    
    # Check OS
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        if [[ "$ID" != "ubuntu" && "$ID" != "debian" && "$ID" != "kali" ]]; then
            warn "Unsupported OS: $ID. Proceeding anyway..."
        fi
    fi
    
    # Check RAM
    TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
    if [[ $TOTAL_RAM -lt 8 ]]; then
        warn "Less than 8GB RAM detected. Performance may be affected."
    fi
    
    # Check disk space
    FREE_DISK=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
    if [[ $FREE_DISK -lt 50 ]]; then
        warn "Less than 50GB free disk space. Consider expanding."
    fi
    
    # Check virtualization
    if grep -q -E '(vmx|svm)' /proc/cpuinfo; then
        info "Hardware virtualization supported"
    else
        warn "Hardware virtualization not detected. VMs may not work."
    fi
}

install_base_packages() {
    log "Installing base packages..."
    
    apt-get update
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common \
        wget \
        git \
        unzip \
        jq \
        htop \
        iotop \
        net-tools \
        iputils-ping \
        dnsutils \
        tcpdump \
        nmap \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        cmake \
        ninja-build \
        libssl-dev \
        libffi-dev \
        pkg-config \
        imagemagick \
        ffmpeg
    
    log "Base packages installed"
}

install_docker() {
    log "Installing Docker..."
    
    if command -v docker &> /dev/null; then
        info "Docker already installed"
        return
    fi
    
    # Add Docker GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    # Create Docker network
    docker network create $DOCKER_NETWORK 2>/dev/null || true
    
    log "Docker installed and configured"
}

install_nodejs() {
    log "Installing Node.js..."
    
    if command -v node &> /dev/null; then
        info "Node.js already installed: $(node --version)"
        return
    fi
    
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    
    # Install yarn
    npm install -g yarn
    
    log "Node.js $(node --version) installed"
}

install_mongodb() {
    log "Setting up MongoDB..."
    
    # Run MongoDB in Docker
    docker run -d \
        --name seraph-mongodb \
        --network $DOCKER_NETWORK \
        --restart unless-stopped \
        -p 27017:27017 \
        -v seraph-mongodb-data:/data/db \
        -e MONGO_INITDB_DATABASE=seraph_ai \
        mongo:6.0
    
    # Wait for MongoDB to start
    sleep 10
    
    log "MongoDB container started"
}

install_elasticsearch() {
    log "Setting up Elasticsearch & Kibana..."
    
    # Create Elasticsearch container
    docker run -d \
        --name seraph-elasticsearch \
        --network $DOCKER_NETWORK \
        --restart unless-stopped \
        -p 9200:9200 \
        -p 9300:9300 \
        -e "discovery.type=single-node" \
        -e "xpack.security.enabled=false" \
        -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
        -v seraph-es-data:/usr/share/elasticsearch/data \
        elasticsearch:8.11.0
    
    sleep 15
    
    # Create Kibana container
    docker run -d \
        --name seraph-kibana \
        --network $DOCKER_NETWORK \
        --restart unless-stopped \
        -p 5601:5601 \
        -e "ELASTICSEARCH_HOSTS=http://seraph-elasticsearch:9200" \
        kibana:8.11.0
    
    log "Elasticsearch & Kibana containers started"
}

install_wireguard() {
    log "Installing WireGuard VPN..."
    
    apt-get install -y wireguard wireguard-tools
    
    # Generate server keys if not exist
    WG_DIR="/etc/wireguard"
    mkdir -p $WG_DIR
    
    if [[ ! -f "$WG_DIR/server_private.key" ]]; then
        wg genkey | tee "$WG_DIR/server_private.key" | wg pubkey > "$WG_DIR/server_public.key"
        chmod 600 "$WG_DIR/server_private.key"
    fi
    
    SERVER_PRIVATE=$(cat "$WG_DIR/server_private.key")
    SERVER_PUBLIC=$(cat "$WG_DIR/server_public.key")
    
    # Create WireGuard config
    cat > "$WG_DIR/wg0.conf" << EOF
[Interface]
PrivateKey = $SERVER_PRIVATE
Address = 10.200.200.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
SaveConfig = false

# Clients will be added dynamically via API
EOF
    
    chmod 600 "$WG_DIR/wg0.conf"
    
    # Enable IP forwarding
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    sysctl -p
    
    # Start WireGuard
    systemctl enable wg-quick@wg0
    systemctl start wg-quick@wg0 || true
    
    log "WireGuard VPN installed. Server public key: $SERVER_PUBLIC"
}

install_cuckoo() {
    log "Setting up Cuckoo Sandbox..."
    
    # Create Cuckoo directory
    CUCKOO_DIR="$SERAPH_HOME/cuckoo"
    mkdir -p "$CUCKOO_DIR"
    
    # Create docker-compose for Cuckoo
    cat > "$CUCKOO_DIR/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  cuckoo:
    image: blacktop/cuckoo:2.0.7
    container_name: seraph-cuckoo
    privileged: true
    ports:
      - "8090:8090"
      - "2042:2042"
    volumes:
      - ./cuckoo-data:/cuckoo
      - /tmp:/tmp
    environment:
      - CUCKOO_API_HOST=0.0.0.0
    networks:
      - seraph-network
    restart: unless-stopped

  cuckoo-web:
    image: blacktop/cuckoo:2.0.7
    container_name: seraph-cuckoo-web
    command: web
    ports:
      - "8080:8080"
    environment:
      - CUCKOO_API=http://cuckoo:8090
    depends_on:
      - cuckoo
    networks:
      - seraph-network
    restart: unless-stopped

networks:
  seraph-network:
    external: true
EOF
    
    cd "$CUCKOO_DIR"
    docker compose up -d || warn "Cuckoo containers may need manual VM configuration"
    
    log "Cuckoo Sandbox containers created"
}

install_liboqs() {
    log "Installing liboqs (Post-Quantum Cryptography)..."
    
    LIBOQS_DIR="$SERAPH_HOME/liboqs"
    mkdir -p "$LIBOQS_DIR"
    cd "$LIBOQS_DIR"
    
    # Clone liboqs
    if [[ ! -d "liboqs" ]]; then
        git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git
    fi
    
    cd liboqs
    mkdir -p build && cd build
    
    # Build liboqs
    cmake -GNinja -DBUILD_SHARED_LIBS=ON ..
    ninja
    ninja install
    
    # Update library cache
    ldconfig
    
    # Install Python bindings
    pip3 install liboqs-python
    
    # Verify installation
    python3 -c "import oqs; print(f'liboqs version: {oqs.oqs_version()}')" && \
        log "liboqs installed successfully" || \
        warn "liboqs Python bindings installation failed"
}

install_kali_tools() {
    log "Installing Kali Linux security tools..."
    
    # Add Kali repository (for Debian-based systems)
    if [[ ! -f /etc/apt/sources.list.d/kali.list ]]; then
        echo "deb http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware" | tee /etc/apt/sources.list.d/kali.list
        wget -q -O - https://archive.kali.org/archive-key.asc | apt-key add - 2>/dev/null || true
    fi
    
    apt-get update 2>/dev/null || true
    
    # Install essential security tools
    apt-get install -y \
        nmap \
        masscan \
        nikto \
        sqlmap \
        hydra \
        john \
        hashcat \
        aircrack-ng \
        wireshark-common \
        tshark \
        netcat-openbsd \
        socat \
        proxychains4 \
        tor \
        gobuster \
        dirb \
        wfuzz \
        ffuf \
        nuclei \
        amass \
        subfinder \
        httpx-toolkit \
        dnsx \
        cewl \
        crunch \
        wordlists \
        seclists \
        exploitdb \
        metasploit-framework \
        volatility3 \
        autopsy \
        binwalk \
        foremost \
        scalpel \
        yara \
        clamav \
        rkhunter \
        chkrootkit \
        lynis \
        openvas \
        2>/dev/null || warn "Some Kali tools may not be available"
    
    log "Security tools installed"
}

install_python_deps() {
    log "Installing Python dependencies..."
    
    # Create virtual environment
    VENV_DIR="$SERAPH_HOME/venv"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    pip install --upgrade pip wheel setuptools
    
    # Core dependencies
    pip install \
        fastapi \
        uvicorn[standard] \
        motor \
        pymongo \
        pydantic \
        python-jose[cryptography] \
        passlib[bcrypt] \
        python-multipart \
        aiofiles \
        httpx \
        websockets \
        redis \
        celery \
        elasticsearch \
        requests \
        beautifulsoup4 \
        lxml \
        paramiko \
        fabric \
        python-nmap \
        scapy \
        psutil \
        netifaces \
        pyOpenSSL \
        cryptography \
        pycryptodome \
        reportlab \
        Pillow \
        matplotlib \
        pandas \
        numpy \
        scikit-learn \
        tensorflow \
        torch \
        transformers \
        sentence-transformers \
        langchain \
        openai \
        anthropic \
        ollama \
        yara-python \
        pefile \
        python-magic \
        virustotal-api \
        shodan \
        censys \
        greynoise \
        OTXv2 \
        pymisp \
        stix2 \
        taxii2-client
    
    # Install emergent integrations
    pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || true
    
    # Install liboqs-python if not already
    pip install liboqs-python || true
    
    log "Python dependencies installed"
}

setup_seraph_app() {
    log "Setting up Seraph AI application..."
    
    # Create directory structure
    mkdir -p "$SERAPH_HOME"/{backend,frontend,agents,scripts,data,logs,quarantine}
    
    # Copy application files (assuming they exist in /app)
    if [[ -d /app/backend ]]; then
        cp -r /app/backend/* "$SERAPH_HOME/backend/"
    fi
    
    if [[ -d /app/frontend ]]; then
        cp -r /app/frontend/* "$SERAPH_HOME/frontend/"
    fi
    
    if [[ -d /app/unified_agent ]]; then
        cp -r /app/unified_agent/* "$SERAPH_HOME/agents/"
    fi
    
    if [[ -d /app/scripts ]]; then
        cp -r /app/scripts/* "$SERAPH_HOME/scripts/"
    fi
    
    # Create environment files
    SERAPH_HOST="${SERAPH_HOST:-165.22.41.184}"
    cat > "$SERAPH_HOME/backend/.env" << EOF
# Seraph AI Backend Configuration
MONGO_URL=mongodb://localhost:27017
DB_NAME=seraph_ai
ELASTICSEARCH_URL=http://localhost:9200
REDIS_URL=redis://localhost:6379
SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
CUCKOO_API_URL=http://localhost:8090
WIREGUARD_CONFIG_PATH=/etc/wireguard
OLLAMA_URL=http://localhost:11434
CORS_ORIGINS=http://${SERAPH_HOST},http://${SERAPH_HOST}:3000,http://localhost:3000
API_URL=http://${SERAPH_HOST}:8001
VPN_SERVER_ENDPOINT=${SERAPH_HOST}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@yourdomain.com}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-CHANGE_ME}
ADMIN_NAME=${ADMIN_NAME:-Seraph Admin}
EOF
    
    cat > "$SERAPH_HOME/frontend/.env" << EOF
REACT_APP_BACKEND_URL=http://${SERAPH_HOST}:8001
EOF
    
    # Install frontend dependencies
    cd "$SERAPH_HOME/frontend"
    yarn install || npm install
    
    log "Seraph AI application configured"
}

create_systemd_services() {
    log "Creating systemd services..."
    
    # Backend service
    cat > /etc/systemd/system/seraph-backend.service << EOF
[Unit]
Description=Seraph AI Backend
After=network.target mongodb.service

[Service]
Type=simple
User=$SERAPH_USER
WorkingDirectory=$SERAPH_HOME/backend
Environment="PATH=$SERAPH_HOME/venv/bin"
ExecStart=$SERAPH_HOME/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    # Frontend service
    cat > /etc/systemd/system/seraph-frontend.service << EOF
[Unit]
Description=Seraph AI Frontend
After=network.target seraph-backend.service

[Service]
Type=simple
User=$SERAPH_USER
WorkingDirectory=$SERAPH_HOME/frontend
ExecStart=/usr/bin/yarn start
Restart=always
RestartSec=5
Environment="PORT=3000"

[Install]
WantedBy=multi-user.target
EOF
    
    # Agent service
    cat > /etc/systemd/system/seraph-agent.service << EOF
[Unit]
Description=Seraph AI Unified Agent
After=network.target seraph-backend.service

[Service]
Type=simple
User=root
WorkingDirectory=$SERAPH_HOME/agents
Environment="PATH=$SERAPH_HOME/venv/bin"
Environment="PYTHONPATH=$SERAPH_HOME/agents"
ExecStart=$SERAPH_HOME/venv/bin/python -m core.agent --server http://${SERAPH_HOST:-165.22.41.184}:8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Create standalone agent installer script
    cat > "$SERAPH_HOME/install-agent.sh" << 'AGENT_INSTALLER'
#!/bin/bash
# Seraph AI Unified Agent Installer
# Usage: curl -sSL http://YOUR_SERVER:8001/api/unified/agent/install-script | sudo bash

SERAPH_SERVER="${1:-http://165.22.41.184:8001}"
INSTALL_DIR="/opt/seraph-agent"

echo "Installing Seraph AI Unified Agent..."
echo "Server: $SERAPH_SERVER"

# Create installation directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Install Python dependencies
apt-get update && apt-get install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install psutil requests netifaces scapy watchdog python-nmap aiohttp pyyaml

# Download agent files from server
curl -sSL "$SERAPH_SERVER/api/unified/agent/download" -o agent.tar.gz
tar -xzf agent.tar.gz

# Create systemd service
cat > /etc/systemd/system/seraph-agent.service << EOF
[Unit]
Description=Seraph AI Unified Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python core/agent.py --server $SERAPH_SERVER
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable seraph-agent
systemctl start seraph-agent

echo "Seraph AI Agent installed and running!"
echo "Check status: systemctl status seraph-agent"
AGENT_INSTALLER
    chmod +x "$SERAPH_HOME/install-agent.sh"
    
    # Reload systemd
    systemctl daemon-reload
    
    log "Systemd services created"
}

create_user() {
    log "Creating Seraph user..."
    
    if id "$SERAPH_USER" &>/dev/null; then
        info "User $SERAPH_USER already exists"
    else
        useradd -r -s /bin/bash -d "$SERAPH_HOME" -m "$SERAPH_USER"
    fi
    
    # Set ownership
    chown -R "$SERAPH_USER:$SERAPH_USER" "$SERAPH_HOME"
    
    # Add to docker group
    usermod -aG docker "$SERAPH_USER" || true
    
    log "User $SERAPH_USER configured"
}

setup_slack_notifications() {
    log "Configuring Slack notifications..."
    
    # Create Slack notification helper script
    cat > "$SERAPH_HOME/scripts/slack_notify.sh" << 'SLACK_EOF'
#!/bin/bash
# Seraph AI Slack Notification Helper
WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
MESSAGE="${1:-Test notification from Seraph AI}"
SEVERITY="${2:-info}"

if [[ -z "$WEBHOOK_URL" ]]; then
    echo "Error: SLACK_WEBHOOK_URL not set"
    exit 1
fi

COLOR="#36a64f"  # Green for info
case "$SEVERITY" in
    critical) COLOR="#ff0000" ;;
    high) COLOR="#ff6600" ;;
    medium) COLOR="#ffcc00" ;;
    low) COLOR="#36a64f" ;;
esac

curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "{
        \"attachments\": [{
            \"color\": \"$COLOR\",
            \"title\": \"Seraph AI Alert\",
            \"text\": \"$MESSAGE\",
            \"footer\": \"Seraph AI Defense System\",
            \"ts\": $(date +%s)
        }]
    }"
SLACK_EOF
    chmod +x "$SERAPH_HOME/scripts/slack_notify.sh"
    
    log "Slack notification helper created at $SERAPH_HOME/scripts/slack_notify.sh"
}

setup_email_notifications() {
    log "Configuring email notifications..."
    
    # Install mailutils for email sending
    apt-get install -y mailutils postfix 2>/dev/null || true
    
    # Create email notification helper script
    cat > "$SERAPH_HOME/scripts/email_notify.sh" << 'EMAIL_EOF'
#!/bin/bash
# Seraph AI Email Notification Helper
SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASS="${SMTP_PASS:-}"
FROM_ADDR="${FROM_ADDR:-seraph@localhost}"
TO_ADDR="${1:-}"
SUBJECT="${2:-Seraph AI Alert}"
MESSAGE="${3:-Alert from Seraph AI Defense System}"

if [[ -z "$TO_ADDR" ]]; then
    echo "Error: No recipient address provided"
    exit 1
fi

# Use sendmail if available
if command -v sendmail &> /dev/null; then
    echo -e "Subject: $SUBJECT\nFrom: $FROM_ADDR\nTo: $TO_ADDR\n\n$MESSAGE" | sendmail -t
elif command -v mail &> /dev/null; then
    echo "$MESSAGE" | mail -s "$SUBJECT" "$TO_ADDR"
else
    echo "Error: No mail command available"
    exit 1
fi
EMAIL_EOF
    chmod +x "$SERAPH_HOME/scripts/email_notify.sh"
    
    log "Email notification helper created at $SERAPH_HOME/scripts/email_notify.sh"
}

verify_installation() {
    log "Verifying installation..."
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  INSTALLATION VERIFICATION${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Check Docker
    echo -n "  Docker: "
    if command -v docker &> /dev/null && docker ps &> /dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not running${NC}"
    fi
    
    # Check MongoDB
    echo -n "  MongoDB: "
    if docker ps | grep -q seraph-mongodb; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${YELLOW}○ Not started${NC}"
    fi
    
    # Check Elasticsearch
    echo -n "  Elasticsearch: "
    if docker ps | grep -q seraph-elasticsearch; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${YELLOW}○ Not started${NC}"
    fi
    
    # Check Kibana
    echo -n "  Kibana: "
    if docker ps | grep -q seraph-kibana; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${YELLOW}○ Not started${NC}"
    fi
    
    # Check Redis
    echo -n "  Redis: "
    if docker ps | grep -q seraph-redis; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${YELLOW}○ Not started${NC}"
    fi
    
    # Check WireGuard
    echo -n "  WireGuard: "
    if command -v wg &> /dev/null; then
        if systemctl is-active --quiet wg-quick@wg0; then
            echo -e "${GREEN}✓ Running${NC}"
        else
            echo -e "${YELLOW}○ Installed, not active${NC}"
        fi
    else
        echo -e "${RED}✗ Not installed${NC}"
    fi
    
    # Check Cuckoo
    echo -n "  Cuckoo Sandbox: "
    if docker ps | grep -q seraph-cuckoo; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${YELLOW}○ Container created${NC}"
    fi
    
    # Check liboqs
    echo -n "  liboqs (Quantum): "
    if python3 -c "import oqs" 2>/dev/null; then
        echo -e "${GREEN}✓ Installed${NC}"
    else
        echo -e "${YELLOW}○ Not installed${NC}"
    fi
    
    # Check Ollama
    echo -n "  Ollama (Local AI): "
    if command -v ollama &> /dev/null; then
        if systemctl is-active --quiet ollama; then
            echo -e "${GREEN}✓ Running${NC}"
        else
            echo -e "${YELLOW}○ Installed, not active${NC}"
        fi
    else
        echo -e "${RED}✗ Not installed${NC}"
    fi
    
    echo ""
}

install_ollama() {
    log "Installing Ollama for local AI..."
    
    curl -fsSL https://ollama.ai/install.sh | sh
    
    # Start Ollama
    systemctl enable ollama
    systemctl start ollama
    
    # Pull default model
    ollama pull llama2 &
    
    log "Ollama installed"
}

install_redis() {
    log "Installing Redis..."
    
    docker run -d \
        --name seraph-redis \
        --network $DOCKER_NETWORK \
        --restart unless-stopped \
        -p 6379:6379 \
        redis:7-alpine
    
    log "Redis container started"
}

setup_firewall() {
    log "Configuring firewall..."
    
    apt-get install -y ufw
    
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH
    ufw allow 22/tcp
    
    # Allow Seraph services
    ufw allow 3000/tcp  # Frontend
    ufw allow 8001/tcp  # Backend API
    ufw allow 5601/tcp  # Kibana
    ufw allow 9200/tcp  # Elasticsearch
    ufw allow 51820/udp # WireGuard
    
    ufw --force enable
    
    log "Firewall configured"
}

print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  SERAPH AI INSTALLATION COMPLETE${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}Services:${NC}"
    echo "  - Backend API:     http://${SERAPH_HOST:-165.22.41.184}:8001"
    echo "  - Frontend:        http://${SERAPH_HOST:-165.22.41.184}:3000"
    echo "  - Elasticsearch:   http://localhost:9200"
    echo "  - Kibana:          http://localhost:5601"
    echo "  - Cuckoo Sandbox:  http://localhost:8080"
    echo "  - WireGuard VPN:   Port 51820/UDP"
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo "  Start all:    systemctl start seraph-backend seraph-frontend seraph-agent"
    echo "  Stop all:     systemctl stop seraph-backend seraph-frontend seraph-agent"
    echo "  View logs:    journalctl -u seraph-backend -f"
    echo ""
    echo -e "${CYAN}Installation Directory:${NC} $SERAPH_HOME"
    echo -e "${CYAN}Log File:${NC} $LOG_FILE"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Configure Cuckoo VM images for malware analysis"
    echo "  2. Add WireGuard clients via the dashboard"
    echo "  3. Configure SIEM integrations in the UI"
    echo ""
    echo -e "${CYAN}Reinstall Command (wipe and rebuild this droplet):${NC}"
    echo "  curl -fsSL https://raw.githubusercontent.com/Byron2306/Metatron/main/scripts/seraph_builder.sh | sudo bash -s -- --reinstall"
    echo "  # or, if the repo is already cloned on this machine:"
    echo "  sudo bash $0 --reinstall"
    echo ""
}

#===============================================================================
# REINSTALL (DROPLET)
#===============================================================================

reinstall_droplet() {
    log "Preparing droplet for reinstall..."

    # Stop and disable Seraph systemd services if present
    for svc in seraph-backend seraph-frontend seraph-agent; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            log "Stopping $svc..."
            systemctl stop "$svc" || true
        fi
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            systemctl disable "$svc" || true
        fi
    done

    # Remove Seraph Docker containers and volumes
    for container in seraph-mongodb seraph-redis seraph-elasticsearch seraph-kibana seraph-cuckoo; do
        if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
            log "Removing container: $container"
            docker rm -f "$container" || true
        fi
    done

    # Remove named Docker volumes used by Seraph
    for volume in seraph-mongodb-data seraph-elasticsearch-data; do
        if docker volume ls -q 2>/dev/null | grep -q "^${volume}$"; then
            log "Removing volume: $volume"
            docker volume rm "$volume" || true
        fi
    done

    # Remove Docker network
    if docker network ls --format '{{.Name}}' 2>/dev/null | grep -q "^${DOCKER_NETWORK}$"; then
        log "Removing Docker network: $DOCKER_NETWORK"
        docker network rm "$DOCKER_NETWORK" || true
    fi

    # Remove application directory
    if [[ -d "$SERAPH_HOME" ]]; then
        log "Removing $SERAPH_HOME..."
        rm -rf "$SERAPH_HOME"
    fi

    log "Droplet cleanup complete. Starting fresh full installation..."
}

#===============================================================================
# MAIN EXECUTION
#===============================================================================

main() {
    banner
    check_root
    check_system
    
    case "$INSTALL_MODE" in
        --minimal)
            log "Starting MINIMAL installation..."
            install_base_packages
            install_docker
            install_nodejs
            install_mongodb
            install_python_deps
            setup_seraph_app
            ;;
        --dev)
            log "Starting DEVELOPMENT installation..."
            install_base_packages
            install_docker
            install_nodejs
            install_mongodb
            install_redis
            install_python_deps
            setup_seraph_app
            ;;
        --reinstall)
            log "Starting REINSTALL on existing droplet..."
            reinstall_droplet
            install_base_packages
            install_docker
            install_nodejs
            install_mongodb
            install_redis
            install_elasticsearch
            install_wireguard
            install_cuckoo
            install_liboqs
            install_kali_tools
            install_ollama
            install_python_deps
            setup_seraph_app
            create_user
            create_systemd_services
            setup_slack_notifications
            setup_email_notifications
            setup_firewall
            verify_installation
            ;;
        --full|*)
            log "Starting FULL installation..."
            install_base_packages
            install_docker
            install_nodejs
            install_mongodb
            install_redis
            install_elasticsearch
            install_wireguard
            install_cuckoo
            install_liboqs
            install_kali_tools
            install_ollama
            install_python_deps
            setup_seraph_app
            create_user
            create_systemd_services
            setup_slack_notifications
            setup_email_notifications
            setup_firewall
            verify_installation
            ;;
    esac
    
    print_summary
    
    log "Installation completed successfully!"
}

# Run main function
main "$@"
