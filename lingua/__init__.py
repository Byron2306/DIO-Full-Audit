"""DIO LINGUA semantic-law and projection surfaces."""

from lingua.semantic_law import build_semantic_law, validate_projection
from lingua import product_projection as _product_projection
from lingua.audience_archetype import classify_audience_archetype

# Compatibility injection for the current M1 projection module. The projection
# builder performs a module-global lookup of audience_archetype at execution
# time, so this keeps the live API stable while moving audience classification
# to its own semantic-precedence surface.
_product_projection.audience_archetype = classify_audience_archetype

build_projection_plan = _product_projection.build_projection_plan
creative_distance = _product_projection.creative_distance
project_story = _product_projection.project_story

__all__ = [
    "build_semantic_law",
    "validate_projection",
    "classify_audience_archetype",
    "build_projection_plan",
    "creative_distance",
    "project_story",
]
