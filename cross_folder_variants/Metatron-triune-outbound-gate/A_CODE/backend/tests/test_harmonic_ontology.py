from backend.schemas.polyphonic_models import HarmonicState, TimingFeatures
from backend.services.harmonic_ontology import get_harmonic_ontology


def test_harmonic_ontology_covers_all_phase_2a_fields():
    ontology = get_harmonic_ontology()
    required = {
        "resonance_score",
        "discord_score",
        "confidence",
        "drift_norm",
        "jitter_norm",
        "burstiness",
        "entropy_signature",
        "sequence_class",
    }
    assert required.issubset(set(ontology.keys()))
    for field_name in required:
        entry = ontology[field_name]
        assert entry["formula"]
        assert entry["domain"]
        assert entry["required_sample_size"] is not None
        assert entry["confidence_penalties"]
        assert entry["misuse_boundaries"]


def test_polyphonic_models_expose_harmonic_field_descriptions():
    timing_schema = TimingFeatures.model_json_schema()
    harmonic_schema = HarmonicState.model_json_schema()

    for field_name in ["jitter_norm", "drift_norm", "burstiness", "entropy_signature", "sequence_class"]:
        assert timing_schema["properties"][field_name]["description"]

    for field_name in ["resonance_score", "discord_score", "confidence", "drift_norm", "jitter_norm"]:
        assert harmonic_schema["properties"][field_name]["description"]
