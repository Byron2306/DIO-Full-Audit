# DIO Android Native Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an installable Android APK that connects to the existing Debian-hosted DIO organism, reads the same live portfolio truth, and embeds GoldenEye, Control Deck, Market Command, and Production Studio without Chrome, Termux, public DIO listeners, or a second source of truth.

**Architecture:** A Kotlin/Jetpack Compose Android shell owns a bounded SSH session to Debian and establishes four loopback-only local port forwards. The native home screen reads `/api/launcher/state` over the tunnel, while allowlisted WebViews render the existing four DIO surfaces. Android never hardcodes portfolio readiness or 68-product truth, and disconnects clear all live-ready/verified presentation.

**Tech Stack:** Android Gradle Plugin 9.4.0; Gradle 9.6.0; JDK 17; Kotlin via AGP built-in Kotlin; compileSdk 37; targetSdk 36; minSdk 26; Jetpack Compose BOM 2026.08.00; Material3 1.4.0; Activity Compose 1.13.0; SSHJ 0.40.0; Android Keystore AES-256-GCM; `HttpURLConnection` for loopback launcher-state reads; GitHub Actions for CI/APK artifacts.

**Spec:** `docs/superpowers/specs/2026-09-08-dio-android-native-client-design.md`

## Global Constraints

- Debian remains the runtime host and only DIO truth plane.
- Historical portfolio anchor remains immutable at 53; Android never stores or derives an independent canon.
- Android may display `53 + 15 = 68` as verified only when live launcher state reports that verified condition.
- Debian DIO services remain bound to localhost; no DIO HTTP service may be changed to `0.0.0.0`.
- Android owns SSH port forwarding only; no interactive shell, arbitrary remote command execution, or password credential storage is permitted.
- Required Android-loopback forwards are exactly 8764, 8765, 8766, and 8770, all bound to `127.0.0.1`.
- Host identity is pinned. No permissive host-key verifier is permitted.
- Private SSH key material is never committed, bundled in the APK, logged, or stored as plaintext preferences.
- Disconnect, invalid launcher state, host-key mismatch, or forward failure must clear READY/VERIFIED presentation immediately.
- WebView internal navigation is allowlisted to the bounded DIO loopback origins and paths only.
- V1 build output is a debug-signed installable APK artifact from CI; release signing remains separate.

---

## File Structure

Create the Android project under `android/dio-mobile/` with responsibility-focused files:

- `android/dio-mobile/settings.gradle.kts` — project/repository setup.
- `android/dio-mobile/build.gradle.kts` — AGP plugin declaration.
- `android/dio-mobile/gradle.properties` — deterministic Gradle/Android flags.
- `android/dio-mobile/gradle/wrapper/gradle-wrapper.properties` — Gradle 9.6.0 pin.
- `android/dio-mobile/app/build.gradle.kts` — Android config and dependencies.
- `android/dio-mobile/app/src/main/AndroidManifest.xml` — app/foreground-service/network permissions.
- `android/dio-mobile/app/src/main/res/xml/network_security_config.xml` — cleartext allowance bounded to loopback use by app policy.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/model/DioModels.kt` — connection/truth/surface data models.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/truth/LauncherStateParser.kt` — strict live launcher-state parsing.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/truth/DioReadinessReducer.kt` — fail-closed READY derivation.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/security/SecureIdentityStore.kt` — Android Keystore wrapping and SSH identity persistence.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ssh/HostKeyPinStore.kt` — pinned host fingerprint state.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ssh/DioForwardPlan.kt` — canonical four-forward map.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ssh/DioSshTransport.kt` — SSHJ connection/authentication/forward lifecycle.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/service/DioConnectionService.kt` — Android foreground service maintaining transport.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/truth/LauncherStateClient.kt` — no-cache loopback state fetch.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/repository/DioRepository.kt` — single observable app state.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/web/DioNavigationPolicy.kt` — WebView allowlist.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ui/DioHomeScreen.kt` — native DIO home.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ui/DioSurfaceScreen.kt` — embedded bounded WebView.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ui/SetupScreen.kt` — first-run host/user/key authorization UI.
- `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/MainActivity.kt` — activity-level routing/wiring.
- `android/dio-mobile/app/src/test/...` — unit contracts.
- `android/dio-mobile/app/src/androidTest/...` — Compose/WebView instrumentation contracts.
- `tests/test_dio_android_contract.py` — repository-side static boundary assertions.
- `.github/workflows/dio-android.yml` — Android test/lint/APK artifact workflow.

---

### Task 1: Scaffold a deterministic Android application build

**Files:**
- Create: `android/dio-mobile/settings.gradle.kts`
- Create: `android/dio-mobile/build.gradle.kts`
- Create: `android/dio-mobile/gradle.properties`
- Create: `android/dio-mobile/gradle/wrapper/gradle-wrapper.properties`
- Create: `android/dio-mobile/gradlew`
- Create: `android/dio-mobile/gradlew.bat`
- Create: `android/dio-mobile/app/build.gradle.kts`
- Create: `android/dio-mobile/app/src/main/AndroidManifest.xml`
- Create: `android/dio-mobile/app/src/main/res/values/strings.xml`
- Create: `android/dio-mobile/app/src/main/res/values/themes.xml`
- Test: `tests/test_dio_android_contract.py`

**Interfaces:**
- Consumes: repository branch `agent/dio-android-native-client`.
- Produces: an Android application module with package/namespace `za.co.dioworkflows.mobile`, `minSdk=26`, `targetSdk=36`, `compileSdk=37`.

- [ ] **Step 1: Write the failing repository contract test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "dio-mobile"


def test_android_project_is_pinned_and_dio_scoped():
    app = (ANDROID / "app" / "build.gradle.kts").read_text()
    wrapper = (ANDROID / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text()
    root_build = (ANDROID / "build.gradle.kts").read_text()
    assert 'id("com.android.application") version "9.4.0" apply false' in root_build
    assert "compileSdk = 37" in app
    assert "minSdk = 26" in app
    assert "targetSdk = 36" in app
    assert 'namespace = "za.co.dioworkflows.mobile"' in app
    assert "gradle-9.6.0-bin.zip" in wrapper
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest -q tests/test_dio_android_contract.py::test_android_project_is_pinned_and_dio_scoped
```

Expected: FAIL because the Android project files do not yet exist.

- [ ] **Step 3: Add the minimal Gradle project**

`android/dio-mobile/build.gradle.kts`:

```kotlin
plugins {
    id("com.android.application") version "9.4.0" apply false
}
```

`android/dio-mobile/settings.gradle.kts`:

```kotlin
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "DioMobile"
include(":app")
```

`android/dio-mobile/app/build.gradle.kts` must include:

```kotlin
plugins { id("com.android.application") }

android {
    namespace = "za.co.dioworkflows.mobile"
    compileSdk = 37
    defaultConfig {
        applicationId = "za.co.dioworkflows.mobile"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildFeatures { compose = true }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("com.hierynomus:sshj:0.40.0")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
```

Use JDK 17 source/target compatibility and AGP built-in Kotlin. Do not add a dynamic dependency version.

- [ ] **Step 4: Re-run the repository contract**

Run:

```bash
python -m pytest -q tests/test_dio_android_contract.py::test_android_project_is_pinned_and_dio_scoped
```

Expected: PASS.

- [ ] **Step 5: Run the first Android build**

Run from `android/dio-mobile`:

```bash
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

Expected: BUILD SUCCESSFUL and `app/build/outputs/apk/debug/app-debug.apk` exists.

- [ ] **Step 6: Commit**

```bash
git add android/dio-mobile tests/test_dio_android_contract.py
git commit -m "build: scaffold native DIO Android client"
```

---

### Task 2: Define DIO mobile truth models and fail-closed readiness

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/model/DioModels.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/truth/LauncherStateParser.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/truth/DioReadinessReducer.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/truth/DioReadinessReducerTest.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/truth/LauncherStateParserTest.kt`

**Interfaces:**
- Produces: `ConnectionPhase`, `PortfolioTruth`, `SurfaceStatus`, `DioAppState`, `LauncherSnapshot`, `LauncherStateParser.parse(String): LauncherSnapshot`, and `DioReadinessReducer.reduce(transportConnected: Boolean, snapshot: LauncherSnapshot?): DioAppState`.

- [ ] **Step 1: Write RED tests for truth derivation**

```kotlin
@Test fun verified68RequiresLiveBackendProof() {
    val snapshot = LauncherSnapshot(
        launcherReady = true,
        baseCount = 53,
        extensionCount = 15,
        totalCount = 68,
        extensionVerified = true,
        surfaces = requiredReadySurfaces(),
        generatedAt = "2026-09-08T04:00:00Z",
    )
    val state = DioReadinessReducer.reduce(true, snapshot)
    assertEquals(ConnectionPhase.READY, state.phase)
    assertEquals(PortfolioTruth(53, 15, 68, true), state.portfolio)
}

@Test fun staleVerifiedStateIsClearedOnDisconnect() {
    val state = DioReadinessReducer.reduce(false, previouslyVerifiedSnapshot())
    assertEquals(ConnectionPhase.DISCONNECTED, state.phase)
    assertNull(state.portfolio)
    assertTrue(state.surfaces.all { !it.ready })
}

@Test fun wrongArithmeticCannotBecomeReady() {
    val state = DioReadinessReducer.reduce(true, verifiedSnapshot(totalCount = 67))
    assertEquals(ConnectionPhase.CONNECTED_HELD, state.phase)
    assertNull(state.portfolio)
}
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
./gradlew :app:testDebugUnitTest --tests '*DioReadinessReducerTest' --tests '*LauncherStateParserTest'
```

Expected: FAIL because models/parser/reducer are absent.

- [ ] **Step 3: Implement minimal fail-closed models/parser/reducer**

The reducer must enforce:

```kotlin
val verified68 = snapshot != null &&
    snapshot.launcherReady &&
    snapshot.baseCount == 53 &&
    snapshot.extensionCount == 15 &&
    snapshot.totalCount == snapshot.baseCount + snapshot.extensionCount &&
    snapshot.totalCount == 68 &&
    snapshot.extensionVerified &&
    REQUIRED_SURFACES.all { id -> snapshot.surfaces[id]?.ready == true }
```

If `verified68` is false, return `CONNECTED_HELD` with no verified `PortfolioTruth`. If transport is disconnected, return `DISCONNECTED` and clear all surface readiness.

`LauncherStateParser` must reject absent/non-numeric counts, missing required surfaces, malformed JSON, and responses that claim READY while failing arithmetic.

- [ ] **Step 4: Re-run unit tests**

```bash
./gradlew :app:testDebugUnitTest --tests '*DioReadinessReducerTest' --tests '*LauncherStateParserTest'
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/dio-mobile/app/src/main/java android/dio-mobile/app/src/test
git commit -m "feat: enforce live DIO truth in Android state"
```

---

### Task 3: Add canonical forward planning and strict WebView navigation policy

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ssh/DioForwardPlan.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/web/DioNavigationPolicy.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/ssh/DioForwardPlanTest.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/web/DioNavigationPolicyTest.kt`
- Modify: `tests/test_dio_android_contract.py`

**Interfaces:**
- Produces: `ForwardSpec(localHost, localPort, remoteHost, remotePort)`, `DioForwardPlan.REQUIRED`, `DioNavigationPolicy.isInternal(Uri): Boolean`, and `DioNavigationPolicy.surfaceUrl(SurfaceId): String`.

- [ ] **Step 1: Write RED tests for exact transport/navigation boundaries**

```kotlin
@Test fun forwardPlanIsExactlyFourLoopbackMappings() {
    assertEquals(
        listOf(8764, 8765, 8766, 8770),
        DioForwardPlan.REQUIRED.map { it.localPort }
    )
    assertTrue(DioForwardPlan.REQUIRED.all {
        it.localHost == "127.0.0.1" && it.remoteHost == "127.0.0.1" && it.localPort == it.remotePort
    })
}

@Test fun arbitraryHostsAreNeverInternal() {
    assertFalse(DioNavigationPolicy.isInternal(Uri.parse("http://192.168.1.20:8765/")))
    assertFalse(DioNavigationPolicy.isInternal(Uri.parse("https://example.com/")))
}

@Test fun productionStudioUsesTheCanonicalBusinessPort() {
    assertTrue(DioNavigationPolicy.isInternal(Uri.parse("http://127.0.0.1:8765/dashboard/production.html")))
}
```

- [ ] **Step 2: Verify RED**

```bash
./gradlew :app:testDebugUnitTest --tests '*DioForwardPlanTest' --tests '*DioNavigationPolicyTest'
```

Expected: FAIL because policies are absent.

- [ ] **Step 3: Implement the bounded constants**

```kotlin
object DioForwardPlan {
    val REQUIRED = listOf(
        ForwardSpec("127.0.0.1", 8764, "127.0.0.1", 8764),
        ForwardSpec("127.0.0.1", 8765, "127.0.0.1", 8765),
        ForwardSpec("127.0.0.1", 8766, "127.0.0.1", 8766),
        ForwardSpec("127.0.0.1", 8770, "127.0.0.1", 8770),
    )
}
```

Allow internal WebView navigation only when scheme is `http`, host is exactly `127.0.0.1`, and port/path match the four DIO surfaces. Do not treat `localhost`, LAN IPs, arbitrary loopback ports, or arbitrary HTTP destinations as internal.

- [ ] **Step 4: Add Python static contract against service drift**

```python
def test_android_forward_plan_matches_canonical_dio_ports():
    forward_plan = (ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/ssh/DioForwardPlan.kt").read_text()
    for port in (8764, 8765, 8766, 8770):
        assert str(port) in forward_plan
    assert '"0.0.0.0"' not in forward_plan
```

- [ ] **Step 5: Verify GREEN**

```bash
./gradlew :app:testDebugUnitTest --tests '*DioForwardPlanTest' --tests '*DioNavigationPolicyTest'
python -m pytest -q tests/test_dio_android_contract.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android/dio-mobile/app/src tests/test_dio_android_contract.py
git commit -m "feat: bound DIO Android transport and navigation"
```

---

### Task 4: Create encrypted app-specific SSH identity storage

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/security/SecureIdentityStore.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/security/SecureIdentityStoreContractTest.kt`
- Modify: `tests/test_dio_android_contract.py`

**Interfaces:**
- Produces: `SecureIdentityStore.createIdentity(): PublicIdentity`, `loadPrivateKeyBytes(): ByteArray`, `clearIdentity()`, and `PublicIdentity(openSshPublicKey: String, fingerprint: String)`.

- [ ] **Step 1: Write RED static/security tests**

```python
def test_private_key_storage_is_keystore_wrapped_and_not_plain_preferences():
    text = (ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/security/SecureIdentityStore.kt").read_text()
    assert "AndroidKeyStore" in text
    assert "AES/GCM/NoPadding" in text
    assert "256" in text
    assert "putString(\"private" not in text
    assert "putString(\"ssh_private" not in text
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_dio_android_contract.py::test_private_key_storage_is_keystore_wrapped_and_not_plain_preferences
```

Expected: FAIL because the identity store does not exist.

- [ ] **Step 3: Implement encrypted-at-rest identity storage**

Create an AES wrapping key in `AndroidKeyStore`:

```kotlin
val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
keyGenerator.init(
    KeyGenParameterSpec.Builder(
        "dio-mobile-ssh-wrap-v1",
        KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
    )
        .setKeySize(256)
        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
        .build()
)
```

Persist only `ciphertext + IV + public key + non-secret metadata` in app-private storage. Generate the SSH keypair locally using SSHJ-supported key material; wipe temporary private-key byte arrays after import/use where practical. Never log key bytes.

- [ ] **Step 4: Verify GREEN**

```bash
python -m pytest -q tests/test_dio_android_contract.py
./gradlew :app:testDebugUnitTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/dio-mobile/app/src tests/test_dio_android_contract.py
git commit -m "feat: secure DIO Mobile SSH identity"
```

---

### Task 5: Implement strict host-key pinning and SSHJ forwarding transport

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ssh/HostKeyPinStore.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ssh/DioSshTransport.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/ssh/HostKeyPinStoreTest.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/ssh/DioSshTransportPolicyTest.kt`
- Modify: `tests/test_dio_android_contract.py`

**Interfaces:**
- Consumes: `SecureIdentityStore`, `DioForwardPlan.REQUIRED`.
- Produces: `DioSshTransport.connect(profile, onUntrustedFingerprint): TransportSession`, `TransportSession.isHealthy(): Boolean`, `TransportSession.close()`.

- [ ] **Step 1: Write RED tests for pinning and forbidden permissive verification**

```kotlin
@Test fun changedFingerprintIsRejected() {
    val pins = FakePinStore(existing = "SHA256:AAA")
    assertFalse(pins.accepts("host", 22, "SHA256:BBB"))
}

@Test fun missingRequiredForwardPreventsHealthySession() {
    val health = ForwardHealth(required = DioForwardPlan.REQUIRED, activePorts = setOf(8764, 8765, 8766))
    assertFalse(health.allRequiredActive)
}
```

Python static assertion:

```python
def test_android_ssh_transport_never_uses_promiscuous_host_verification():
    text = (ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/ssh/DioSshTransport.kt").read_text()
    assert "PromiscuousVerifier" not in text
    assert "StrictHostKeyChecking=no" not in text
```

- [ ] **Step 2: Verify RED**

```bash
./gradlew :app:testDebugUnitTest --tests '*HostKeyPinStoreTest' --tests '*DioSshTransportPolicyTest'
python -m pytest -q tests/test_dio_android_contract.py
```

Expected: FAIL because transport/pinning are absent.

- [ ] **Step 3: Implement host verification before authentication**

Use SSHJ `HostKeyVerifier` or a stored SHA-256 fingerprint through `SSHClient.addHostKeyVerifier(...)`. For first contact, surface the observed SHA-256 fingerprint through `onUntrustedFingerprint` and abort the connection. Only a subsequent explicit operator acceptance writes the pin and allows connection. Never accept the first key silently.

- [ ] **Step 4: Implement SSH public-key auth and four local forwarders**

For each `ForwardSpec`, create an SSHJ local port forwarder bound to `InetSocketAddress("127.0.0.1", localPort)` and targeting `HostPort("127.0.0.1", remotePort)`. Run each listener on a dedicated managed executor thread. The session is healthy only after all four listeners are active.

Do not call `startSession()`, `startShell()`, `exec()`, SCP, or SFTP anywhere in `DioSshTransport`.

- [ ] **Step 5: Verify GREEN**

```bash
./gradlew :app:testDebugUnitTest --tests '*HostKeyPinStoreTest' --tests '*DioSshTransportPolicyTest'
python -m pytest -q tests/test_dio_android_contract.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android/dio-mobile/app/src tests/test_dio_android_contract.py
git commit -m "feat: add pinned SSH transport for DIO Mobile"
```

---

### Task 6: Add live no-cache launcher-state client and repository

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/truth/LauncherStateClient.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/repository/DioRepository.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/truth/LauncherStateClientContractTest.kt`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/repository/DioRepositoryTest.kt`

**Interfaces:**
- Consumes: `LauncherStateParser`, `DioReadinessReducer`.
- Produces: `LauncherStateClient.fetch(): LauncherSnapshot`; `DioRepository.state: StateFlow<DioAppState>`; `refreshTruth()`; `transportDisconnected()`.

- [ ] **Step 1: Write RED tests for no-cache and stale-state clearing**

```kotlin
@Test fun disconnectImmediatelyClearsVerifiedTruth() = runTest {
    val repo = DioRepository(fakeClient, fakeTransport)
    repo.acceptFreshSnapshot(verifiedSnapshot())
    assertEquals(ConnectionPhase.READY, repo.state.value.phase)
    repo.transportDisconnected()
    assertEquals(ConnectionPhase.DISCONNECTED, repo.state.value.phase)
    assertNull(repo.state.value.portfolio)
}
```

- [ ] **Step 2: Verify RED**

```bash
./gradlew :app:testDebugUnitTest --tests '*LauncherStateClientContractTest' --tests '*DioRepositoryTest'
```

Expected: FAIL because client/repository are absent.

- [ ] **Step 3: Implement loopback launcher-state fetch**

Use exactly:

```kotlin
val url = URL("http://127.0.0.1:8764/api/launcher/state")
val connection = (url.openConnection() as HttpURLConnection).apply {
    requestMethod = "GET"
    connectTimeout = 3_000
    readTimeout = 3_000
    useCaches = false
    setRequestProperty("Cache-Control", "no-store, no-cache, max-age=0")
    setRequestProperty("Pragma", "no-cache")
}
```

Only HTTP 200 with strictly valid JSON is accepted. All exceptions/errors map to held/disconnected state and must not preserve old portfolio truth.

- [ ] **Step 4: Verify GREEN**

```bash
./gradlew :app:testDebugUnitTest --tests '*LauncherStateClientContractTest' --tests '*DioRepositoryTest'
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/dio-mobile/app/src
git commit -m "feat: read live DIO launcher truth on Android"
```

---

### Task 7: Run SSH lifecycle in an Android foreground service

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/service/DioConnectionService.kt`
- Modify: `android/dio-mobile/app/src/main/AndroidManifest.xml`
- Test: `android/dio-mobile/app/src/test/java/za/co/dioworkflows/mobile/service/DioConnectionServicePolicyTest.kt`

**Interfaces:**
- Consumes: `DioSshTransport`, `DioRepository`.
- Produces: service actions `ACTION_CONNECT`, `ACTION_DISCONNECT`, notification channel `dio_connection`, and a single owned `TransportSession`.

- [ ] **Step 1: Write RED lifecycle policy tests**

```kotlin
@Test fun losingTransportPublishesDisconnectedBeforeRetry() {
    val state = ConnectionFailurePolicy.onTransportLost(previous = readyState())
    assertEquals(ConnectionPhase.DISCONNECTED, state.phase)
    assertNull(state.portfolio)
}
```

- [ ] **Step 2: Verify RED**

```bash
./gradlew :app:testDebugUnitTest --tests '*DioConnectionServicePolicyTest'
```

Expected: FAIL.

- [ ] **Step 3: Implement the foreground service**

Manifest must include `INTERNET`, `FOREGROUND_SERVICE`, and the current Android foreground-service permission/type required for data sync/network transport. Start foreground before long-lived SSH work. Notification copy must make the connection visible, for example `DIO connected to Debian` or `DIO reconnecting`.

On any SSH/forward failure:

```kotlin
repository.transportDisconnected()
session?.close()
session = null
```

Reconnect may use bounded backoff, but READY returns only after a fresh `/api/launcher/state` fetch passes the reducer.

- [ ] **Step 4: Verify GREEN**

```bash
./gradlew :app:testDebugUnitTest --tests '*DioConnectionServicePolicyTest'
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/dio-mobile/app/src
git commit -m "feat: maintain DIO transport in foreground service"
```

---

### Task 8: Build first-run setup, native home, and embedded DIO surfaces

**Files:**
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ui/SetupScreen.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ui/DioHomeScreen.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/ui/DioSurfaceScreen.kt`
- Create: `android/dio-mobile/app/src/main/java/za/co/dioworkflows/mobile/MainActivity.kt`
- Create: `android/dio-mobile/app/src/main/res/xml/network_security_config.xml`
- Test: `android/dio-mobile/app/src/androidTest/java/za/co/dioworkflows/mobile/DioHomeScreenTest.kt`
- Test: `android/dio-mobile/app/src/androidTest/java/za/co/dioworkflows/mobile/DioSurfaceScreenTest.kt`

**Interfaces:**
- Consumes: `DioRepository.state`, `SecureIdentityStore`, `HostKeyPinStore`, `DioNavigationPolicy`.
- Produces: complete first-run/daily-use Android UI.

- [ ] **Step 1: Write instrumentation contracts**

```kotlin
@Test fun disconnectedHomeDoesNotShowVerified68() {
    composeRule.setContent { DioHomeScreen(disconnectedState(), onOpenSurface = {}) }
    composeRule.onNodeWithText("DISCONNECTED").assertExists()
    composeRule.onNodeWithText("68 VERIFIED").assertDoesNotExist()
}

@Test fun readyHomeShowsFourSurfacesAndLiveArithmetic() {
    composeRule.setContent { DioHomeScreen(ready68State(), onOpenSurface = {}) }
    composeRule.onNodeWithText("53 + 15 = 68").assertExists()
    composeRule.onNodeWithText("GoldenEye").assertExists()
    composeRule.onNodeWithText("Control Deck").assertExists()
    composeRule.onNodeWithText("Market Command").assertExists()
    composeRule.onNodeWithText("Production Studio").assertExists()
}
```

- [ ] **Step 2: Verify RED**

Run on CI/emulator or locally where Android instrumentation is available:

```bash
./gradlew :app:connectedDebugAndroidTest
```

Expected: FAIL because screens are absent.

- [ ] **Step 3: Implement Setup screen**

Fields: Debian host, SSH port default 22, SSH user default `byron`. Actions: create phone identity, copy public key, connect, display first-seen host fingerprint, explicit `Trust this Debian host` control. No password field.

- [ ] **Step 4: Implement Home screen**

Render portfolio arithmetic only from `DioAppState.portfolio`. Use visually distinct `READY`, `HELD`, and `DISCONNECTED` states. Disable all four surface cards unless their fresh surface state is ready.

- [ ] **Step 5: Implement bounded WebView surface screen**

Create WebView with JavaScript only as required by existing DIO pages, DOM storage if required, no file access unless proven necessary, and a `WebViewClient` that delegates every navigation decision to `DioNavigationPolicy`. Unexpected non-DIO network URLs are not loaded internally. Do not add JavaScript interfaces that expose Android secrets or bypass DIO confirmation gates.

- [ ] **Step 6: Configure cleartext only for app loopback usage**

Set the application network security config and keep the code-level navigation policy authoritative. Do not add arbitrary cleartext domains. The SSH tunnel encrypts the off-device leg.

- [ ] **Step 7: Verify instrumentation and unit suites**

```bash
./gradlew :app:testDebugUnitTest :app:connectedDebugAndroidTest :app:lintDebug
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add android/dio-mobile/app/src
git commit -m "feat: add native DIO Android operator console"
```

---

### Task 9: Add Android CI and publish the debug APK artifact

**Files:**
- Create: `.github/workflows/dio-android.yml`
- Modify: `tests/test_dio_android_contract.py`

**Interfaces:**
- Produces: CI job `android-contract` and uploaded artifact `dio-mobile-debug-apk` containing `app-debug.apk`.

- [ ] **Step 1: Write RED workflow contract**

```python
def test_android_ci_builds_tests_lints_and_uploads_apk():
    workflow = (ROOT / ".github/workflows/dio-android.yml").read_text()
    assert ":app:testDebugUnitTest" in workflow
    assert ":app:lintDebug" in workflow
    assert ":app:assembleDebug" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "dio-mobile-debug-apk" in workflow
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_dio_android_contract.py
```

Expected: FAIL because workflow is absent.

- [ ] **Step 3: Implement workflow**

Workflow must checkout, set up JDK 17, set up Android SDK, run Python repository contracts, then from `android/dio-mobile` run:

```bash
./gradlew --no-daemon :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

Upload only:

```text
android/dio-mobile/app/build/outputs/apk/debug/app-debug.apk
```

under artifact name `dio-mobile-debug-apk` after successful test/lint/build steps.

- [ ] **Step 4: Verify GREEN locally/static**

```bash
python -m pytest -q tests/test_dio_android_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/dio-android.yml tests/test_dio_android_contract.py
git commit -m "ci: build installable DIO Android APK"
```

---

### Task 10: Final security/truth verification and APK acceptance

**Files:**
- Modify only files required to close verified defects found by this task.
- Test: all Android unit tests, lint, repository contract tests, CI build artifact.

**Interfaces:**
- Produces: a branch whose current head has passing Android CI and a downloadable debug APK artifact.

- [ ] **Step 1: Run repository-side boundary tests**

```bash
python -m pytest -q tests/test_dio_android_contract.py tests/test_dio_local_launcher.py tests/test_dio_mobile_pwa.py
```

Expected: PASS. Existing localhost-only launcher/mobile contracts must remain intact.

- [ ] **Step 2: Run full Android verification**

```bash
cd android/dio-mobile
./gradlew --no-daemon clean :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Inspect source for forbidden authority/security patterns**

Run:

```bash
grep -RInE 'PromiscuousVerifier|StrictHostKeyChecking=no|0\.0\.0\.0|startShell\(|\.exec\(|authPassword|ssh_private.*putString' android/dio-mobile/app/src || true
```

Expected: no prohibited implementation matches. Any legitimate textual test fixture must be explicitly reviewed rather than ignored.

- [ ] **Step 4: Verify APK exists and record checksum**

```bash
sha256sum app/build/outputs/apk/debug/app-debug.apk
```

Expected: one SHA-256 checksum for the built APK.

- [ ] **Step 5: Verify GitHub Actions head status and artifact**

Confirm the `android-contract` job is green on the exact branch head and that artifact `dio-mobile-debug-apk` exists for that run. Do not claim completion from an older run.

- [ ] **Step 6: Commit any final verified fixes**

If no fixes were required, do not create an empty commit. If fixes were required:

```bash
git add <verified-files>
git commit -m "fix: close DIO Android acceptance findings"
```

- [ ] **Step 7: Open a draft Android PR**

Open a draft PR from `agent/dio-android-native-client` to `agent/dio-control-deck-68-productgrade` titled `Add native DIO Android operator console`. The PR body must state that it creates no new DIO source of truth, keeps Debian DIO services localhost-only, uses app-owned SSH port forwarding, and publishes a debug APK for device testing.
