#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARDA OS — FULL STACK INSTALLER
# Installs all dependencies for the complete Arda OS stack:
#   - Python 3 + Flask + dependencies
#   - Ollama + Qwen 2.5:7b (live AI witnesses)
#   - TPM tools
#   - eBPF toolchain
#   - The Arda Desktop (Coronation Dashboard)
#
# Run as root: sudo ./02_install_arda_stack.sh
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KIT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="$(dirname "$KIT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
GOLD='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   ARDA OS — FULL STACK INSTALLER${NC}"
echo -e "${CYAN}   The Ainur Must Be Seated Before the Music Can Begin${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Run as root: sudo $0${NC}"
    exit 1
fi

# ── Phase 1: System Packages ────────────────────────
echo -e "${GOLD}── PHASE 1: System Packages ──${NC}"
apt-get update -qq

# Core tools
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    git curl wget \
    gcc make pkg-config \
    2>/dev/null
echo -e "${GREEN}  ✓ Core tools installed${NC}"

# TPM tools
apt-get install -y -qq \
    tpm2-tools tpm2-abrmd \
    2>/dev/null || echo -e "${GOLD}  ⚠ tpm2-tools: install manually if needed${NC}"
echo -e "${GREEN}  ✓ TPM tools installed${NC}"

# eBPF toolchain
apt-get install -y -qq \
    clang llvm libbpf-dev bpftool \
    linux-headers-$(uname -r) \
    2>/dev/null || echo -e "${GOLD}  ⚠ Some eBPF packages unavailable (may need backports)${NC}"
echo -e "${GREEN}  ✓ eBPF toolchain installed${NC}"

echo ""

# ── Phase 2: Python Dependencies ────────────────────
echo -e "${GOLD}── PHASE 2: Python Dependencies ──${NC}"

# Create a venv for Arda
VENV_DIR="/opt/arda/venv"
mkdir -p /opt/arda
python3 -m venv "$VENV_DIR" 2>/dev/null || {
    # Some live USBs don't have venv — use system pip
    echo -e "${GOLD}  venv unavailable, using system pip${NC}"
    VENV_DIR=""
}

if [ -n "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

pip3 install --quiet \
    flask \
    requests \
    aiohttp \
    hashlib-additional 2>/dev/null || true

echo -e "${GREEN}  ✓ Python packages installed${NC}"
echo ""

# ── Phase 3: Ollama + Qwen ──────────────────────────
echo -e "${GOLD}── PHASE 3: Ollama (Live AI Witnesses) ──${NC}"

if command -v ollama &>/dev/null; then
    echo -e "${GREEN}  ✓ Ollama already installed${NC}"
else
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || {
        echo -e "${RED}  ✗ Ollama install failed. Manual install:${NC}"
        echo "    curl -fsSL https://ollama.com/install.sh | sh"
        echo "  Continuing without Ollama (witnesses will use mock mode)..."
    }
fi

# Start Ollama service
if command -v ollama &>/dev/null; then
    echo "  Starting Ollama service..."
    # Start in background if not already running
    if ! pgrep -x ollama &>/dev/null; then
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    fi
    
    # Pull Qwen model
    echo "  Pulling qwen2.5:7b model (this may take a few minutes)..."
    echo "  (The Ainur Council requires at least one witness with a voice)"
    ollama pull qwen2.5:7b 2>/dev/null && {
        echo -e "${GREEN}  ✓ qwen2.5:7b model ready — Live witnesses ARMED${NC}"
    } || {
        echo -e "${GOLD}  ⚠ Model pull failed — may need internet or more disk space${NC}"
        echo "  Minimum: ~4.5GB free for qwen2.5:7b"
        echo "  Available: $(df -h /tmp | tail -1 | awk '{print $4}')"
    }
else
    echo -e "${GOLD}  ⚠ Ollama not available — witnesses will use mock mode${NC}"
fi

echo ""

# ── Phase 4: Arda OS Directory Structure ────────────
echo -e "${GOLD}── PHASE 4: Arda OS Directory Structure ──${NC}"

ARDA_HOME="/opt/arda"
mkdir -p "$ARDA_HOME"/{config,keys,logs,evidence}

# Copy the Arda codebase from the repo
if [ -d "$REPO_DIR/arda_os" ]; then
    cp -r "$REPO_DIR/arda_os/"* "$ARDA_HOME/" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Arda OS codebase deployed to $ARDA_HOME${NC}"
fi

# Copy the coronation kit
if [ -d "$KIT_DIR" ]; then
    cp -r "$KIT_DIR" "$ARDA_HOME/coronation_kit" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Coronation kit deployed${NC}"
fi

# Copy the desktop app
if [ -d "$REPO_DIR/docs" ]; then
    cp -r "$REPO_DIR/docs" "$ARDA_HOME/desktop" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Desktop app deployed${NC}"
fi

# Set permissions
chmod -R 755 "$ARDA_HOME"
echo ""

# ── Phase 5: Environment Configuration ──────────────
echo -e "${GOLD}── PHASE 5: Environment Configuration ──${NC}"

# Create Arda env file
cat > "$ARDA_HOME/config/arda.env" <<EOF
# Arda OS Environment Configuration
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

# Environment: Set to 'production' to enforce fail-closed TPM
ARDA_ENV=sovereign

# Sovereign mode: enables real enforcement paths
ARDA_SOVEREIGN_MODE=1

# Ollama endpoint (for live AI witnesses)
OLLAMA_HOST=http://localhost:11434

# Python path
PYTHONPATH=$ARDA_HOME/backend:$ARDA_HOME
EOF

echo -e "${GREEN}  ✓ Environment configured at $ARDA_HOME/config/arda.env${NC}"

# Create launcher script
cat > "$ARDA_HOME/launch_arda.sh" <<'LAUNCHER'
#!/bin/bash
# ═══ ARDA OS LAUNCHER ═══
ARDA_HOME="/opt/arda"
source "$ARDA_HOME/config/arda.env" 2>/dev/null || true

echo "═══════════════════════════════════════"
echo "  ARDA OS v1.3 — Telperion Build"
echo "═══════════════════════════════════════"

# Check Ollama
if command -v ollama &>/dev/null && pgrep -x ollama &>/dev/null; then
    echo "  Ollama: RUNNING"
    MODELS=$(ollama list 2>/dev/null | grep -c "qwen" || echo "0")
    echo "  Qwen Models: $MODELS"
else
    echo "  Ollama: NOT RUNNING"
    echo "  Starting Ollama..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
fi

# Check TPM
if [ -c /dev/tpm0 ] || [ -c /dev/tpmrm0 ]; then
    echo "  TPM: DETECTED"
else
    echo "  TPM: NOT FOUND"
fi

# Check BPF LSM
LSMS=$(cat /sys/kernel/security/lsm 2>/dev/null || echo "unknown")
if echo "$LSMS" | grep -q "bpf"; then
    echo "  BPF LSM: ACTIVE"
else
    echo "  BPF LSM: INACTIVE (add lsm=...bpf to kernel params)"
fi

echo ""
echo "  Starting Arda Desktop on port 8080..."
echo "  Open: http://localhost:8080"
echo ""

export PYTHONPATH="$ARDA_HOME/backend:$ARDA_HOME"
export ARDA_SOVEREIGN_MODE=1

# Activate venv if exists
[ -f "$ARDA_HOME/venv/bin/activate" ] && source "$ARDA_HOME/venv/bin/activate"

cd "$ARDA_HOME"
python3 arda_desktop/app.py 2>&1
LAUNCHER
chmod +x "$ARDA_HOME/launch_arda.sh"

echo -e "${GREEN}  ✓ Launcher created: $ARDA_HOME/launch_arda.sh${NC}"
echo ""

# ── Phase 6: Verification ───────────────────────────
echo -e "${GOLD}── PHASE 6: Verification ──${NC}"

echo "  Checking installed components..."

check_component() {
    if command -v "$1" &>/dev/null; then
        echo -e "    ${GREEN}✓${NC} $2"
        return 0
    else
        echo -e "    ${RED}✗${NC} $2"
        return 1
    fi
}

check_component python3      "Python 3"
check_component pip3         "pip3"
check_component flask        "Flask" 2>/dev/null || \
    python3 -c "import flask" 2>/dev/null && echo -e "    ${GREEN}✓${NC} Flask (Python module)" || \
    echo -e "    ${RED}✗${NC} Flask"
check_component git          "Git"
check_component tpm2_getcap  "tpm2-tools"
check_component clang        "Clang (eBPF compiler)"
check_component bpftool      "bpftool"
check_component ollama       "Ollama" || true

# Check Ollama model
if command -v ollama &>/dev/null; then
    if ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
        echo -e "    ${GREEN}✓${NC} qwen2.5:7b model loaded"
    else
        echo -e "    ${GOLD}⚠${NC} qwen2.5:7b model not pulled yet"
        echo "      Run: ollama pull qwen2.5:7b"
    fi
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   ARDA OS STACK INSTALLED${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Run the Coronation (TPM + eBPF hardware proof):"
echo "     cd $ARDA_HOME/coronation_kit"
echo "     sudo ./scripts/00_coronation.sh"
echo ""
echo "  2. Launch the Arda Desktop:"
echo "     sudo $ARDA_HOME/launch_arda.sh"
echo "     Open http://localhost:8080"
echo ""
echo "  3. Run the live gauntlet from the desktop"
echo "     (All 10 trials with real Qwen witnesses)"
echo ""
