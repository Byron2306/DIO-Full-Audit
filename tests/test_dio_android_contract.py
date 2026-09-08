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
    app = (ANDROID / "app" / "build.gradle.kts").read_text(encoding="utf-8")

    assert 'androidx.compose:compose-bom:2026.08.00' in app
    assert 'androidx.activity:activity-compose:1.13.0' in app
    assert 'com.hierynomus:sshj:0.40.0' in app
    assert "+" not in "\n".join(line for line in app.splitlines() if "implementation(" in line)


def test_android_manifest_does_not_create_public_dio_listener():
    manifest = (ANDROID / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "0.0.0.0" not in manifest
    assert "android.permission.INTERNET" in manifest
    assert "android.permission.FOREGROUND_SERVICE" in manifest
