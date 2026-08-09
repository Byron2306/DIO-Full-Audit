"""E2E simulation script for Harmonic Governance Layer (HGL) cadence testing."""

import asyncio
import json
import logging
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.services.harmonic_engine import get_harmonic_engine
from backend.scripts.test_telemetry_v2 import TelemetryCollector

class PhiAccrualSuspicionTracker:
    """A phi-accrual inspired continuous suspicion tracker to smooth sequence resonance signals."""
    
    def __init__(self, threshold: float = 60.0, recovery_rate: float = 1.2):
        self.suspicion = 0.0
        self.threshold = threshold
        self.recovery_rate = recovery_rate
        
    def add_observation(self, discord: float, resonance: float) -> float:
        # Ignore discord below 0.6 to tolerate heavy benign network jitter.
        if discord < 0.6:
            delta = -resonance * 10.0
        else:
            delta = (discord ** 2 * 25.0) - (resonance * 4.0)
            
        if delta < 0:
            self.suspicion = max(0.0, self.suspicion + delta * self.recovery_rate)
        else:
            self.suspicion += delta
            
        return self.suspicion
        
    def should_contain(self) -> bool:
        return self.suspicion >= self.threshold

class HarmonicCadenceExperiment:
    def __init__(self, collector: TelemetryCollector):
        self.collector = collector
        self.engine = get_harmonic_engine(db=None) 
        self.actor_id = "agent:hgl_test_agent"
        self.tool_name = "sys_read_file"
        self.target_domain = "host_fs"
        self.environment = "test"
        
        self.metrics = {
            "test_duration_ms": 0.0,
            "latency_measurements": [],
            "avg_overhead_ms": 0.0,
            "false_positives": 0,
            "true_positives": 0,
            "time_to_containment_events": 0,
        }

    def _simulate_event(self, timestamp_ms: float, learn_baseline: bool) -> Dict[str, Any]:
        """Submits an event to the Harmonic engine and returns the state."""
        start = time.perf_counter()
        result = self.engine.score_observation(
            actor_id=self.actor_id,
            tool_name=self.tool_name,
            target_domain=self.target_domain,
            environment=self.environment,
            stage="tool_execution",
            timestamp_ms=timestamp_ms,
            context={"learn_baseline": learn_baseline}
        )
        end = time.perf_counter()
        
        latency = (end - start) * 1000.0
        self.metrics["latency_measurements"].append(latency)
        
        self.collector.log_event("observation_score", self.actor_id, self.tool_name, "low", "scored", 
                                 {"latency_ms": latency, "harmonic_observation": result})
        return result

    def run_timing_baseline_acquisition(self) -> float:
        self.collector.set_phase("EXP 1: BASELINE ACQUISITION")
        base_ts = time.time() * 1000.0
        
        # Feed 30 events with perfectly stable ~200ms cadence
        for i in range(30):
            ts = base_ts + (i * 200.0) + random.uniform(-10.0, 10.0)
            self._simulate_event(timestamp_ms=ts, learn_baseline=True)
            
        # Verify the baseline was acquired
        ref = self.engine.select_baseline_scope(
            self.actor_id, self.tool_name, self.target_domain, self.environment
        )
        band = ref.baseline_band
        self.collector.logger.info(f"-> Acquired baseline median_interval_ms: {band['median_interval_ms']:.2f}")
        return base_ts + (30 * 200.0)

    def run_jitter_injection_simulation(self, start_ts: float) -> float:
        self.collector.set_phase("EXP 2: JITTER & DRIFT")
        ts = start_ts
        false_alarms = 0
        tracker = PhiAccrualSuspicionTracker(threshold=60.0)
        
        # Feed 50 events where intervals drift and jitter increases, but stays somewhat benign
        for i in range(50):
            delay = 200.0 + random.uniform(50.0, 150.0) 
            ts += delay
            
            result = self._simulate_event(timestamp_ms=ts, learn_baseline=False)
            harmonic_state = result["harmonic_state"]
            discord = harmonic_state["discord_score"]
            resonance = harmonic_state["resonance_score"]
            
            suspicion = tracker.add_observation(discord, resonance)
            
            if tracker.should_contain():
                false_alarms += 1
                tracker.suspicion = 0.0 # reset for test
                self.collector.log_event("alert", self.actor_id, "phi_accrual", "medium", "false_positive", 
                                         {"suspicion": suspicion, "discord": discord})
                
        self.metrics["false_positives"] += false_alarms
        self.collector.logger.info(f"-> False positives under jitter (Phi Accrual): {false_alarms}/50")
        return ts

    def run_attack_cadence_scenario(self, start_ts: float) -> float:
        self.collector.set_phase("EXP 3 & 4: ATTACK BURST")
        ts = start_ts
        tracker = PhiAccrualSuspicionTracker(threshold=60.0)
        events_to_contain = 0
        contained = False
        
        # Simulate rapid tool spamming (e.g. interval = 20ms)
        for i in range(30):
            ts += random.uniform(5.0, 30.0) # highly bursted
            
            result = self._simulate_event(timestamp_ms=ts, learn_baseline=False)
            harmonic_state = result["harmonic_state"]
            
            suspicion = tracker.add_observation(harmonic_state["discord_score"], harmonic_state["resonance_score"])
            
            if tracker.should_contain() and not contained:
                contained = True
                events_to_contain = i + 1
                self.metrics["true_positives"] += 1
                self.collector.log_event("containment", self.actor_id, "phi_accrual", "high", "contained", 
                                         {"events_to_contain": events_to_contain, "suspicion": suspicion})
                break
                
        if contained:
            self.collector.logger.info(f"-> Threat contained after {events_to_contain} events!")
            self.metrics["time_to_containment_events"] = events_to_contain
        else:
            self.collector.logger.error("-> Failed to contain threat!")
            
        return ts
        
    def generate_report(self):
        measurements: List[float] = self.metrics["latency_measurements"]
        if measurements:
            self.metrics["avg_overhead_ms"] = sum(measurements) / len(measurements)
            
        self.collector.logger.info("=== HGL Cadence Metric Summary ===")
        self.collector.logger.info(f"True Positive Rate (Adversarial Burden):  {self.metrics['true_positives']}/1")
        self.collector.logger.info(f"False Positive Rate (Benign Jitter):    {self.metrics['false_positives']}/50")
        self.collector.logger.info(f"Avg Overhead per Engine Observation:    {self.metrics['avg_overhead_ms']:.3f} ms")
        self.collector.logger.info(f"Time to Containment (Tool calls):       {self.metrics['time_to_containment_events']} events")
        
        self.collector.generate_report()

async def main():
    collector = TelemetryCollector("HARMONIC_CADENCE_TEST")
    experiment = HarmonicCadenceExperiment(collector)
    
    start_time = time.time()
    ts = experiment.run_timing_baseline_acquisition()
    ts = experiment.run_jitter_injection_simulation(start_ts=ts)
    ts = experiment.run_attack_cadence_scenario(start_ts=ts)
    
    end_time = time.time()
    experiment.metrics["test_duration_ms"] = (end_time - start_time) * 1000.0
    experiment.generate_report()

if __name__ == "__main__":
    asyncio.run(main())
