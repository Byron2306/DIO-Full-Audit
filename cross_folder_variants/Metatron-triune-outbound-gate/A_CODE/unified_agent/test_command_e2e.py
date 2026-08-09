"""
End-to-end test: Server → Agent command flow
1. Start agent core (headless)
2. Wait for registration + first heartbeat
3. Send a command via admin API (swarm router)
4. Wait for agent to poll and execute it
5. Verify command result via swarm router
"""
import sys, os, time, json, requests, threading

# Add parent paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ui", "desktop"))

from main import UnifiedAgentCore

BACKEND = os.getenv("METATRON_BACKEND_URL", "http://localhost:8001").rstrip('/')
TOKEN = None

def get_token():
    global TOKEN
    resp = requests.post(f"{BACKEND}/api/auth/login", json={
        "email": "admin@seraph.io", "password": "TestAdmin123!"
    })
    TOKEN = resp.json()["access_token"]
    return TOKEN

def auth_headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def send_command(agent_id, cmd_type, params=None, priority="normal"):
    resp = requests.post(
        f"{BACKEND}/api/swarm/agents/{agent_id}/command",
        json={"type": cmd_type, "params": params or {}, "priority": priority},
        headers=auth_headers()
    )
    print(f"  Send '{cmd_type}' → {resp.status_code}: {resp.json()}")
    return resp.json()

def check_command_history(agent_id):
    """Check command results via agent_commands router."""
    resp = requests.get(
        f"{BACKEND}/api/agent-commands/history",
        headers=auth_headers(),
        params={"agent_id": agent_id}
    )
    if resp.status_code == 200:
        return resp.json()
    return None

def main():
    print("=" * 60)
    print("E2E TEST: Server → Agent Command Flow")
    print("=" * 60)

    # 1. Auth
    print("\n[1] Authenticating with backend...")
    get_token()
    print(f"  Token: {TOKEN[:20]}...")

    # 2. Start agent
    print("\n[2] Starting UnifiedAgentCore (headless)...")
    agent = UnifiedAgentCore()
    agent_id = agent.config.agent_id
    print(f"  Agent ID: {agent_id}")
    print(f"  Agent Name: {agent.config.agent_name}")

    agent.start()
    print("  Agent started - waiting 5s for registration + heartbeat...")
    time.sleep(5)
    print(f"  Registered: {agent.registered}")
    print(f"  Last heartbeat: {agent._last_heartbeat}")

    # 3. Register with swarm router too (so commands can be created)
    print("\n[3] Ensuring agent is registered with swarm router...")
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    resp = requests.post(f"{BACKEND}/api/swarm/agents/register", json={
        "agent_id": agent_id,
        "hostname": hostname,
        "ip_address": local_ip,
        "platform": "windows",
        "version": "1.0.0",
        "capabilities": ["file_scanning", "process_monitoring", "port_scanning", "command_execution"]
    })
    print(f"  Swarm register: {resp.status_code}")

    # 4. Test commands  
    print("\n[4] Sending commands to agent...")
    
    # Test 4a: status command
    print("\n  --- Test 4a: STATUS command ---")
    cmd1 = send_command(agent_id, "status")
    cmd1_id = cmd1.get("command_id")
    
    # Test 4b: full_scan command
    print("\n  --- Test 4b: FULL_SCAN command ---")
    cmd2 = send_command(agent_id, "full_scan")
    cmd2_id = cmd2.get("command_id")
    
    # Test 4c: shell command (safe)
    print("\n  --- Test 4c: SHELL command (hostname) ---")
    cmd3 = send_command(agent_id, "shell", {"command": "hostname"})
    cmd3_id = cmd3.get("command_id")

    # Test 4d: collect_forensics
    print("\n  --- Test 4d: COLLECT_FORENSICS command ---")
    cmd4 = send_command(agent_id, "collect_forensics")
    cmd4_id = cmd4.get("command_id")

    # 5. Wait for agent to poll and execute
    print("\n[5] Waiting for agent to poll and execute commands...")
    print("  (Agent polls every 15s, initial delay 10s)")
    
    # Wait up to 30 seconds, checking periodically
    for i in range(30):
        time.sleep(1)
        if i % 5 == 0:
            print(f"  ... waiting ({i}s)")
    
    # 6. Check results
    print("\n[6] Checking command results...")
    
    # Check via swarm command status (query MongoDB directly via any available endpoint)
    for cmd_name, cmd_id in [("status", cmd1_id), ("full_scan", cmd2_id), 
                               ("shell", cmd3_id), ("forensics", cmd4_id)]:
        if not cmd_id:
            print(f"  {cmd_name}: NO COMMAND ID")
            continue
        # Poll the command directly - check if it was completed
        # The swarm router marks delivered on GET, but we need to check result
        # Let's check via the agent-commands history endpoint
        resp = requests.get(
            f"{BACKEND}/api/agent-commands/{cmd_id}/result",
            headers=auth_headers()
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"  {cmd_name} ({cmd_id}): status={result.get('status', 'unknown')}")
            if result.get("result"):
                r = result["result"]
                print(f"    success={r.get('success')}, output={str(r.get('output', ''))[:100]}")
        else:
            print(f"  {cmd_name} ({cmd_id}): HTTP {resp.status_code}")
            # Try checking directly from MongoDB via swarm
            # The ack endpoint sets status to completed, so let's check
            # by trying to get commands again (they won't be pending anymore)

    # Also try a direct check - send one more command and wait
    print("\n[7] Quick verification - sending one more 'status' and waiting...")
    cmd5 = send_command(agent_id, "status")
    cmd5_id = cmd5.get("command_id")
    
    # Wait for next poll cycle
    for i in range(20):
        time.sleep(1)
        if i % 5 == 0:
            print(f"  ... waiting ({i}s)")

    # Check the last command result
    resp = requests.get(
        f"{BACKEND}/api/agent-commands/{cmd5_id}/result",
        headers=auth_headers()
    )
    print(f"\n  Last status command result: HTTP {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"  Status: {result.get('status')}")
        if result.get("result"):
            print(f"  Success: {result['result'].get('success')}")
            print(f"  Output: {str(result['result'].get('output', ''))[:200]}")
            if result['result'].get('system_info'):
                si = result['result']['system_info']
                print(f"  CPU: {si.get('cpu_percent')}%, Memory: {si.get('memory_percent')}%")

    # 8. Stop agent
    print("\n[8] Stopping agent...")
    agent.stop()
    print("  Agent stopped")

    print("\n" + "=" * 60)
    print("E2E TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
