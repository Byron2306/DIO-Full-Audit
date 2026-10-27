# DIO cloud environment setup, validation, and Debian handoff

Date: 2026-10-27. This records work performed in this conversation, including failures and work still outstanding. Historical test results below describe the original setup run; they are not fresh Debian results.

## 1. Scope and present delivery

Requested repositories:

- `Byron2306/DIO-Full-Audit`, requested ref `main`.
- `Byron2306/DIO-Workflows`, requested ref `main`.

The selected baseline was Python product compilation, bounded ContractProof artifact production, portfolio and Commercial Truth projections, and the static public storefront. The large collection of historical application variants was not installed wholesale.

No application source, test, dependency declaration, or existing lockfile was changed during onboarding. Both checkouts were clean at the final original setup inspection and again after the workspace returned. The deliverable adds this report, an exact installed Python package inventory, recovered generated evidence, and an integrity inventory of that evidence.

Requested delivery branch: `codex/cloud-environment-handoff-2026-10-27`. The final chat response records whether commit and remote push actually succeeded. The existence of this document alone does not prove a push.

The user has paired their phone with Debian and intends to continue through that arrangement. No Debian access, pairing mechanism, terminal, packages, services, or network configuration has been inspected or changed by the agent.

## 2. Guidance and safeguards applied

Read the cloud-environment-onboarding setup skill, its onboarding lifecycle reference, the cloud runtime skill, and networking and Tailscale references. Used systematic debugging to investigate observed failures and verification guidance for completion checks.

- Reused the isolated task checkouts; created no Git worktree.
- Kept setup state outside repository roots where practical.
- Preserved TLS, package, and artifact verification.
- Used existing GitHub proxy authentication; requested no token.
- Did not print credential values or dump the environment.
- Did not publish, send mail, spend money, or authorize external product release.
- The later connectivity investigation made no file, service, or firewall changes.

## 3. Repository inspection

### DIO-Full-Audit

Inspected the root README, layout, Git status, `.gitignore`, `requirements-format-core.txt`, representative CI workflows, product imports, the ContractProof validator, Control Deck and Commercial Truth generators, GoldenEye routes and CLI options, and the code/test path responsible for the Commercial Truth failure.

Representative CI files read included `dio-obligation-family-phase6.yml` and `dio-product-incarnation-studio-phase16.yml`. They use Python 3.12 and packages including pytest, jsonschema, and reportlab.

Agent-instruction discovery found a nested `AGENTS.md` in `cross_folder_variants/outlook triage/A_CODE/`. No implementation work was done in that subtree.

The repository includes many legacy variants, production adapters, corpora, and generated artifacts. Repository presence was not interpreted as proof that every component runs.

### DIO-Workflows

Inspected README, static site layout, tests, scripts, and storefront/public-portfolio workflows. Read the public asset-path validator. The website has no required application build step for the static serving workflow tested here.

## 4. Original machine observations

| Item | Observed |
| --- | --- |
| Python | 3.12.14 |
| Node.js | v24.19.0 |
| uv | Available |
| Available filesystem capacity | Approximately 26 GB |
| Total memory | Approximately 33 GiB |
| Swap | None |

These describe the cloud instance, not Debian. Some storefront CI uses Node 20; local JavaScript syntax checks used the available Node 24 runtime.

## 5. Git access and checkout identity

Read-only `git ls-remote origin HEAD` succeeded for both repositories using existing platform authentication. Remote HEAD observations were:

- Full Audit: `99aeb676a49f708e4d87b88a22fffa3e9d8d29db`.
- Workflows: `63e623c5d9b6f1b4484157f8ee39a5ca6107e2d0`.

After workspace recovery, Full Audit was on local branch `work` at abbreviated commit `99aeb676a`, and Workflows local HEAD was verified as `63e623c5d9b6f1b4484157f8ee39a5ca6107e2d0`. Full Audit read access was successfully retested before this delivery. Read access alone was not treated as push authorization; the user explicitly requested the push.

No reset, source rewrite, or push to main was required.

## 6. Installed Python environment

Created `/workspace/.venvs/dio`, outside both checkouts:

```bash
python3 -m venv /workspace/.venvs/dio
/workspace/.venvs/dio/bin/python -m pip install \
  pytest jsonschema reportlab \
  -r /workspace/DIO-Full-Audit/requirements-format-core.txt
/workspace/.venvs/dio/bin/python -m pip install beautifulsoup4
/workspace/.venvs/dio/bin/python -m pip check
```

BeautifulSoup was added after the Workflows tests reported `ModuleNotFoundError: No module named 'bs4'`. After that correction, test collection succeeded. `pip check` returned `No broken requirements found.` The default pip cache was not writable, so pip disabled caching; installation succeeded without changing trust settings.

The recovered installed package inventory is saved next to this report under `cloud_environment_2026-10-27/python-requirements.freeze.txt`. It includes all 20 packages returned by `pip freeze`, including transitive dependencies. It is an environment inventory, not a new canonical application dependency declaration or a checksum lockfile.

Principal installed versions were pytest 9.1.1, jsonschema 4.26.0, reportlab 5.1.0, python-docx 1.2.0, python-pptx 1.0.2, Pillow 12.3.0, and beautifulsoup4 4.15.0.

The virtual environment itself is not committed: it contains machine-specific executables and paths. Recreate it on Debian with Debian-local paths and Python 3.12 when available. Installing this exact inventory on Debian has not been tested.

## 7. Full Audit focused test run

From `/workspace/DIO-Full-Audit`:

```bash
/workspace/.venvs/dio/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_product_compiler_phase2.py \
  tests/test_work_pattern_runtime_phase3.py \
  tests/test_obligation_engine_phase4.py \
  tests/test_contractproof_phase5.py \
  tests/test_obligation_family_phase6.py \
  tests/test_control_deck_phase9.py \
  tests/test_commercial_truth_phase10.py
```

Result: **64 passed, 1 failed**, approximately 3.99 seconds, exit code 1.

Failure: `test_commercial_truth_phase10.py::test_absence_is_unknown_not_zero_or_failure`.

The test defines `PRODUCTS` as the original four products: ContractProof, TenderProof, GrantProof, and PermitProof. It asserts that every product in the generated snapshot belongs to that set. The current Control Deck returns twelve products, including `dio_agentauthority`. `build_commercial_truth_snapshot` derives IDs from the Control Deck products, so this assertion rejects a current registered product.

This is a checked-in test/runtime expectation mismatch, not an unresolved missing dependency. No assertion was weakened, no test skipped, and no application code changed. The correct intended scope still needs a separate code-review decision.

## 8. ContractProof functional acceptance

```bash
cd /workspace/DIO-Full-Audit
/workspace/.venvs/dio/bin/python scripts/validate_contractproof_phase5.py
```

Passed with `DIO_CONTRACTPROOF_GOLDEN_READY`.

Reported checks included constitution/profile validity, deterministic compilation, capability resolution, human execution/review gates, work-pattern readiness, bounded execution, required multi-format evidence outputs and semantic sections, artifact integrity, child tamper detection, proof-manifest authority tamper detection, and internal-proof maturity boundaries.

This did not establish fulfilment, external release, legal approval, or commercial validation. Temporary files produced by this validator were not separately recovered for this handoff.

## 9. Generated portfolio and commercial evidence

```bash
cd /workspace/DIO-Full-Audit
/workspace/.venvs/dio/bin/python scripts/run_control_deck_phase9.py \
  --output /workspace/.dio-runtime/control-deck
/workspace/.venvs/dio/bin/python scripts/run_commercial_truth_phase10.py \
  --output /workspace/.dio-runtime/commercial-truth
```

Control Deck passed with `DIO_CONTROL_DECK_PORTFOLIO_OS_READY`:

- Deterministic projection: PASS.
- Twelve registered products, six suites, four META primitives.
- External release gate: REFUSE.

Commercial Truth passed with `DIO_COMMERCIAL_TRUTH_LAYER_READY`:

- Deterministic projection: PASS.
- Twelve products.
- Existing repository-derived live verified payment count: one.
- Attributed paid cases: zero.
- Economically proven products: zero.

The payment was existing evidence discovered by the projection. The agent initiated no payment and claimed no attributed revenue.

After the environment returned, both output trees survived: 72 files, approximately 860 KiB on disk. They are copied byte-for-byte under `docs/cloud_environment_2026-10-27/evidence/`, preserving nested names. These include JSON receipts, snapshots, evidence packs in JSON/HTML/DOCX/PDF, and proof manifests. The second tree contains another nested Control Deck run, so some evidence is deliberately repeated.

Original embedded absolute paths and observation timestamps are retained as historical evidence. Moving these files does not prove path-dependent integrity checks will pass from the new location, and fixed fixture timestamps must not be mistaken for wall-clock generation time. Regenerate outputs for a fresh functional validation.

The sibling `evidence-sha256.json` records the copied files' relative paths, sizes, and SHA-256 hashes. A basic credential-pattern scan of recovered output returned no matches. No credential files or runtime authentication bindings are included.

## 10. GoldenEye startup and HTTP verification

Started during setup:

```bash
cd /workspace/DIO-Full-Audit
/workspace/.venvs/dio/bin/python scripts/serve_goldeneye_portfolio.py \
  --snapshot /workspace/.dio-runtime/control-deck/CONTROL_DECK_PORTFOLIO_SNAPSHOT.json \
  --commercial-truth /workspace/.dio-runtime/commercial-truth/COMMERCIAL_TRUTH_SNAPSHOT.json
```

Used default loopback port 8766. Local requests verified:

| Route | Result |
| --- | --- |
| `/` | HTTP 200, GoldenEye text, 3,895 bytes |
| `/api/control-deck/portfolio` | HTTP 200, JSON, twelve products, 26,935 bytes |
| `/api/commercial-truth` | HTTP 200, JSON, twelve products, 12,291 bytes |

A live process or open port was not used as the sole readiness signal. No public preview was created. Process survival across workspace replacement is unknown; no stop/restart repeatability check was completed. Do not assume these processes are still running.

## 11. Workflows tests and static checks

```bash
cd /workspace/DIO-Workflows
PYTHONDONTWRITEBYTECODE=1 /workspace/.venvs/dio/bin/python \
  -m pytest -q -p no:cacheprovider tests
```

After installing BeautifulSoup: **66 passed, 2 failed**, approximately 0.43 seconds, exit code 1.

Failures:

- `test_surgical_enhancement_contract.py::test_vesper_transport_is_byte_for_byte_preserved`.
- `test_thorough_polish_contract.py::test_vesper_transport_remains_byte_identical`.

Both expected SHA-256:
`e765756ae65a78ec401e1bbcf88ceed3d782ef7c6daf4558dc9abc24f3d1b96c`.

Actual `vesper-intake.js` SHA-256:
`5fc4e3f03de8eee109ad19e596f22e56490eda48fbe6769413463d5614ef8f2a`.

`git diff --exit-code HEAD -- vesper-intake.js` showed no changes, and hashing `git show HEAD:vesper-intake.js` reproduced the actual hash. The mismatch is in checked-in content. The agent did not alter the file or expected hashes.

Additional checks passed:

```bash
python3 scripts/check_public_asset_paths.py
node --check assets/launch-v2.js
node --check vesper-intake.js
node --check products/app.js
node --check products/catalog.js
```

Asset validator token: `DIO_PUBLIC_ASSET_PATHS_VERIFIED`.

The initial combined shell invocation continued after pytest collection failed and therefore ended with a misleading overall zero status. That was not treated as a passing pytest run. The subsequent standalone test invocation reported the two failures correctly.

## 12. Static storefront startup and HTTP verification

```bash
python3 -m http.server 8080 --bind 127.0.0.1 \
  --directory /workspace/DIO-Workflows
```

Verified local HTTP 200 responses:

- `/`: 28,438 bytes, contained DIO.
- `/products/`: 4,479 bytes, contained DIO.
- `/health.txt`: three bytes, contained ok.
- `/vesper-intake.js`: 20,868 bytes.

These demonstrate static file serving, not live intake submission or production deployment. The services above were started before the later diagnostic instruction prohibiting service starts. No service was started as part of that diagnostic.

## 13. Tailscale PC investigation

User requested inspection followed by a TCP-only test of `100.113.55.14:22`, with no SSH authentication, file changes, service starts, or firewall changes.

At test time, `/etc/codex/network-policy.json` reported:

```text
version: 1
vpn_configured: false
automatic_tailscale_access: false
tcp_connect_proxy: http://proxy:8088
tcp_network_access: {"domains": [], "ip_ranges": []}
tailscale_cli_present: false
```

Tailscale runs in the managed sidecar, so lack of an executor CLI alone does not prove VPN failure. The environment API reported a connected running instance with enforced restricted HTTP policy, but that API did not prove VPN health or TCP grants.

Attempted a bounded socket connection to `proxy:8088` and, if connected, an HTTP CONNECT for `100.113.55.14:22`. The proxy connection failed before a target tunnel was established:

```text
ConnectionRefusedError: [Errno 111] Connection refused
```

Repeated the same proxy connectivity check using the normal escalated execution path to distinguish sandbox restrictions. It returned exactly the same error.

No explicit network-policy denial was returned. The refusal was at the proxy endpoint; it does not establish whether Debian's port 22 is open. No SSH protocol identification or authentication was sent. No VPN client was installed and no route, firewall, file, or service was changed.

For that managed-cloud route, configured VPN access and a TCP grant covering `100.113.55.14/32` would be prerequisites. They were not added during the test. The paired phone-to-Debian route is a separate arrangement and has not been tested here.

## 14. Workspace outage and recovery

The environment later became unavailable. An attempted shell read returned `No usable execution environment is available`. The status API described an offline instance in starting phase at configuration revision 4, with VPN capability metadata and `failure: null`. That null value did not establish VPN health. The wait tool then reported the environment was neither ready nor starting.

At that point no branch, commit, report file, or push could be created; a detailed inline Markdown handoff was supplied in chat instead.

The workspace was subsequently reattached. A new `git ls-remote origin HEAD` succeeded for Full Audit. The user again explicitly requested pushing the Markdown and all other work. The virtual environment and generated output directories were recovered, and the working trees were clean before adding these handoff deliverables.

## 15. Optional or unverified capabilities

Not installed or exercised as part of the selected baseline:

- Ollama and Granite models.
- Pocket TTS, voice assets, and its server.
- Piper and voice downloads.
- edge-tts narration and full ffmpeg campaign rendering.
- Every historical variant, adapter, or production service.
- Live Outlook/Microsoft Graph, live intake submission, payment operations, mail sending, external deployment, publication, or media spend.
- Complete phase 0–16.1 chain, the entire Full Audit suite, or browser-based visual validation.
- Debian toolchain, SSH, phone transport, and Tailscale connectivity after later configuration changes.

No fresh tests were silently substituted for the recorded historical runs. The three diagnosed failing assertions remain unresolved.

## 16. Reusable cloud configuration status

No `install_script` or `start_skill` draft was saved during the original session. No environment publication or fresh-task snapshot restoration was verified. The task changed to connectivity diagnosis before that step, then to repository delivery and Debian handoff.

If managed-cloud onboarding is resumed, save tested complete installation instructions and service startup/readiness instructions through the configuration tool. Installation state is distinct from live processes. Reuse task checkouts and do not create worktrees unless explicitly requested. Test startup repeatability and separately verify a new task's restoration. This report and package inventory do not themselves publish or complete cloud onboarding.

## 17. Remaining work in recommended order

1. Verify the requested branch push and remote commit; report the branch URL in chat.
2. On the phone/Debian arrangement, establish which terminal or remote-control mechanism is available. Pairing alone does not prove command execution, SSH, Tailscale, file transfer, or dashboard access.
3. Inspect Debian repositories and preserve any local changes; record Python/Node versions, disk, memory, and existing environments.
4. Fetch the handoff branch and inspect this report and evidence. Avoid copying machine-specific cloud virtual environments.
5. Create a Debian-local Python environment and install the baseline dependencies. Use Python 3.12 where practical; check compatibility if another version is chosen. Keep verification enabled.
6. Run `pip check`, the recorded focused tests, ContractProof acceptance, Control Deck and Commercial Truth generation, and static-site checks. Record Debian results independently.
7. Start local dashboards when needed, regenerate current projections, and make representative HTTP requests. Verify phone access through the actual chosen transport. Do not expose operator dashboards broadly by assumption.
8. Review the Commercial Truth four-product test assumption against the twelve-product registry. Decide the correct contract before changing tests or implementation.
9. Investigate the intended Vesper transport revision and the two stale expected hashes before updating either source or assertions. Rerun affected tests after a reviewed correction.
10. Add optional speech, model, campaign-rendering, or external integration dependencies only for a concrete selected workflow.
11. If cloud access is still desired, separately resolve VPN/TCP policy and retest transport without authentication first; then complete reusable environment configuration and publication.

## 18. Final evidence matrix

| Capability | Recorded outcome |
| --- | --- |
| Full Audit focused tests | 64 passed, 1 failed |
| Workflows full tests directory | 66 passed, 2 failed |
| ContractProof functional acceptance | Passed |
| Control Deck generation | Passed |
| Commercial Truth generation | Passed |
| GoldenEye root and two APIs | HTTP checks passed |
| Static storefront representative routes | HTTP checks passed |
| Public asset paths and four JS syntax checks | Passed |
| Python dependency consistency | Passed |
| Original application source preservation | Both checkouts clean |
| Tailscale PC port 22 | Unverified; proxy refused twice |
| SSH authentication | Never attempted |
| Debian/phone operation | User reports pairing; agent has not tested |
| Saved cloud scripts/publication | Not completed |
| Generated evidence recovery | 72 files recovered for this delivery |

This handoff distinguishes local development checks, repository defects, cloud configuration, external access, and user-reported Debian pairing. None implies the others.
