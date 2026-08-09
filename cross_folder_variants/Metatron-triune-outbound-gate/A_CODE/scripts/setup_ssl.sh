#!/bin/bash
# Seraph AI - SSL Certificate Setup Script
# =========================================
# Generates self-signed certs for testing or sets up Let's Encrypt for production

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="${SCRIPT_DIR}/../nginx/ssl"
DOMAIN="${1:-localhost}"
EMAIL="${2:-admin@example.com}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "=================================================="
echo "  Seraph AI - SSL Certificate Setup"
echo "=================================================="
echo -e "${NC}"

mkdir -p "$SSL_DIR"

# Function to generate self-signed certificate
generate_self_signed() {
    echo -e "${YELLOW}Generating self-signed certificate for testing...${NC}"
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${SSL_DIR}/privkey.pem" \
        -out "${SSL_DIR}/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=Seraph AI/CN=${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},IP:127.0.0.1"
    
    echo -e "${GREEN}✓ Self-signed certificate generated${NC}"
    echo "  - Certificate: ${SSL_DIR}/fullchain.pem"
    echo "  - Private Key: ${SSL_DIR}/privkey.pem"
    echo ""
    echo -e "${YELLOW}⚠ Warning: Self-signed certs will show browser warnings.${NC}"
    echo "  For production, use Let's Encrypt with: $0 --letsencrypt ${DOMAIN} ${EMAIL}"
}

# Function to set up Let's Encrypt with certbot
setup_letsencrypt() {
    echo -e "${YELLOW}Setting up Let's Encrypt certificate...${NC}"
    
    if ! command -v certbot &> /dev/null; then
        echo -e "${RED}Certbot not found. Installing...${NC}"
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y certbot
        elif command -v yum &> /dev/null; then
            sudo yum install -y certbot
        else
            echo -e "${RED}Please install certbot manually${NC}"
            exit 1
        fi
    fi
    
    # Stop nginx temporarily for standalone mode
    docker-compose stop nginx 2>/dev/null || true
    
    # Get certificate
    sudo certbot certonly --standalone \
        -d "${DOMAIN}" \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email \
        --non-interactive
    
    # Copy certificates
    sudo cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${SSL_DIR}/"
    sudo cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${SSL_DIR}/"
    sudo chmod 644 "${SSL_DIR}/fullchain.pem"
    sudo chmod 600 "${SSL_DIR}/privkey.pem"
    
    echo -e "${GREEN}✓ Let's Encrypt certificate installed${NC}"
    echo ""
    echo "Certificate will auto-renew. To manually renew:"
    echo "  sudo certbot renew"
    
    # Start nginx
    docker-compose start nginx 2>/dev/null || true
}

# Function to set up certificate renewal cron job
setup_renewal_cron() {
    echo -e "${YELLOW}Setting up automatic certificate renewal...${NC}"
    
    # Create renewal script
    cat > "${SCRIPT_DIR}/renew_certs.sh" << 'EOF'
#!/bin/bash
# Auto-renewal script for Let's Encrypt certificates
certbot renew --quiet
# Copy renewed certs to nginx ssl directory
DOMAIN=$(cat /etc/letsencrypt/renewal/*.conf | grep "^\[" | head -1 | tr -d '[]')
if [ -n "$DOMAIN" ]; then
    cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "/app/nginx/ssl/"
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "/app/nginx/ssl/"
    docker-compose -f /app/docker-compose.yml exec -T nginx nginx -s reload
fi
EOF
    chmod +x "${SCRIPT_DIR}/renew_certs.sh"
    
    # Add cron job (runs twice daily as recommended)
    (crontab -l 2>/dev/null | grep -v "renew_certs.sh"; echo "0 0,12 * * * ${SCRIPT_DIR}/renew_certs.sh") | crontab -
    
    echo -e "${GREEN}✓ Automatic renewal configured${NC}"
}

# Main logic
case "$1" in
    --letsencrypt|-l)
        if [ -z "$2" ]; then
            echo -e "${RED}Usage: $0 --letsencrypt DOMAIN EMAIL${NC}"
            exit 1
        fi
        DOMAIN="$2"
        EMAIL="${3:-admin@${DOMAIN}}"
        setup_letsencrypt
        setup_renewal_cron
        ;;
    --self-signed|-s)
        DOMAIN="${2:-localhost}"
        generate_self_signed
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS] [DOMAIN] [EMAIL]"
        echo ""
        echo "Options:"
        echo "  --self-signed, -s    Generate self-signed certificate (for testing)"
        echo "  --letsencrypt, -l    Set up Let's Encrypt certificate (for production)"
        echo "  --help, -h           Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 --self-signed localhost"
        echo "  $0 --letsencrypt seraph.example.com admin@example.com"
        ;;
    *)
        # Default: generate self-signed
        generate_self_signed
        ;;
esac

echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Start the stack: docker-compose up -d"
echo "  2. Access via HTTPS: https://${DOMAIN}"
echo ""
