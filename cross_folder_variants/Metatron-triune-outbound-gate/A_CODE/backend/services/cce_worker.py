"""
Real-time Cognition Engine Worker
==================================
Background worker that continuously analyzes CLI command streams
and generates session summaries for SOAR playbook evaluation.

This worker:
1. Polls for recent CLI commands across all hosts
2. Groups commands by (host_id, session_id)
3. Runs the CognitionEngine analysis on active sessions
4. Stores summaries and triggers SOAR evaluation

Can be run standalone or integrated into FastAPI's lifespan.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.cognition_engine import CognitionEngine

logger = logging.getLogger(__name__)


class CCEWorker:
    """
    Real-time Cognition/Correlation Engine Worker.
    Continuously monitors CLI command streams for machine-like behavior.
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        analysis_interval_s: int = 10,
        window_s: int = 30,
        min_commands: int = 3,
        max_concurrent_analyses: int = 10
    ):
        """
        Initialize the CCE Worker.
        
        Args:
            db: MongoDB database instance
            analysis_interval_s: How often to check for new sessions (default: 10s)
            window_s: Analysis window for cognition engine (default: 30s)
            min_commands: Minimum commands needed to analyze (default: 3)
            max_concurrent_analyses: Max parallel session analyses (default: 10)
        """
        self.db = db
        self.analysis_interval_s = analysis_interval_s
        self.window_s = window_s
        self.min_commands = min_commands
        self.max_concurrent_analyses = max_concurrent_analyses
        
        self.engine = CognitionEngine(db, config={"time_window_s": window_s})
        self.running = False
        self.task = None
        
        # Track recently analyzed sessions to avoid duplicates
        self._analyzed_sessions: Dict[str, datetime] = {}
        self._analysis_cooldown_s = 15  # Don't re-analyze same session within this period
        
        logger.info(f"CCE Worker initialized: interval={analysis_interval_s}s, window={window_s}s")
    
    async def start(self):
        """Start the background worker"""
        if self.running:
            logger.warning("CCE Worker already running")
            return
            
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info("CCE Worker started")
    
    async def stop(self):
        """Stop the background worker"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("CCE Worker stopped")
    
    async def _run_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                await self._process_active_sessions()
                await asyncio.sleep(self.analysis_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CCE Worker error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _process_active_sessions(self):
        """Find and analyze active CLI sessions"""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.window_s * 2)  # Look back 2x window
        
        # Find distinct (host_id, session_id) pairs with recent activity
        pipeline = [
            {
                "$match": {
                    "event_type": "cli.command",
                    "timestamp": {"$gte": window_start.isoformat()}
                }
            },
            {
                "$group": {
                    "_id": {
                        "host_id": "$host_id",
                        "session_id": "$session_id"
                    },
                    "command_count": {"$sum": 1},
                    "last_command": {"$max": "$timestamp"}
                }
            },
            {
                "$match": {
                    "command_count": {"$gte": self.min_commands}
                }
            },
            {
                "$sort": {"last_command": -1}
            },
            {
                "$limit": self.max_concurrent_analyses * 2
            }
        ]
        
        active_sessions = await self.db.cli_commands.aggregate(pipeline).to_list(100)
        
        if not active_sessions:
            return
        
        logger.debug(f"CCE Worker found {len(active_sessions)} active sessions")
        
        # Filter out recently analyzed sessions
        sessions_to_analyze = []
        for session in active_sessions:
            host_id = session["_id"]["host_id"]
            session_id = session["_id"]["session_id"]
            key = f"{host_id}:{session_id}"
            
            last_analyzed = self._analyzed_sessions.get(key)
            if last_analyzed:
                elapsed = (now - last_analyzed).total_seconds()
                if elapsed < self._analysis_cooldown_s:
                    continue
            
            sessions_to_analyze.append((host_id, session_id))
        
        if not sessions_to_analyze:
            return
        
        # Limit concurrent analyses
        sessions_to_analyze = sessions_to_analyze[:self.max_concurrent_analyses]
        
        # Run analyses concurrently
        tasks = [
            self._analyze_and_store(host_id, session_id)
            for host_id, session_id in sessions_to_analyze
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        success_count = sum(1 for r in results if r is True)
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        if success_count > 0 or error_count > 0:
            logger.info(f"CCE Worker: analyzed {success_count} sessions, {error_count} errors")
    
    async def _analyze_and_store(self, host_id: str, session_id: str) -> bool:
        """Analyze a single session and store/trigger SOAR if needed"""
        key = f"{host_id}:{session_id}"
        
        try:
            # Run cognition analysis
            summary = await self.engine.analyze_session(host_id, session_id, self.window_s)
            
            if not summary:
                return False
            
            # Mark as analyzed
            self._analyzed_sessions[key] = datetime.now(timezone.utc)
            
            # Only store if machine likelihood is noteworthy (>0.3)
            if summary.get("machine_likelihood", 0) < 0.3:
                return True
            
            # Check if we already have a recent summary for this session
            existing = await self.db.cli_session_summaries.find_one(
                {
                    "host_id": host_id,
                    "session_id": session_id,
                    "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(seconds=self._analysis_cooldown_s)).isoformat()}
                },
                {"_id": 1}
            )
            
            if existing:
                return True  # Skip duplicate
            
            # Store the summary
            summary["source"] = "cce_worker"
            await self.db.cli_session_summaries.insert_one(summary)
            await self.db.events_raw.insert_one({**summary, "_id": None})
            
            # Trigger SOAR evaluation for high-risk sessions
            if summary.get("machine_likelihood", 0) >= 0.6:
                await self._trigger_soar(summary)
            
            logger.info(
                f"CCE Summary stored: {host_id}/{session_id} - "
                f"ML:{summary.get('machine_likelihood', 0):.2f} "
                f"Intents:{summary.get('dominant_intents', [])}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"CCE analysis error for {host_id}/{session_id}: {e}")
            return False
    
    async def _trigger_soar(self, summary: dict):
        """Trigger SOAR playbook evaluation for a summary"""
        try:
            from soar_engine import soar_engine
            await soar_engine.evaluate_event(summary, self.db)
        except Exception as e:
            logger.error(f"SOAR trigger error: {e}")
    
    def cleanup_analyzed_cache(self, max_age_s: int = 300):
        """Clean up old entries from analyzed sessions cache"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=max_age_s)
        
        keys_to_remove = [
            key for key, timestamp in self._analyzed_sessions.items()
            if timestamp < cutoff
        ]
        
        for key in keys_to_remove:
            del self._analyzed_sessions[key]
        
        if keys_to_remove:
            logger.debug(f"CCE Worker: cleaned up {len(keys_to_remove)} cached session entries")


# Global worker instance
_cce_worker: CCEWorker = None


def get_cce_worker() -> CCEWorker:
    """Get the global CCE Worker instance"""
    return _cce_worker


async def start_cce_worker(db: AsyncIOMotorDatabase):
    """Start the global CCE Worker"""
    global _cce_worker
    
    if _cce_worker is not None:
        logger.warning("CCE Worker already exists, stopping old instance")
        await _cce_worker.stop()
    
    _cce_worker = CCEWorker(db)
    await _cce_worker.start()
    
    return _cce_worker


async def stop_cce_worker():
    """Stop the global CCE Worker"""
    global _cce_worker
    
    if _cce_worker is not None:
        await _cce_worker.stop()
        _cce_worker = None
