# DIO Product Constitution v1.0

**Status: FROZEN (Phase 0)**

## Canonical hierarchy

1. **DIO** is the single shared governed intelligence organism.
2. **META** is four reusable trust primitives: Evidence, Assurance, Authority and Room.
3. **Work patterns** are twelve reusable operational grammars.
4. **Profiles** configure domain, framework, authority, connectors, outputs and commercial policy.
5. **Incarnations** are named outcome products.
6. **Suites** package incarnations for markets but do not alter runtime semantics.

The canonical product equation is:

```text
DIO PRODUCT
=
Work Pattern
x META Composition
x Domain Profile
x Framework Profile
x Authority Profile
x Connector Pack
x Output Profile
x Commercial Policy
```

## Frozen nouns

- **Product**: a governed composition specification expressed by a DIO Product Manifest. It is not proof of maturity.
- **Profile**: declarative configuration in one of six canonical classes. It does not create authority or execution.
- **Organ**: a reusable internal capability-bearing subsystem behind governed interfaces. It is not a product.
- **Executor**: a runtime implementation resolved to fulfil an execution requirement under existing authority boundaries.
- **Suite**: market packaging only. It does not change runtime, authority or maturity.
- **Incarnation**: a named customer-facing or internal outcome product represented by a product manifest.
- **Work pattern**: domain-independent transformation grammar with an explicit human boundary.
- **META capability**: one of Evidence, Assurance, Authority or Room.

## The anti-spaghetti laws

1. Product manifests request **capabilities**, never concrete organ wiring.
2. Profiles are configuration, never parallel runtime engines.
3. META primitives may be composed but do not create authority, executors, maturity, market validation or revenue proof.
4. Suites may group products but have no execution semantics.
5. A new incarnation normally means a new composition/profile, not a new sovereign runtime.
6. If an execution requirement has no valid executor, the result is **REFUSE**.
7. Valinor remains sole kernel authority. ARDA remains execution identity/attestation authority.
8. Existing portfolio status labels are evidence inputs. They are not silently promoted into the canonical maturity ladder.

## Canonical registries

- `config/portfolio/work_patterns.json`: WP01–WP12.
- `config/portfolio/meta_capabilities.json`: exactly four META primitives.
- `config/portfolio/profile_classes.json`: exactly six profile classes.
- `config/portfolio/maturity_vocabulary.json`: nine maturity states plus independent operational flags.
- `config/portfolio/suites.json`: six market-facing suites with no runtime semantics.
- `config/portfolio/repo_boundaries.json`: ownership boundaries that prevent vertical forks.
- `schemas/dio_product_manifest.schema.json`: machine contract for every product manifest.

## META migration rule

`config/dio_meta_products.json` remains compatibility evidence for the existing META layer. Its `vertical_compositions` are not the source of truth for new compositions. Canonical composition moves to `config/products/manifests/`, with Phase 2 responsible for migration/compilation.

## Phase boundary

Phase 0 does **not** implement concrete source-bound profiles, the Product Compiler, Work Pattern runtimes or Obligation Core.

Those remain Phase 1–4. In particular, no `contractproof.py`, `tenderproof.py`, `grantproof.py` or `permitproof.py` is permitted as a shortcut around the factory.

## Exit condition

Phase 0 is complete when the constitution gate proves:

- one canonical definition exists for product, profile, organ, executor, suite and incarnation;
- exactly 12 work patterns exist;
- exactly four META primitives exist;
- exactly six profile classes exist;
- the maturity vocabulary is fixed;
- manifests cannot create direct organ wiring or a permissive missing-executor path;
- repository ownership makes new vertical engines the exception, not the default.
