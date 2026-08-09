#!/usr/bin/env bash
# start_local.sh — wire up backend auth, register agent, start dashboard
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/unified_agent"
PYTHON="$AGENT_DIR/venv/bin/python"
BACKEND="http://localhost:8001"
# Default dev secret (set in backend when SERAPH_AGENT_SECRET is unset)
ENROLLMENT_KEY="dev-agent-secret-change-in-production"
LOCAL_EMAIL="local@metatron.local"
LOCAL_PASS="MetatronLocal2026!"

# Load .env file if it exists to pick up INTEGRATION_API_KEY for synchronization
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "      Loading .env variables..."
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# ── 0. Pre-flight DB cleanup ──────────────────────────────────────────────
echo "[0/5] Pre-flight: clearing stale VPN decisions + ensuring local admin..."
"$PYTHON" - << 'PYEOF'
import sys, bcrypt
try:
    import pymongo
    client = pymongo.MongoClient('localhost', 27017, serverSelectionTimeoutMS=3000)
    db = client['seraph_ai_defense']

    # Cancel any queued VPN decisions — wg-quick must NOT run inside the
    # backend container (it rewrites iptables and breaks Docker networking).
    vpn_types = ['vpn_start','vpn_stop','vpn_initialize','vpn_peer_add','vpn_peer_remove',
                 'vpn_kill_switch_enable','vpn_kill_switch_disable']
    r = db.triune_decisions.update_many(
        {'action_type': {'$in': vpn_types},
         'status': {'$nin': ['cancelled','rejected']}},
        {'$set': {'status': 'cancelled', 'execution_status': 'skipped'}}
    )
    print(f"      Cancelled {r.modified_count} VPN decisions.")

    # Ensure local admin user exists with the correct password and role so
    # the dashboard can always authenticate regardless of prior manual changes.
    email = "local@metatron.local"
    password = "MetatronLocal2026!"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    existing = db.users.find_one({'email': email})
    if existing:
        db.users.update_one({'email': email},
            {'$set': {'password': pw_hash, 'role': 'admin'}})
        print(f"      Reset password+role for {email}")
    else:
        import uuid
        db.users.insert_one({
            'id': str(uuid.uuid4()),
            'email': email,
            'password': pw_hash,
            'name': 'Local Admin',
            'role': 'admin',
        })
        print(f"      Created admin user {email}")

except Exception as e:
    print(f"      DB pre-flight error (non-fatal): {e}")
PYEOF

# ── 1. Rebuild + restart backend container to apply code changes ────────────
echo "[1/5] Rebuilding and restarting backend container..."
cd "$SCRIPT_DIR"
docker-compose build backend
docker-compose up -d --no-deps backend
echo "      Waiting for backend to be healthy..."
for i in $(seq 1 20); do
    STATUS=$(curl -sf "$BACKEND/api/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || true)
    [ "$STATUS" = "healthy" ] && break
    printf "."
    sleep 3
done
echo ""
echo "      Backend: ${STATUS:-timeout}"

# ── 2. Ensure local user account exists ───────────────────────────────────
echo "[2/5] Ensuring local user account..."
LOGIN=$(curl -sf -X POST "$BACKEND/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$LOCAL_EMAIL\",\"password\":\"$LOCAL_PASS\"}" 2>/dev/null || true)
if echo "$LOGIN" | python3 -c "import sys,json; json.load(sys.stdin)['access_token']" &>/dev/null; then
    echo "      Logged in as $LOCAL_EMAIL"
else
    echo "      Creating account..."
    curl -sf -X POST "$BACKEND/api/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$LOCAL_EMAIL\",\"password\":\"$LOCAL_PASS\",\"name\":\"Local Admin\"}" 2>/dev/null || true
    echo "      Account created."
fi

# ── 3. Register agent with backend ────────────────────────────────────────
echo "[3/5] Registering agent..."
AGENT_ID="metatron-$(hostname)-local"
REG=$(curl -sf -X POST "$BACKEND/api/unified/agents/register" \
    -H "Content-Type: application/json" \
    -H "X-Enrollment-Key: $ENROLLMENT_KEY" \
    -H "x-agent-id: $AGENT_ID" \
    -d "{
        \"agent_id\": \"$AGENT_ID\",
        \"platform\": \"linux\",
        \"hostname\": \"$(hostname)\",
        \"ip_address\": \"127.0.0.1\",
        \"version\": \"2.0.0\",
        \"capabilities\": [\"monitor\",\"remediate\",\"network_scan\"]
    }" 2>/dev/null || true)

# Extract token and save to file for dashboard/agent use
if [ -n "$REG" ]; then
    TOKEN=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || true)
    if [ -n "$TOKEN" ]; then
        echo "{\"agent_id\": \"$AGENT_ID\", \"auth_token\": \"$TOKEN\"}" > "$AGENT_DIR/agent_auth.json"
        echo "      Agent registered. Token saved to agent_auth.json"
    else
        echo "      Warning: Could not extract agent token from response."
    fi
else
    echo "      Warning: Agent registration failed (no response)."
fi
echo ""

# ── 4. Kill any running dashboard ─────────────────────────────────────────
echo "[4/5] Stopping old dashboard if running..."
pkill -f "ui/web/app.py" 2>/dev/null || true
sleep 1

# ── 5. Start dashboard ────────────────────────────────────────────────────
echo "[5/5] Starting dashboard → http://localhost:5000"
cd "$AGENT_DIR"
# Pass tokens so dashboard can authenticate its backend orchestration calls.
REMOTE_SERVER_URL="$BACKEND" \
    INTEGRATION_API_KEY="$INTEGRATION_API_KEY" \
    SWARM_AGENT_TOKEN="$SWARM_AGENT_TOKEN" \
    "$PYTHON" ui/web/app.py
