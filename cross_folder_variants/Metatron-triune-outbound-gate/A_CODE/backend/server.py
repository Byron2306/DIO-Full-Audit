"""
Anti-AI Defense System - Main Server
=====================================
Modular FastAPI application with comprehensive security features.

This server has been refactored from a monolithic 2700+ line file into
clean, modular routers for better maintainability.

v3.0 Features:
- Threat Intelligence Feeds
- Ransomware Protection
- Container Security (Trivy)
- VPN Integration (WireGuard)
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from backend.services.runtime_environment import is_production_like

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize database for routers
from routers.dependencies import set_database
set_database(db)

# Initialize services with database
from audit_logging import audit
from threat_timeline import timeline_builder
from threat_intel import threat_intel
from ransomware_protection import ransomware_protection
from container_security import container_security
from vpn_integration import vpn_manager
from threat_correlation import correlation_engine
from edr_service import edr_manager

audit.set_database(db)
timeline_builder.set_database(db)
threat_intel.set_database(db)
ransomware_protection.set_database(db)
container_security.set_database(db)
vpn_manager.set_database(db)
correlation_engine.set_database(db)
correlation_engine.set_threat_intel(threat_intel)
edr_manager.set_database(db)

# Create FastAPI app
app = FastAPI(
    title="Anti-AI Defense System API",
    description="Comprehensive agentic cybersecurity platform for detecting and responding to AI-powered threats",
    version="3.0.0"
)

FRONTEND_BUILD_DIR = ROOT_DIR.parent / "frontend" / "build"
FRONTEND_INDEX = FRONTEND_BUILD_DIR / "index.html"
if (FRONTEND_BUILD_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")), name="frontend-static")

def _resolve_cors_origins() -> List[str]:
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://165.22.41.184,http://165.22.41.184:3000,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5000,http://127.0.0.1:5000",
    )
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    prod_like = is_production_like()

    if prod_like and (not origins or "*" in origins):
        raise RuntimeError("CORS_ORIGINS must be explicit in production/strict mode; wildcard is not allowed.")

    return origins or ["http://165.22.41.184", "http://localhost:3000"]


# Configure CORS
cors_origins = _resolve_cors_origins()
allow_credentials = "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS configured with {len(cors_origins)} origin(s); credentials={'enabled' if allow_credentials else 'disabled'}")

# Import all routers
from routers.auth import router as auth_router, users_router
from routers.threats import router as threats_router
from routers.alerts import router as alerts_router
from routers.ai_analysis import router as ai_router
from routers.dashboard import router as dashboard_router
from routers.network import router as network_router
from routers.hunting import router as hunting_router
from routers.honeypots import router as honeypots_router
from routers.reports import router as reports_router
from routers.agents import router as agents_router, agents_router as agents_list_router
from routers.quarantine import router as quarantine_router
from routers.settings import router as settings_router
from routers.response import router as response_router
from routers.audit import router as audit_router
from routers.timeline import router as timeline_router, timelines_router
from routers.websocket import router as websocket_router
from routers.openclaw import router as openclaw_router
from routers.threat_intel import router as threat_intel_router
from routers.ransomware import router as ransomware_router
from routers.containers import router as containers_router
from routers.vpn import router as vpn_router
from routers.integrations import router as integrations_router
from routers.correlation import router as correlation_router
from routers.edr import router as edr_router
soar_router = None
try:
    from routers.soar import router as soar_router
except Exception as e:
    logger.warning(f"SOAR router disabled due to import error: {e}")
from routers.honey_tokens import router as honey_tokens_router
from routers.zero_trust import router as zero_trust_router
# from routers.ml_prediction import router as ml_router  # Disabled due to numpy import issue
from routers.sandbox import router as sandbox_router
from routers.browser_isolation import router as browser_isolation_router
from routers.kibana import router as kibana_router
from routers.identity import router as identity_router
from routers.attestation import router as attestation_router
from routers.fabric import router as fabric_router
from routers.formation import router as formation_router
from routers.metatron import router as metatron_router
from routers.sigma import router as sigma_router
from routers.osquery import router as osquery_router
from routers.zeek import router as zeek_router
from routers.mitre_attack import router as mitre_attack_router
from routers.atomic_validation import router as atomic_validation_router
from routers.deception import router as deception_router
from routers.policies import router as policies_router
from routers.system_services import router as system_services_router
from routers.ledger import router as ledger_router
from routers.kernel_advanced import router as kernel_advanced_router
from routers.reasoning import router as reasoning_router
from routers.specialist import router as specialist_router
from routers.foundation import router as foundation_router

# Import Browser Extension router
from routers.extension import router as extension_router

# Import Multi-Tenant router
from routers.multi_tenant import router as multi_tenant_router

# Import Tier 1 Enterprise Security routers (fail-open if optional modules are incompatible)
attack_paths_router = None
secure_boot_router = None
kernel_sensors_router = None
kernel_router = None

try:
    from routers.attack_paths import router as attack_paths_router
except Exception as e:
    logger.warning(f"Attack paths router disabled due to import error: {e}")

try:
    from routers.secure_boot import router as secure_boot_router
except Exception as e:
    logger.warning(f"Secure boot router disabled due to import error: {e}")

try:
    from routers.kernel_sensors import router as kernel_sensors_router
except Exception as e:
    logger.warning(f"Kernel sensors router disabled due to import error: {e}")

try:
    from routers.kernel import router as kernel_router
except Exception as e:
    logger.warning(f"Kernel enforcement router disabled due to import error: {e}")

platform_sovereignty_router = None
try:
    from routers.platform_sovereignty import router as platform_sovereignty_router
except Exception as e:
    logger.warning(f"Platform sovereignty router disabled due to import error: {e}")

# Initialize ML service with database
from ml_threat_prediction import ml_predictor
ml_predictor.set_database(db)

# Register all routers with /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(threats_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(network_router, prefix="/api")
app.include_router(hunting_router, prefix="/api")
app.include_router(honeypots_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(agents_list_router, prefix="/api")
app.include_router(quarantine_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(response_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(timeline_router, prefix="/api")
app.include_router(timelines_router, prefix="/api")
app.include_router(websocket_router, prefix="/api")
app.include_router(openclaw_router, prefix="/api")
app.include_router(threat_intel_router, prefix="/api")
app.include_router(ransomware_router, prefix="/api")
app.include_router(containers_router, prefix="/api")
app.include_router(vpn_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(correlation_router, prefix="/api")
app.include_router(edr_router, prefix="/api")
if soar_router is not None:
    app.include_router(soar_router, prefix="/api")
app.include_router(honey_tokens_router, prefix="/api")
app.include_router(zero_trust_router, prefix="/api")
# app.include_router(ml_router, prefix="/api")  # Disabled due to numpy import issue
app.include_router(sandbox_router, prefix="/api")
app.include_router(browser_isolation_router, prefix="/api")
app.include_router(kibana_router, prefix="/api")
app.include_router(attestation_router, prefix="/api")
app.include_router(fabric_router, prefix="/api")
app.include_router(formation_router, prefix="/api")
app.include_router(metatron_router, prefix="/api")
app.include_router(sigma_router, prefix="/api")
app.include_router(osquery_router, prefix="/api")
app.include_router(zeek_router, prefix="/api")
app.include_router(mitre_attack_router, prefix="/api")
app.include_router(atomic_validation_router, prefix="/api")
app.include_router(deception_router, prefix="/api")
app.include_router(policies_router, prefix="/api")
app.include_router(system_services_router, prefix="/api")
app.include_router(ledger_router, prefix="/api")
app.include_router(kernel_advanced_router, prefix="/api")
app.include_router(reasoning_router, prefix="/api")
app.include_router(specialist_router, prefix="/api")
app.include_router(foundation_router, prefix="/api")

# Register Browser Extension router
app.include_router(extension_router, prefix="/api")

# Register Multi-Tenant router
app.include_router(multi_tenant_router, prefix="/api")

# Register Tier 1 Enterprise Security routers
if attack_paths_router is not None:
    app.include_router(attack_paths_router)  # Already has /api/v1 prefix
if secure_boot_router is not None:
    app.include_router(secure_boot_router)   # Already has /api/v1 prefix
if kernel_sensors_router is not None:
    app.include_router(kernel_sensors_router)  # Already has /api/v1 prefix
if kernel_router is not None:
    app.include_router(kernel_router, prefix="/api")  # Enforcement endpoints

if platform_sovereignty_router is not None:
    app.include_router(platform_sovereignty_router, prefix="/api")  # WorldManifold

# Import agent commands router
from routers.agent_commands import router as agent_commands_router
app.include_router(agent_commands_router, prefix="/api")

# Import CLI events router for AI-Agentic defense
from routers.cli_events import router as cli_events_router, deception_router
app.include_router(cli_events_router, prefix="/api")
app.include_router(deception_router, prefix="/api")

# Import Swarm Management router
from routers.swarm import router as swarm_router
app.include_router(swarm_router, prefix="/api")

# Import AI Threats (AATL/AATR) router
from routers.ai_threats import router as ai_threats_router
app.include_router(ai_threats_router, prefix="/api")

# Import Enterprise Security router (Identity, Policy, Tokens, Tools, Telemetry)
from routers.enterprise import router as enterprise_router
app.include_router(enterprise_router, prefix="/api")

# Import CSPM (Cloud Security Posture Management) router
from routers.cspm import router as cspm_router
app.include_router(cspm_router)  # Already has /api/v1 prefix

# Import Advanced Security router (MCP, Vector Memory, VNS, Quantum, AI)
from routers.advanced import router as advanced_router
app.include_router(advanced_router, prefix="/api")

# Import Unified Agent router (Metatron integration)
from routers.unified_agent import router as unified_agent_router
app.include_router(unified_agent_router, prefix="/api")

# ============ EMAIL PROTECTION ============
from routers.email_protection import router as email_protection_router
app.include_router(email_protection_router, prefix="/api")

# ============ MOBILE SECURITY ============
from routers.mobile_security import router as mobile_security_router
app.include_router(mobile_security_router, prefix="/api")

# ============ EMAIL GATEWAY ============
from routers.email_gateway import router as email_gateway_router
app.include_router(email_gateway_router, prefix="/api")

# ============ MDM CONNECTORS ============
from routers.mdm_connectors import router as mdm_connectors_router
app.include_router(mdm_connectors_router, prefix="/api")

# ============ DECEPTION ENGINE ============
# Import advanced deception system with Pebbles, Mystique, and Stonewall
from routers.deception import router as deception_engine_router
app.include_router(deception_engine_router, prefix="/api")  # Now /api/deception
app.include_router(deception_engine_router, prefix="/api/v1")  # Frontend compatibility: /api/v1/deception
app.include_router(identity_router)  # Already has /api/v1/identity prefix

# Initialize deception engine and integrate with existing systems
from deception_engine import deception_engine, integrate_with_honey_tokens, integrate_with_ransomware_protection
from honey_tokens import honey_token_manager
from ransomware_protection import ransomware_protection as ransomware_mgr

deception_engine.set_database(db)
integrate_with_honey_tokens(honey_token_manager)
integrate_with_ransomware_protection(ransomware_mgr.behavior_detector)

# Wire deception engine alert callback → SOAR evaluate_event (Gap A)
# Every TRAP_SINK / HONEYPOT / decoy-touch and Stonewall escalation now
# feeds directly into the ai_decoy_hit_01 playbook chain.
from soar_engine import soar_engine as _soar_engine_ref

async def _deception_soar_handler(event: dict):
    try:
        raw_type = event.get("event_type", "")
        # Disinformation persistence alerts are forwarded as-is so SOAR can
        # route them to _evaluate_disinfo_persistence instead of the generic
        # deception.hit handler.
        if raw_type == "deception.disinfo":
            await _soar_engine_ref.evaluate_event({
                "event_type": "deception.disinfo",
                "host_id": event.get("source_ip"),
                "session_id": event.get("session_id"),
                "campaign_id": event.get("campaign_id"),
                "source_ip": event.get("source_ip"),
                "risk_score": event.get("risk_score", 0),
                "disinfo_events": event.get("disinfo_events", 0),
                "path": (event.get("details") or {}).get("path", "/"),
            }, db)
            return
        route = event.get("route_decision", "")
        severity = "critical" if route in ("trap_sink", "honeypot") else "high"
        await _soar_engine_ref.evaluate_event({
            "event_type": "deception.hit",
            "host_id": event.get("source_ip"),
            "session_id": event.get("session_id"),
            "campaign_id": event.get("campaign_id"),
            "source_ip": event.get("source_ip"),
            "token_id": (event.get("details") or {}).get("decoy_id"),
            "decoy_type": (event.get("details") or {}).get("decoy_type", event.get("event_type", "unknown")),
            "severity": severity,
            "risk_score": event.get("risk_score", 0),
            "route": route,
        }, db)
    except Exception:
        pass

def _deception_alert_bridge(event: dict):
    try:
        asyncio.create_task(_deception_soar_handler(event))
    except RuntimeError:
        pass  # no running event loop (e.g. import-time / test context)

deception_engine.set_alert_callback(_deception_alert_bridge)

# ============ WEBSOCKET ENDPOINTS ============

from routers.honeypots import ws_manager
from websocket_service import realtime_ws

@app.websocket("/ws/threats")
async def websocket_threats(websocket: WebSocket):
    """WebSocket endpoint for real-time threat updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "message": "received"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.websocket("/ws/agent/{agent_id}")
async def websocket_agent(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for agent real-time communication"""
    await realtime_ws.connect(websocket, agent_id)
    try:
        while True:
            data = await websocket.receive_json()
            await realtime_ws.handle_message(agent_id, data)
    except WebSocketDisconnect:
        await realtime_ws.disconnect(agent_id)

# ============ ROOT ENDPOINT ============

@app.get("/enroll")
async def enrollment_redirect():
    """Send backend-port enrollment visits to the React enrollment page."""
    if FRONTEND_INDEX.exists():
        return FileResponse(str(FRONTEND_INDEX))
    configured = os.environ.get("SERAPH_ENROLLMENT_URL", "").strip()
    if configured:
        return RedirectResponse(configured)
    public_url = os.environ.get("SERAPH_PUBLIC_URL", "").strip().rstrip("/")
    if public_url:
        return RedirectResponse(f"{public_url}/enroll")
    return RedirectResponse("http://localhost:3000/enroll")


@app.get("/unified-agent")
async def unified_agent_dashboard_shell():
    """Serve the React unified agent dashboard from the backend/ngrok domain."""
    if FRONTEND_INDEX.exists():
        return FileResponse(str(FRONTEND_INDEX))
    return RedirectResponse("http://localhost:3000/unified-agent")


@app.get("/command")
async def command_workspace_shell():
    """Serve the React command workspace from the backend/ngrok domain."""
    if FRONTEND_INDEX.exists():
        return FileResponse(str(FRONTEND_INDEX))
    return RedirectResponse("http://localhost:3000/command")

@app.get("/api/")
async def root():
    """API root endpoint"""
    return {
        "name": "Anti-AI Defense System API",
        "version": "3.0.0",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": [
            "threat_detection",
            "ai_analysis",
            "network_topology",
            "threat_hunting",
            "honeypots",
            "quarantine",
            "auto_response",
            "audit_logging",
            "timeline_reconstruction",
            "openclaw_integration",
            "threat_intelligence_feeds",
            "ransomware_protection",
            "container_security",
            "vpn_integration",
            "threat_correlation",
            "edr_capabilities",
            "memory_forensics",
            "deception_engine",
            "campaign_tracking_pebbles",
            "adaptive_deception_mystique",
            "progressive_escalation_stonewall"
        ]
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected"
    }

# ============ SHUTDOWN HANDLER ============

@app.on_event("startup")
async def startup():
    """Initialize background services on startup"""
    logger.info("Starting Seraph AI Defense System services...")

    # ------------------------------------------------------------------
    # Seed initial admin account from environment variables.
    # Only runs when no admin user exists, so it is safe to restart.
    # Set ADMIN_EMAIL, ADMIN_PASSWORD, and ADMIN_NAME in your .env file.
    # ------------------------------------------------------------------
    try:
        import uuid
        from routers.dependencies import hash_password
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
        admin_name = os.environ.get("ADMIN_NAME", "Seraph Admin").strip()
        if admin_email and admin_password:
            existing_admin = await db.users.find_one({"role": "admin"})
            if not existing_admin:
                existing_user = await db.users.find_one({"email": admin_email})
                if existing_user:
                    # Promote existing account to admin
                    await db.users.update_one(
                        {"email": admin_email},
                        {"$set": {"role": "admin"}}
                    )
                    logger.info(f"Promoted existing user '{admin_email}' to admin role")
                else:
                    user_id = str(uuid.uuid4())
                    await db.users.insert_one({
                        "id": user_id,
                        "email": admin_email,
                        "password": hash_password(admin_password),
                        "name": admin_name,
                        "role": "admin",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(f"Admin account created for '{admin_email}'")
            else:
                logger.info("Admin account already exists – skipping seed")
        else:
            logger.warning(
                "ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin seed. "
                "Set these in your .env file, or use POST /api/auth/setup "
                "(with X-Setup-Token if SETUP_TOKEN is configured) to create "
                "the first admin account manually."
            )
    except Exception as e:
        logger.error(f"Failed to seed admin account: {e}")
    
    # Start the CCE (Cognition/Correlation Engine) Worker
    try:
        from services.cce_worker import start_cce_worker
        await start_cce_worker(db)
        logger.info("CCE Worker started successfully")
    except Exception as e:
        logger.error(f"Failed to start CCE Worker: {e}")
    
    # Start Network Discovery Service only when explicitly enabled. Manual scan
    # endpoints can still start it on demand.
    network_discovery_enabled = os.environ.get("NETWORK_DISCOVERY_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if network_discovery_enabled:
        try:
            from services.network_discovery import start_network_discovery

            interval = int(os.environ.get("NETWORK_DISCOVERY_INTERVAL", "1800"))
            await start_network_discovery(db, scan_interval_s=interval)
            logger.info("Network Discovery Service started successfully")
        except Exception as e:
            logger.error(f"Failed to start Network Discovery Service: {e}")
    else:
        logger.info("Network Discovery Service disabled on boot")
    
    # Start Agent Deployment Service
    try:
        from services.agent_deployment import start_deployment_service
        api_url = os.environ.get('API_URL', 'http://165.22.41.184:8001')
        await start_deployment_service(db, api_url)
        logger.info("Agent Deployment Service started successfully")
    except Exception as e:
        logger.error(f"Failed to start Agent Deployment Service: {e}")
    
    # Initialize OS Enforcement Service (starts BPF LSM arm thread + auto-enforce)
    try:
        from services.os_enforcement_service import get_os_enforcement_service
        get_os_enforcement_service()  # Creates singleton and starts arm thread
        logger.info("OS Enforcement Service: arm thread started")
    except Exception as e:
        logger.error(f"Failed to initialize OS Enforcement Service: {e}")

    # Initialize AATL (Autonomous Agent Threat Layer)
    try:
        from services.aatl import init_aatl_engine
        await init_aatl_engine(db)
        logger.info("AATL Engine initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AATL Engine: {e}")
    
    # Initialize AATR (Autonomous AI Threat Registry)
    try:
        from services.aatr import init_aatr
        await init_aatr(db)
        logger.info("AATR initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AATR: {e}")

    # MongoDB indexes for UI-critical endpoints (Command Center, dashboards).
    try:
        await db.agent_commands.create_index([("created_at", -1)])
        await db.agent_commands.create_index([("agent_id", 1), ("created_at", -1)])
        await db.agent_commands.create_index([("status", 1), ("created_at", -1)])
        await db.agent_commands.create_index([("id", 1)])
        await db.agent_commands.create_index([("command_id", 1)])
        await db.integrations_jobs.create_index([("id", 1)])
        await db.integrations_jobs.create_index([("command_id", 1)])
        await db.alerts.create_index([("created_at", -1)])
        await db.threats.create_index([("created_at", -1)])
        await db.unified_agents.create_index([("last_heartbeat", -1)])
        logger.info("MongoDB indexes ensured")
    except Exception as e:
        logger.warning(f"Failed to ensure MongoDB indexes: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down Seraph AI Defense System...")
    
    # Stop the CCE Worker
    try:
        from services.cce_worker import stop_cce_worker
        await stop_cce_worker()
        logger.info("CCE Worker stopped")
    except Exception as e:
        logger.error(f"Error stopping CCE Worker: {e}")
    
    # Stop Network Discovery Service
    try:
        from services.network_discovery import stop_network_discovery
        await stop_network_discovery()
        logger.info("Network Discovery Service stopped")
    except Exception as e:
        logger.error(f"Error stopping Network Discovery: {e}")
    
    # Stop Agent Deployment Service
    try:
        from services.agent_deployment import stop_deployment_service
        await stop_deployment_service()
        logger.info("Agent Deployment Service stopped")
    except Exception as e:
        logger.error(f"Error stopping Deployment Service: {e}")
    
    client.close()

# ============ MAIN ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
