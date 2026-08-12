# DIO Unified Workspace

DIO is one organism. The local developer/operator experience should reflect that.

The canonical local entry point is now:

```text
/home/byron/DIO
```

The workspace is intentionally **not** a destructive monorepo migration. Existing organ repositories retain their own Git histories, dirty worktrees, remotes, services and hard-coded paths. The workspace mounts those live repositories into one canonical tree and makes Phase 0 resolve those mounts before any legacy path hint.

## Layout

```text
/home/byron/DIO/
├── dio                 # one command surface
├── WORKSPACE.json      # hashed mount/source receipt
├── README.md
├── core/               # current DIO-Full-Audit checkout
├── organs/
│   ├── sophia/
│   ├── beast/
│   ├── metatron/
│   ├── arda/
│   ├── seraph/
│   ├── phoenix/
│   └── legalis/
├── surfaces/
│   └── workflows-site/
├── state/
│   └── system_snapshots/
└── receipts/
```

A mounted organ is a filesystem link to the authoritative current worktree. The workspace receipt records the resolved target, Git root, HEAD, branch, dirty state and evidence-marker discovery used for resolution.

## Why links instead of physically moving everything

Moving the existing repositories would be dangerous at this stage because some local services, scripts and current production work may depend on their present absolute paths. A move could also destroy the evidentiary value of dirty/unpublished work by forcing premature commits or copies.

The workspace therefore gives DIO **one operational folder without rewriting history or relocating live organs**.

The policy from this point forward is different: new cross-cutting DIO meta-layers belong in `core`; an organ only remains a separate repository when its independent lifecycle genuinely benefits DIO.

## Build the workspace

From the active DIO Full Audit checkout:

```bash
python3 scripts/build_unified_dio_workspace.py --repair
```

The builder:

1. creates `/home/byron/DIO`;
2. mounts the current Full Audit checkout as `core`;
3. resolves known organ paths from `config/dio_workspace.json`;
4. performs bounded content-marker discovery where names alone are insufficient, especially for Legalis;
5. refuses `READY_FOR_PHASE0` if a required organ cannot be resolved;
6. writes `WORKSPACE.json` with a canonical SHA-256 receipt;
7. creates the executable `./dio` launcher.

It never moves or modifies source repositories.

## One command surface

```bash
cd /home/byron/DIO
./dio status
./dio doctor
./dio phase0
./dio phase1
./dio phase01
```

### `./dio phase0`

Runs the cross-system truth capture through the unified workspace. Workspace mounts override legacy absolute path hints. The snapshot is written to:

```text
/home/byron/DIO/state/system_snapshots/latest.json
```

A mounted source is **not** automatically accepted. If an expected implementation/evidence marker is missing, Phase 0 returns `BLOCKED` with `EXPECTED_EVIDENCE_MARKER_MISSING`.

### `./dio phase1`

Compiles the Phase 0/1 Python surface and runs the governed product/case/migration/workspace tests against the current core checkout.

### `./dio phase01`

Runs Phase 0 first. Phase 1 does not start unless Phase 0 earns `READY`.

This establishes the invariant:

```text
CURRENT SOURCE TRUTH
       must pass
          ↓
GOVERNED CASE CORE
       may be tested
```

## Legalis discovery

Legalis is deliberately not resolved by guessing that a folder called `Legalis` must be authoritative. Candidate directories are accepted only when configured marker terms such as `requirement registry`, `evidence receipts`, and `NEEDS_YOU` are found in bounded text-source scanning. The scan includes untracked worktree files so unpublished Wave 1 work can still be captured honestly.

After workspace resolution, Phase 0 performs its own stricter expected-marker gate before implementation claims can be promoted.

## Truth boundary

The unified folder changes **ergonomics**, not provenance.

`/home/byron/DIO/organs/sophia` does not erase Integritas history.

`/home/byron/DIO/organs/beast` does not turn BEAST into a copied snapshot.

`/home/byron/DIO/organs/legalis` does not certify Legalis merely because the mount exists.

The one-folder view is an operator surface over explicit source identities. DIO remains able to say exactly which repository/worktree and which content fingerprint supported a claim.
