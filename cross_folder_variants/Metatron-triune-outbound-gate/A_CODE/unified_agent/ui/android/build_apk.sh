#!/bin/bash
# Seraph Unified Agent — Android APK builder
# Usage: ./build_apk.sh [debug|release]  (default: debug)
set -e

MODE="${1:-debug}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/app/build/outputs/apk/$MODE"

echo "=== SERAPH ANDROID APK BUILDER ==="
echo "Mode: $MODE"
echo ""

# Build Docker image if needed
if ! docker images -q seraph-android-builder | grep -q .; then
    echo "[1/2] Building Docker image (first run — takes a few minutes)…"
    docker build -t seraph-android-builder -f "$SCRIPT_DIR/Dockerfile.build.android" "$SCRIPT_DIR"
else
    echo "[1/2] Docker image seraph-android-builder already exists."
fi

# Run the Gradle build inside Docker
echo "[2/2] Running Gradle assembleRelease/Debug…"
docker run --rm \
    -v "$SCRIPT_DIR:/app" \
    -w /app \
    seraph-android-builder \
    bash -c "chmod +x gradlew && ./gradlew assemble${MODE^} --no-daemon 2>&1"

# Find the APK
APK="$(find "$OUTPUT_DIR" -name "*.apk" 2>/dev/null | head -1)"
if [ -n "$APK" ]; then
    echo ""
    echo "=== BUILD SUCCESS ==="
    echo "APK: $APK"
    # Copy to project root for easy access
    cp "$APK" "$SCRIPT_DIR/seraph-agent-$(date +%Y%m%d).apk"
    echo "Copied to: $SCRIPT_DIR/seraph-agent-$(date +%Y%m%d).apk"
else
    echo "ERROR: APK not found in $OUTPUT_DIR"
    exit 1
fi
