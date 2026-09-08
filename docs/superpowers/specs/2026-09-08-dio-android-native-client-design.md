# DIO Android Native Client Design

**Date:** 2026-09-08  
**Branch:** `agent/dio-android-native-client`  
**Status:** Design for review  
**Base:** `agent/dio-control-deck-68-productgrade` at `2d99f1b0ba68761b0cf7e1dfce9eee5575786ee8`

## Goal

Build a real installable Android application that gives the phone the same live DIO data and governed work surfaces as the Debian laptop without duplicating DIO state, weakening the localhost-only service boundary, or requiring Termux, Chrome, or a manual SSH command.

The Android application is a second operator console for the same DIO organism. Debian remains the runtime host and source of truth.

## Core invariant

There is exactly one DIO truth plane.

The Android application does not contain its own portfolio database, canon list, market state, GoldenEye state, production state, or evidence receipts. It reads the same live services that the laptop reads.

The verified portfolio display remains derived from the runtime truth contract. The historical 53-product anchor is never mutated or copied into Android as an alternate authority. Android may display `53 + 15 = 68` only when the backend portfolio/launcher state reports the verified 68-product condition.

## Recommended architecture

### 1. Native Android shell

Create a Kotlin Android application under `android/dio-mobile/` using Jetpack Compose for the native shell.

The native home screen provides:

- DIO brand/header
- connection state
- portfolio truth state
- four application cards: GoldenEye, Control Deck, Market Command, Production Studio
- settings/setup access
- disconnect/reconnect controls

The application is a real APK with its own launcher icon and process. It does not launch Chrome or depend on the PWA for operation.

### 2. Embedded SSH transport

The APK owns the secure connection to Debian.

A maintained Java SSH implementation is embedded in the Android application and used only for authenticated SSH transport and local TCP forwarding. The application does not expose an interactive shell and does not execute arbitrary remote commands.

Once authenticated, the app creates these exact Android-loopback forwards:

| Android loopback | Debian target | Surface |
| --- | --- | --- |
| `127.0.0.1:8764` | `127.0.0.1:8764` | DIO launcher/state |
| `127.0.0.1:8765` | `127.0.0.1:8765` | Control Deck / Production Studio |
| `127.0.0.1:8766` | `127.0.0.1:8766` | GoldenEye |
| `127.0.0.1:8770` | `127.0.0.1:8770` | Market Command |

This preserves the existing service design: the Debian services remain bound to localhost and do not need to listen on the LAN or public internet.

All four forwards are mandatory. If any required forward cannot be established, DIO Mobile is not READY.

### 3. App-specific SSH identity

DIO Mobile generates its own SSH keypair during first-run setup.

The private key is never committed to the repository, never bundled in the APK, and never transmitted as application telemetry. It is stored only in app-private storage encrypted by a key held in Android Keystore.

The setup screen displays the public key and a bounded Debian authorization instruction so the operator can add that key to the Debian user's `authorized_keys` once.

V1 uses key authentication only. Password storage is out of scope.

### 4. Host identity pinning

The app uses strict SSH host-key verification.

On first connection, DIO Mobile shows the Debian SSH host fingerprint and requires explicit operator acceptance before storing the fingerprint. Subsequent connections must match the pinned fingerprint. A changed host key causes a hard refusal until the operator deliberately resets the pinned host identity.

No `StrictHostKeyChecking=no` equivalent is permitted.

### 5. Foreground connection service

The SSH session and port forwards run in an Android foreground service while DIO Mobile is connected.

This provides:

- resilience when the user switches between DIO surfaces
- keepalive handling
- controlled reconnect attempts
- a visible Android notification while the tunnel is active
- clean shutdown when the operator disconnects

The foreground service has no DIO execution authority. It only maintains transport.

### 6. Same surfaces, embedded in the APK

After the tunnel is healthy, the app opens the existing DIO surfaces inside allowlisted Android WebViews:

- GoldenEye: `http://127.0.0.1:8766/`
- Control Deck: `http://127.0.0.1:8765/`
- Market Command: `http://127.0.0.1:8770/`
- Production Studio: `http://127.0.0.1:8765/dashboard/production.html`

This deliberately reuses the mature laptop interfaces instead of reimplementing four complex products in native Android UI.

The WebView is not a general browser. Navigation is allowlisted to the four loopback ports and DIO paths. External links may be handed to the Android system browser only after an explicit user action. Unexpected non-loopback navigation is blocked.

The app does not inject JavaScript that bypasses existing confirmation gates or changes server-side authority.

### 7. Native truth header

The native home screen reads:

`http://127.0.0.1:8764/api/launcher/state`

through the embedded SSH tunnel.

It uses this state for:

- global READY / HELD / DISCONNECTED state
- four-surface readiness
- verified portfolio truth
- base / extension / total counts
- generated-at timestamp

The Android client never synthesizes a successful truth state from local constants.

## Data flow

```text
DIO Android APK
    |
    | SSH key authentication + host-key pinning
    v
Debian sshd
    |
    | local TCP forwards only
    +--> 127.0.0.1:8764 DIO launcher/state
    +--> 127.0.0.1:8765 Control Deck + Production Studio
    +--> 127.0.0.1:8766 GoldenEye
    +--> 127.0.0.1:8770 Market Command

Android native Home
    +--> /api/launcher/state

Android embedded WebViews
    +--> exact existing DIO surfaces
```

## Connection states

DIO Mobile has five explicit transport states:

1. `UNCONFIGURED` - no Debian connection profile exists
2. `CONNECTING` - SSH transport or forwards are being established
3. `CONNECTED_HELD` - SSH is up but one or more DIO surfaces or the portfolio truth gate is not ready
4. `READY` - all four surfaces are ready and the launcher portfolio gate is verified
5. `DISCONNECTED` - transport is unavailable or failed after configuration

`READY` is impossible unless the live launcher state says ready.

## Fail-closed behavior

If SSH disconnects, host verification fails, a local forward dies, `/api/launcher/state` becomes unreachable, or the response is invalid:

- native READY state is cleared immediately
- cached portfolio counts are not presented as current truth
- all surface cards become unavailable
- embedded WebViews are closed or replaced by the disconnected surface
- no stale `VERIFIED` badge survives the disconnect
- automatic reconnect may retry transport, but it cannot restore READY until fresh launcher state verifies it

## Caching policy

Truth is live, not offline-first.

The native launcher-state client uses no-store/no-cache semantics. The app does not persist the last successful portfolio truth as an authoritative offline state.

WebViews prefer live content. DIO API responses must not be treated as offline truth. Static rendering assets may be cached by Android/WebView where harmless, but disconnect always clears the app's native readiness and truth display.

## Cleartext loopback boundary

The existing DIO HTTP services use loopback HTTP. Android therefore needs permission to load cleartext content on device loopback after the SSH forwards are established.

This permission is bounded by application policy:

- only `127.0.0.1` DIO ports are valid internal surface destinations
- SSH encrypts traffic before it leaves the phone
- the Debian targets remain localhost-only
- the WebView navigation delegate refuses unapproved network destinations

No new public HTTP listener is introduced.

## First-run UX

### Screen 1: Connect DIO

Fields:

- Debian host or private reachable IP/name
- SSH port, default 22
- SSH user, default `byron`

Action: **Create DIO Mobile identity**

### Screen 2: Authorize this phone

The app displays:

- generated public key
- copy button
- Debian authorization command/instructions
- Debian host fingerprint on first attempted connection

The operator authorizes the app-specific key once.

### Screen 3: DIO Home

After successful transport, DIO Mobile shows the live portfolio truth and four surfaces.

Daily use becomes:

`Tap DIO -> reconnect automatically -> live DIO Home -> open a surface`

No Termux or manual tunnel command is part of daily operation.

## Remote-away-from-home behavior

The Android app's SSH transport requires the configured Debian SSH endpoint to be reachable.

V1 does not open Debian SSH or DIO services to the public internet automatically. It works immediately on networks where the configured SSH endpoint is reachable, such as the same LAN or an existing private VPN/overlay address.

A later networking phase may add a first-class private overlay/VPN setup, but that is deliberately separated from the Android client so secure transport topology can evolve without changing DIO truth or the application surfaces.

## Authority boundary

The Android client creates no new DIO business authority.

It may display and interact with the same governed interfaces available on the laptop. Any production, sending, publishing, payment, release, promotion, evidence, or approval action continues to be controlled by the server-side DIO rules and explicit confirmation gates already present in those surfaces.

The SSH layer itself cannot run commands. It is port-forwarding transport only.

## Repository structure

Planned top-level layout:

```text
android/dio-mobile/
  app/
    src/main/
    src/test/
    src/androidTest/
  gradle/
  build.gradle.kts
  settings.gradle.kts
  gradlew
  gradlew.bat

.github/workflows/dio-android.yml

docs/superpowers/specs/2026-09-08-dio-android-native-client-design.md
```

Existing DIO Python services remain in their current locations.

## Build and packaging

GitHub Actions builds the Android application so the Debian laptop does not need Android Studio for normal CI.

V1 CI produces an installable debug-signed APK artifact for device testing.

A stable release-signed APK requires one persistent release keystore. That keystore must remain outside git and be provided to CI through protected repository secrets or used in a controlled local release build. A new signing key must not be generated for every release because Android updates require signature continuity.

## Test strategy

Implementation follows TDD.

### Android unit contracts

Tests must cover at least:

- exact four-forward plan: 8764, 8765, 8766, 8770
- all local forwards bind to `127.0.0.1`
- failure of any forward prevents READY
- launcher state is the only source for verified portfolio display
- disconnect clears prior READY/VERIFIED state
- host-key mismatch refuses the connection
- private-key material is never stored as plaintext preferences
- WebView navigation allowlist accepts only bounded DIO loopback destinations
- external/unexpected navigation is refused or handed off deliberately

### Android instrumentation contracts

Tests cover:

- Compose Home renders disconnected/held/ready states correctly
- surface navigation opens the intended embedded WebView
- back navigation returns to DIO Home rather than exiting unpredictably
- WebView cannot navigate to an arbitrary HTTP host

### Repository integration contracts

Python-side tests assert that the expected DIO services remain localhost-only and the Android client forward map stays aligned with the canonical ports.

### CI gates

The Android workflow must run:

- Gradle unit tests
- Android lint
- debug APK assembly
- artifact upload only after test/build success

The Android branch must not weaken or bypass the existing portfolio/canon verification workflows.

## V1 success criteria

V1 is accepted when all of the following are true:

1. A GitHub Actions artifact provides an installable DIO Android APK.
2. The app launches from its own Android icon without Chrome or Termux.
3. First-run setup creates an app-specific SSH identity and stores it encrypted at rest.
4. The app pins and verifies the Debian SSH host key.
5. One tap can establish the four loopback forwards after initial configuration.
6. The native Home reads live DIO launcher state and never hardcodes READY or 68-product verification.
7. GoldenEye, Control Deck, Market Command, and Production Studio open inside the APK using the same Debian-hosted surfaces and data as the laptop.
8. Disconnect immediately removes live-ready and verified truth presentation.
9. Debian DIO services remain localhost-only.
10. No SSH private key, password, token, or release signing key is committed to git.

## Non-goals for V1

- porting the DIO Python organism to Android
- duplicating DIO databases or receipts onto the phone
- rebuilding all four work surfaces in native Compose
- public internet exposure of DIO HTTP services
- arbitrary remote shell execution
- password-based credential storage
- Play Store publication
- background DIO execution on the phone when Debian is off

## Follow-on phases

After V1 is stable, later phases may add:

- private overlay/VPN onboarding for reliable remote access away from home
- Android notifications for GoldenEye events and `NEEDS_YOU` gates
- native Android views for high-value summary screens while retaining server truth
- biometric unlock for DIO connection credentials
- release signing automation and optional Play Store/internal distribution

These are additive and do not change the V1 source-of-truth model.
