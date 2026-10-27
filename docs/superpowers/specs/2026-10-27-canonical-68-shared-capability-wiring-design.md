# Canonical 68 Shared Capability Wiring Design

## Goal

Give every canonical commercial offer one deterministic, inspectable production plan that connects its native fulfilment route to the shared professional-quality capabilities: Format Core, Production Studio, Document Studio, and NicheFoundry.

## Design

The ten existing fulfilment routes remain responsible for product substance. A shared capability registry describes the four portfolio services, their real provider references, runtime requirements, and authority boundaries. Each 68-product binding receives the complete catalog so an operator can route any offer through any shared service without inventing product-specific plumbing.

Each binding also receives an ordered capability plan. Document Studio is identified as a required component inside document/publication and HOMS learning routes, and NicheFoundry is identified inside campaign routes. They are not projected as independent executor steps until their route adapters can return hash-bound provider receipts. Format Core and Production Studio are required executable finishing stages for every offer and run after the native route.

The execution profile contains only required steps. Available-on-request services stay visible in the binding but do not execute implicitly. Every step records its purpose, provider, dependencies, and authority boundary. Missing provider source files fail registry construction instead of silently producing false capability claims.

## Truth and authority boundaries

- Capability availability does not claim that a customer artifact passed professional review.
- Provider resolution does not create publication, external-send, pricing, or spend authority.
- NicheFoundry never runs for a non-campaign offer without an approved request.
- All execution remains behind the existing `NEEDS_YOU` gate.
- The existing route adapter remains the product-substance entry point. Dispatch then runs the universal Format Core and Production Studio finish over its held artifacts. Document Studio and NicheFoundry remain route-owned or approved-request capabilities because they need product-specific inputs.

## Acceptance criteria

- Exactly 68 bindings expose all four shared capabilities.
- Every binding requires Format Core and Production Studio after its native route.
- Document Studio and NicheFoundry route-composition requirements are deterministic and do not claim independent execution.
- Every required execution profile step resolves to an existing source file and carries no authority.
- Dispatch proves Format Core and Production Studio with real held artifacts and refuses a partial shared-finish configuration.
- Registry and execution hashes remain deterministic.

