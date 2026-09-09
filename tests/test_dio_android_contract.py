from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "dio-mobile"


def test_android_project_is_pinned_and_dio_scoped():
    root_build = (ANDROID / "build.gradle.kts").read_text(encoding="utf-8")
    app = (ANDROID / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    wrapper = (ANDROID / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(encoding="utf-8")

    assert 'id("com.android.application") version "9.4.0" apply false' in root_build
    assert 'namespace = "za.co.dioworkflows.mobile"' in app
    assert 'applicationId = "za.co.dioworkflows.mobile"' in app
    assert "compileSdk = 37" in app
    assert "minSdk = 26" in app
    assert "targetSdk = 36" in app
    assert "gradle-9.6.0-bin.zip" in wrapper


def test_android_dependencies_are_pinned_for_dio_v1():
    root_build = (ANDROID / "build.gradle.kts").read_text(encoding="utf-8")
    app = (ANDROID / "app" / "build.gradle.kts").read_text(encoding="utf-8")

    assert 'id("org.jetbrains.kotlin.plugin.compose") version "2.3.21" apply false' in root_build
    assert 'id("org.jetbrains.kotlin.plugin.compose")' in app
    assert 'androidx.compose:compose-bom:2026.08.00' in app
    assert 'androidx.activity:activity-compose:1.13.0' in app
    assert 'com.hierynomus:sshj:0.40.0' in app
    assert "+" not in "\n".join(line for line in app.splitlines() if "implementation(" in line)


def test_android_manifest_does_not_create_public_dio_listener():
    manifest = (ANDROID / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "0.0.0.0" not in manifest
    assert "android.permission.INTERNET" in manifest
    assert "android.permission.FOREGROUND_SERVICE" in manifest


def test_private_key_storage_is_keystore_wrapped_and_not_plain_preferences():
    text = (
        ANDROID
        / "app/src/main/java/za/co/dioworkflows/mobile/security/SecureIdentityStore.kt"
    ).read_text(encoding="utf-8")

    assert "AndroidKeyStore" in text
    assert "AES/GCM/NoPadding" in text
    assert "setKeySize(256)" in text
    assert "KeyGenParameterSpec" in text
    assert 'putString("private' not in text
    assert 'putString("ssh_private' not in text


def test_android_ssh_transport_never_uses_permissive_or_shell_auth_patterns():
    text = (
        ANDROID
        / "app/src/main/java/za/co/dioworkflows/mobile/ssh/DioSshTransport.kt"
    ).read_text(encoding="utf-8")

    assert "PromiscuousVerifier" not in text
    assert "StrictHostKeyChecking=no" not in text
    assert "authPassword" not in text
    assert "startShell(" not in text
    assert ".exec(" not in text
    assert "addHostKeyVerifier" in text
    assert "DioForwardPlan.REQUIRED" in text


def test_launcher_state_client_is_network_only_and_no_cache():
    text = (
        ANDROID
        / "app/src/main/java/za/co/dioworkflows/mobile/truth/LauncherStateClient.kt"
    ).read_text(encoding="utf-8")

    assert "http://127.0.0.1:8764/api/launcher/state" in text
    assert "useCaches = false" in text
    assert 'setRequestProperty("Cache-Control", "no-cache, no-store")' in text
    assert "LauncherStateParser.parse" in text


def test_connection_service_is_private_special_use_and_fail_closed():
    manifest = (ANDROID / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    service = (
        ANDROID
        / "app/src/main/java/za/co/dioworkflows/mobile/service/DioConnectionService.kt"
    ).read_text(encoding="utf-8")

    assert "android.permission.FOREGROUND_SERVICE_SPECIAL_USE" in manifest
    assert 'android:name=".service.DioConnectionService"' in manifest
    assert 'android:exported="false"' in manifest
    assert 'android:foregroundServiceType="specialUse"' in manifest
    assert "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" in manifest
    assert "startForeground" in service
    assert "DioSshTransport" in service
    assert "DioRuntime.repository.refreshTruth" in service
    assert "DioRuntime.repository.transportDisconnected" in service
    assert "ACTION_CONNECT" in service
    assert "ACTION_DISCONNECT" in service
    assert "authPassword" not in service
    assert "startShell(" not in service
    assert ".exec(" not in service


def test_connection_failures_are_visible_in_setup_ui():
    service = (
        ANDROID
        / "app/src/main/java/za/co/dioworkflows/mobile/service/DioConnectionService.kt"
    ).read_text(encoding="utf-8")
    activity = (
        ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/MainActivity.kt"
    ).read_text(encoding="utf-8")
    setup = (
        ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/ui/SetupScreen.kt"
    ).read_text(encoding="utf-8")

    assert "DioRuntime.reportConnectionError" in service
    assert "DioRuntime.clearConnectionError" in service
    assert "DioRuntime.connectionError" in activity
    assert "connectionError = connectionError" in activity
    assert "Connection error" in setup


def test_saved_connection_profile_has_no_password_surface():
    text = (
        ANDROID
        / "app/src/main/java/za/co/dioworkflows/mobile/ssh/DioProfileStore.kt"
    ).read_text(encoding="utf-8")

    lowered = text.lower()
    assert "password" not in lowered
    assert "DioSshProfile" in text


def test_android_ci_uploads_installable_debug_apk():
    workflow = (ROOT / ".github/workflows/dio-android.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@v4" in workflow
    assert "dio-android-debug-apk" in workflow
    assert "app/build/outputs/apk/debug/app-debug.apk" in workflow


def test_native_operator_ui_is_activity_backed_and_live_truth_only():
    manifest = (ANDROID / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    activity = (
        ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/MainActivity.kt"
    ).read_text(encoding="utf-8")
    setup = (
        ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/ui/SetupScreen.kt"
    ).read_text(encoding="utf-8")
    home = (
        ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/ui/DioHomeScreen.kt"
    ).read_text(encoding="utf-8")

    assert 'android:name=".MainActivity"' in manifest
    assert 'android.intent.action.MAIN' in manifest
    assert 'android.intent.category.LAUNCHER' in manifest
    assert "DioRuntime.repository.state" in activity
    assert "SecureIdentityStore" in activity
    assert "HostKeyPinStore" in activity
    assert "DioConnectionService.ACTION_CONNECT" in activity
    assert "DioConnectionService.ACTION_DISCONNECT" in activity
    assert "password" not in setup.lower()
    assert "portfolio.baseCount" in home
    assert "portfolio.extensionCount" in home
    assert "portfolio.totalCount" in home
    assert '"53 + 15 = 68"' not in home


def test_embedded_webview_is_bounded_to_dio_navigation_policy():
    surface = (
        ANDROID / "app/src/main/java/za/co/dioworkflows/mobile/ui/DioSurfaceScreen.kt"
    ).read_text(encoding="utf-8")

    assert "DioNavigationPolicy.isInternal" in surface
    assert "allowFileAccess = false" in surface
    assert "allowContentAccess = false" in surface
    assert "addJavascriptInterface" not in surface
    assert "WebViewClient" in surface


def test_android_ci_runs_instrumentation_contracts():
    workflow = (ROOT / ".github/workflows/dio-android.yml").read_text(encoding="utf-8")

    assert "android-emulator-runner" in workflow
    assert ":app:connectedDebugAndroidTest" in workflow
