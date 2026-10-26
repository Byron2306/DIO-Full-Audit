from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
from typing import Any, Callable

from adapters.document_studio import local_media_compositor as local_media


Resolver = Callable[[str], tuple[dict[str, Any], dict[str, Any]]]
_campaign_context: ContextVar[Any] = ContextVar("dio_local_composition_campaign", default=None)


def install_local_compositor_identity_bridge() -> None:
    """Teach the local compositor DIO's namespaced marketing-family identity.

    Production Studio may bind one configured marketing profile to an exact
    canonical incarnation by constructing product ids such as::

        HOMS_ASSESS--HOMS Assess

    LINGUA then appends the audience id, producing::

        HOMS_ASSESS--HOMS Assess--tutors_publishers

    The marketing matrix still keys the reusable visual/source profile by the
    first segment and the audience by the final segment. The middle segment(s)
    are exact-incarnation lineage and MUST NOT be mistaken for audience text.

    Custom OPERATOR campaigns have no reusable matrix profile. Their exact
    product/audience must come from the active factory call, not an inferred
    alias. Context is isolated per execution and reset even when rendering fails.
    """
    from scripts import build_multichannel_campaign_factory_v3 as factory

    current: Resolver = local_media.resolve_product_audience
    if getattr(current, "_dio_namespaced_identity_bridge", False):
        return

    original: Resolver = current

    def resolve_namespaced_product_audience(family_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        context = _campaign_context.get()
        if context is not None and family_id == context[0]:
            return deepcopy(context[1]), deepcopy(context[2])
        # Preserve the ordinary two-part contract when it already resolves.
        try:
            return original(family_id)
        except local_media.LocalMediaCompositorError as first_error:
            parts = str(family_id or "").split("--")
            if len(parts) < 3:
                raise first_error

            canonical_profile_id = parts[0].strip()
            audience_id = parts[-1].strip()
            if not canonical_profile_id or not audience_id:
                raise first_error

            canonical_family_id = f"{canonical_profile_id}--{audience_id}"
            try:
                return original(canonical_family_id)
            except local_media.LocalMediaCompositorError as second_error:
                raise local_media.LocalMediaCompositorError(
                    "Namespaced marketing family could not be resolved after preserving exact-incarnation lineage: "
                    f"family_id={family_id!r}; canonical_profile_id={canonical_profile_id!r}; audience_id={audience_id!r}; "
                    f"underlying_error={second_error}"
                ) from second_error

    resolve_namespaced_product_audience._dio_namespaced_identity_bridge = True  # type: ignore[attr-defined]
    local_media.resolve_product_audience = resolve_namespaced_product_audience

    original_build = factory.build_family

    @wraps(original_build)
    def build_family(product, audience, channels, output_root, render_reels):
        family_id = f"{product['id']}--{audience['id']}"
        token = _campaign_context.set((family_id, deepcopy(product), deepcopy(audience)))
        try:
            return original_build(product, audience, channels, output_root, render_reels)
        finally:
            _campaign_context.reset(token)

    build_family._dio_campaign_context_bridge = True
    factory.build_family = build_family
