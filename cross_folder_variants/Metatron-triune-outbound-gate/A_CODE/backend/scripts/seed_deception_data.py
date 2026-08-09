import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.getcwd())

async def seed():
    print("--- Seeding Deception Engine Demo Data ---")
    try:
        from deception_engine import deception_engine
        from threat_response import AIDefenseEngine
        
        # 1. Create mock IPs and behavioral events
        mock_ips = [
            ("192.168.1.45", "Scraper-Bot/2.1", "aggressive_scan"),
            ("10.0.5.112", "Mozilla/5.0 (Kali)", "credential_stuffing"),
            ("172.16.0.8", "curl/7.68.0", "path_traversal")
        ]
        
        paths = [
            "/admin", "/config.php", "/.env", "/backup.sql", 
            "/api/v2/users", "/wp-login.php", "/shell.php"
        ]
        
        for ip, ua, behavior in mock_ips:
            print(f"Generating events for {ip}...")
            for path in paths:
                # Add some randomness to score
                flags = {behavior: True, "high_velocity": True}
                assessment = await deception_engine.process_request(
                    ip=ip,
                    path=path,
                    headers={"User-Agent": ua},
                    behavior_flags=flags
                )
                
            # Record some decoy hits
            print(f"Recording decoy interactions for {ip}...")
            await deception_engine.record_decoy_interaction(
                ip=ip,
                decoy_type="credentials",
                decoy_id=f"honey-creds-{ip.split('.')[-1]}",
                headers={"User-Agent": ua}
            )
            
        # 2. Deploy some decoys in AIDefenseEngine
        print("Deploying demo decoys...")
        await AIDefenseEngine.deploy_decoy(
            host_id="demo-host-01",
            decoy_type="credentials",
            decoys=["svc_admin:P@ssw0rd123", "api_key_prod_de82", "ssh_honey_key"],
            placement="filesystem"
        )
        
        print(f"Success! Seeded:")
        print(f"- Campaigns: {len(deception_engine.campaigns)}")
        print(f"- Events: {len(deception_engine.events)}")
        print(f"- Fingerprints: {len(deception_engine.fingerprints)}")
        print(f"- Deployed DecoY Batches: {len(AIDefenseEngine.deployed_decoys)}")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(seed())
