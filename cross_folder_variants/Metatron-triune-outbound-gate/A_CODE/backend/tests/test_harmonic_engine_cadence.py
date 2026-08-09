"""Unit tests for HarmonicEngine cadence scoring and resonance metrics."""

import math
import pytest
from typing import Any, Dict, List

from backend.services.harmonic_engine import HarmonicEngine
from backend.services.resonance_service import get_resonance_service
from backend.schemas.polyphonic_models import TimingFeatures, BaselineRef

@pytest.fixture
def engine():
    get_resonance_service().reset()
    return HarmonicEngine(window_size=64)

def test_compute_intervals(engine):
    timestamps = [1000.0, 1200.0, 1400.0, 1600.0]
    intervals = engine.compute_intervals(timestamps)
    assert intervals == [200.0, 200.0, 200.0]
    
def test_compute_jitter(engine):
    intervals = [200.0, 210.0, 190.0, 200.0]
    jitter = engine.compute_jitter(intervals)
    assert math.isclose(jitter, 7.07, rel_tol=0.1) # pstdev of 200, 210, 190, 200
    
def test_compute_drift(engine):
    intervals = [300.0, 310.0, 290.0] # median 300
    band = {"median_interval_ms": 200.0}
    drift = engine.compute_drift(intervals, band)
    assert math.isclose(drift, 0.5, rel_tol=0.01) # abs(300 - 200) / 200 = 0.5
    
def test_compute_burstiness(engine):
    # threshold 80.0
    intervals = [50.0, 200.0, 40.0, 300.0] # 2 out of 4 <= 80
    burstiness = engine.compute_burstiness(intervals, short_threshold_ms=80.0, baseline_expectation=0.0)
    assert burstiness == 0.5

def test_compute_entropy_signature(engine):
    intervals = [200.0, 200.0, 200.0, 200.0]
    entropy = engine.compute_entropy_signature(intervals)
    # Since all fall into the same bucket (probably the 400 bucket given defaults 50, 150, 400, 1000), entropy is 0
    assert entropy == 0.0

def test_score_observation_benign(engine):
    for i in range(10):
        engine.score_observation(
            actor_id="test_actor",
            tool_name="test_tool",
            target_domain="test_domain",
            environment="test_env",
            stage="exec",
            timestamp_ms=1000.0 + i*200.0,
            context={"learn_baseline": True}
        )
    
    # 11th event
    result = engine.score_observation(
        actor_id="test_actor",
        tool_name="test_tool",
        target_domain="test_domain",
        environment="test_env",
        stage="exec",
        timestamp_ms=1000.0 + 10*200.0,
        context={"learn_baseline": False}
    )
    
    state = result["harmonic_state"]
    # We expect high resonance, low discord, normal flow
    assert state["resonance_score"] > 0.8
    assert state["discord_score"] < 0.4
    assert state["mode_recommendation"] == "normal_flow"

def test_score_observation_spam_attack(engine):
    # Establish benign baseline
    for i in range(20):
        engine.score_observation(
            actor_id="attacker",
            tool_name="test_tool",
            target_domain="test_domain",
            environment="test_env",
            stage="exec",
            timestamp_ms=1000.0 + i*200.0,
            context={"learn_baseline": True}
        )
        
    ts = 1000.0 + 20*200.0
    # Attack burst!
    for i in range(15):
        ts += 15.0 # rapid spam
        result = engine.score_observation(
            actor_id="attacker",
            tool_name="test_tool",
            target_domain="test_domain",
            environment="test_env",
            stage="exec",
            timestamp_ms=ts,
            context={"learn_baseline": False}
        )
        
    state = result["harmonic_state"]
    # We expect high discord, low resonance, tighten or sandbox
    assert state["resonance_score"] < 0.75
    assert state["discord_score"] > 0.6
    assert state["mode_recommendation"] in ["sandbox_or_contain", "tighten_scrutiny", "monitor_with_obligations"]
