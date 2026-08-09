#!/bin/bash
# Metatron Unified Agent Build Script
# Builds all platform-specific agent applications

# Resolve script directory so paths work no matter where the script is invoked from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -e

# Determine python/pip command (prefer python3/pip3, fall back to python/pip)
PYTHON_CMD=python3
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD=python
    fi
fi

PIP_CMD=pip3
if ! command -v "$PIP_CMD" &> /dev/null; then
    if command -v pip &> /dev/null; then
        PIP_CMD=pip
    fi
fi
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     ███╗   ███╗███████╗████████╗ █████╗ ████████╗██████╗  ██████╗ ███╗   ██╗   ██╗"
echo "║     ████╗ ████║██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║   ██║"
echo "║     ██╔████╔██║█████╗     ██║   ███████║   ██║   ██████╔╝██║   ██║██╔██╗ ██║   ██║"
echo "║     ██║╚██╔╝██║██╔══╝     ██║   ██╔══██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║   ╚═╝"
echo "║     ██║ ╚═╝ ██║███████╗   ██║   ██║  ██║   ██║   ██║  ██║╚██████╔╝██║ ╚████║   ██╗"
echo "║     ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝"
echo "║                                                              ║"
echo "║                 UNIFIED AGENT BUILD SYSTEM                    ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BUILD_DIR="$SCRIPT_DIR"
DIST_DIR="$BUILD_DIR/dist"
VERSION="1.0.0"

# Create directories
mkdir -p "$DIST_DIR"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking build dependencies..."

    # Check Python
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        log_error "Python 3 is required but not installed."
        exit 1
    fi

    # Check pip
    if ! command -v "$PIP_CMD" &> /dev/null; then
        log_error "pip is required but not installed."
        exit 1
    fi

    PYTHON_VERSION_FULL=$($PYTHON_CMD --version | cut -d' ' -f2)
    PY_MAJOR=$(echo "$PYTHON_VERSION_FULL" | cut -d. -f1)
    PY_MINOR=$(echo "$PYTHON_VERSION_FULL" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
        log_error "Python 3.8+ is required. Found: $PYTHON_VERSION_FULL"
        exit 1
    fi

    log_success "Python $PYTHON_VERSION_FULL found"
}

install_python_deps() {
    log_info "Installing Python dependencies..."

    # Install repository requirements from the unified_agent folder
    if [ -f "$BUILD_DIR/requirements.txt" ]; then
        # Use the detected pip to install requirements
        $PIP_CMD install -r "$BUILD_DIR/requirements.txt"
    else
        log_error "Could not open requirements file: $BUILD_DIR/requirements.txt"
        exit 1
    fi

    # Install platform-specific tools
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        $PIP_CMD install pyinstaller
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        $PIP_CMD install pyinstaller
        # Check for Xcode command line tools
        if ! xcode-select -p &> /dev/null; then
            log_warning "Xcode command line tools not found. Installing..."
            xcode-select --install
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        $PIP_CMD install pyinstaller
    fi

    log_success "Python dependencies installed"
}

build_desktop_app() {
    local platform=$1
    local source_file=$2
    local output_name=$3

    log_info "Building $platform desktop application..."

    if [[ "$platform" == "windows" ]]; then
        pyinstaller --onefile --windowed --name "$output_name" "$source_file" --distpath "$DIST_DIR/windows"
    elif [[ "$platform" == "linux" ]]; then
        pyinstaller --onefile --name "$output_name" "$source_file" --distpath "$DIST_DIR/linux"
    elif [[ "$platform" == "macos" ]]; then
        pyinstaller --onefile --name "$output_name" "$source_file" --distpath "$DIST_DIR/macos"
    fi

    if [[ $? -eq 0 ]]; then
        log_success "$platform application built successfully"
    else
        log_error "Failed to build $platform application"
        exit 1
    fi
}

build_windows_app() {
    log_info "Building Windows application..."

    # Build the main Tkinter app
    # Prefer the windows UI entrypoint; fall back to desktop/main.py if missing
    SOURCE_UI="$BUILD_DIR/ui/windows/main.py"
    if [ ! -f "$SOURCE_UI" ] && [ -f "$BUILD_DIR/ui/desktop/main.py" ]; then
        SOURCE_UI="$BUILD_DIR/ui/desktop/main.py"
        log_warning "Windows UI entrypoint not found; using desktop UI: $SOURCE_UI"
    fi

    pyinstaller \
        --onefile \
        --windowed \
        --name "MetatronAgent" \
        --distpath "$DIST_DIR/windows" \
        --add-data "unified_agent/core;core" \
        --hidden-import tkinter \
        --hidden-import PIL \
        "$SOURCE_UI"

    # Create installer using NSIS (if available)
    if command -v makensis &> /dev/null; then
        log_info "Creating Windows installer..."
        # Create NSIS script
        cat > installer.nsi << EOF
!include "MUI2.nsh"

Name "Metatron Agent"
OutFile "$DIST_DIR/windows/MetatronAgent-$VERSION-Setup.exe"
Unicode True

InstallDir "\$PROGRAMFILES\Metatron Agent"
InstallDirRegKey HKCU "Software\MetatronAgent" ""

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "MainSection" SEC01
    SetOutPath "\$INSTDIR"
    File "$DIST_DIR/windows/MetatronAgent.exe"
    CreateShortCut "\$SMPROGRAMS\Metatron Agent.lnk" "\$INSTDIR\MetatronAgent.exe"
    WriteRegStr HKCU "Software\MetatronAgent" "" \$INSTDIR
    WriteUninstaller "\$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "\$INSTDIR\MetatronAgent.exe"
    Delete "\$INSTDIR\Uninstall.exe"
    Delete "\$SMPROGRAMS\Metatron Agent.lnk"
    RMDir "\$INSTDIR"
    DeleteRegKey HKCU "Software\MetatronAgent"
SectionEnd
EOF
        makensis installer.nsi
        rm installer.nsi
        log_success "Windows installer created"
    fi

    log_success "Windows application built"
}

build_linux_app() {
    log_info "Building Linux application..."

    # Build the main Tkinter app
    pyinstaller \
        --onefile \
        --name "MetatronAgent" \
        --distpath "$DIST_DIR/linux" \
        --add-data "unified_agent/core:core" \
        --hidden-import tkinter \
        --hidden-import PIL \
        "$BUILD_DIR/ui/linux/main.py"

    # Create .deb package (if dpkg is available)
    if command -v dpkg &> /dev/null; then
        log_info "Creating Debian package..."

        # Create package structure
        PKG_DIR="$DIST_DIR/linux/deb/metatron-agent_$VERSION"
        mkdir -p "$PKG_DIR/DEBIAN"
        mkdir -p "$PKG_DIR/usr/bin"
        mkdir -p "$PKG_DIR/usr/share/metatron-agent"

        # Copy files
        cp "$DIST_DIR/linux/MetatronAgent" "$PKG_DIR/usr/bin/"
        chmod +x "$PKG_DIR/usr/bin/MetatronAgent"

        # Create control file
        cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: metatron-agent
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.8)
Maintainer: Metatron Security <security@metatron.local>
Description: Unified Security Agent for Metatron
 Metatron unified security agent for cross-platform monitoring
 and threat detection.
EOF

        # Create postinst script
        cat > "$PKG_DIR/DEBIAN/postinst" << EOF
#!/bin/bash
chmod +x /usr/bin/MetatronAgent
EOF
        chmod +x "$PKG_DIR/DEBIAN/postinst"

        # Build package
        dpkg-deb --build "$PKG_DIR"
        mv "$PKG_DIR.deb" "$DIST_DIR/linux/"
        rm -rf "$PKG_DIR"

        log_success "Debian package created"
    fi

    log_success "Linux application built"
}

build_macos_app() {
    log_info "Building macOS application..."

    # Build the SwiftUI app
    if command -v swift &> /dev/null; then
        log_info "Building SwiftUI application..."

        SWIFT_DIR="$BUILD_DIR/ui/macos"
        BUILD_OUTPUT="$DIST_DIR/macos"

        # Create Xcode project structure if it doesn't exist
        if [ ! -d "$SWIFT_DIR.xcodeproj" ]; then
            log_info "Creating Xcode project..."
            # In a real implementation, this would create an Xcode project
            # For now, we'll assume the Swift files are ready
        fi

        # Build with Swift
        cd "$SWIFT_DIR"
        swift build --configuration release
        cp ".build/release/MetatronAgent" "$BUILD_OUTPUT/"
        cd - > /dev/null

        log_success "SwiftUI application built"
    else
        log_warning "Swift not found, building Python fallback..."

        # Fallback to Python app
        pyinstaller \
            --onefile \
            --name "MetatronAgent" \
            --distpath "$DIST_DIR/macos" \
            --add-data "unified_agent/core:core" \
            --hidden-import tkinter \
            --hidden-import PIL \
            "$BUILD_DIR/ui/macos/main.py"
    fi

    # Create .dmg if hdiutil is available
    if command -v hdiutil &> /dev/null; then
        log_info "Creating macOS .dmg installer..."

        DMG_DIR="$DIST_DIR/macos/dmg"
        mkdir -p "$DMG_DIR"
        cp "$DIST_DIR/macos/MetatronAgent" "$DMG_DIR/"

        hdiutil create -volname "Metatron Agent" -srcfolder "$DMG_DIR" -ov -format UDZO "$DIST_DIR/macos/MetatronAgent-$VERSION.dmg"
        rm -rf "$DMG_DIR"

        log_success "macOS .dmg created"
    fi

    log_success "macOS application built"
}

build_android_app() {
    log_info "Building Android application..."

    ANDROID_DIR="$BUILD_DIR/ui/android"

    if [ -d "$ANDROID_DIR" ] && command -v gradle &> /dev/null; then
        log_info "Building Android APK..."

        cd "$ANDROID_DIR"

        # Build debug APK
        ./gradlew assembleDebug

        # Build release APK (requires signing config)
        if [ -f "app/release.keystore" ]; then
            ./gradlew assembleRelease
            cp "app/build/outputs/apk/release/app-release.apk" "$DIST_DIR/android/"
        fi

        cp "app/build/outputs/apk/debug/app-debug.apk" "$DIST_DIR/android/"

        cd - > /dev/null

        log_success "Android APK built"
    else
        log_warning "Android build tools not found, skipping Android build"
    fi
}

build_ios_app() {
    log_info "Building iOS application..."

    IOS_DIR="$BUILD_DIR/ui/ios"

    if [ -d "$IOS_DIR" ] && command -v xcodebuild &> /dev/null; then
        log_info "Building iOS app..."

        cd "$IOS_DIR"

        # Build for simulator
        xcodebuild -scheme "MetatronAgent" -configuration Release -sdk iphonesimulator -derivedDataPath build

        # Archive for distribution (requires provisioning profile)
        # xcodebuild -scheme "MetatronAgent" -configuration Release -sdk iphoneos -derivedDataPath build archive

        # Export IPA if archive exists
        if [ -d "build.xcarchive" ]; then
            xcodebuild -exportArchive -archivePath "build.xcarchive" -exportPath "$DIST_DIR/ios" -exportOptionsPlist exportOptions.plist
        fi

        cd - > /dev/null

        log_success "iOS app built"
    else
        log_warning "iOS build tools not found, skipping iOS build"
    fi
}

build_server() {
    log_info "Building server components..."

    # Build server API
    pyinstaller \
        --onefile \
        --name "MetatronServer" \
        --distpath "$DIST_DIR/server" \
        "$BUILD_DIR/server_api.py"

    # Build auto-deployment system
    pyinstaller \
        --onefile \
        --name "AutoDeployment" \
        --distpath "$DIST_DIR/server" \
        "$BUILD_DIR/auto_deployment.py"

    log_success "Server components built"
}

create_installer_scripts() {
    log_info "Creating installer scripts..."

    # Create Windows installer script
    cat > "$DIST_DIR/windows/install.bat" << 'EOF'
@echo off
echo Installing Metatron Agent...
copy "MetatronAgent.exe" "%PROGRAMFILES%\Metatron Agent\"
echo Metatron Agent installed successfully!
pause
EOF

    # Create Linux installer script
    cat > "$DIST_DIR/linux/install.sh" << 'EOF'
#!/bin/bash
echo "Installing Metatron Agent..."
sudo cp MetatronAgent /usr/local/bin/
sudo chmod +x /usr/local/bin/MetatronAgent
echo "Metatron Agent installed successfully!"
EOF
    chmod +x "$DIST_DIR/linux/install.sh"

    # Create macOS installer script
    cat > "$DIST_DIR/macos/install.sh" << 'EOF'
#!/bin/bash
echo "Installing Metatron Agent..."
cp MetatronAgent /Applications/
chmod +x /Applications/MetatronAgent
echo "Metatron Agent installed successfully!"
EOF
    chmod +x "$DIST_DIR/macos/install.sh"

    log_success "Installer scripts created"
}

main() {
    local platforms=("$@")

    # Default to all platforms if none specified
    if [ ${#platforms[@]} -eq 0 ]; then
        platforms=("windows" "linux" "macos" "android" "ios" "server")
    fi

    log_info "Building Metatron Agent for platforms: ${platforms[*]}"

    check_dependencies
    install_python_deps

    for platform in "${platforms[@]}"; do
        case $platform in
            "windows")
                build_windows_app
                ;;
            "linux")
                build_linux_app
                ;;
            "macos")
                build_macos_app
                ;;
            "android")
                build_android_app
                ;;
            "ios")
                build_ios_app
                ;;
            "server")
                build_server
                ;;
            *)
                log_warning "Unknown platform: $platform"
                ;;
        esac
    done

    create_installer_scripts

    log_success "Build completed!"
    log_info "Output directory: $DIST_DIR"
    log_info "Built platforms: ${platforms[*]}"

    echo ""
    echo -e "${CYAN}Build Summary:${NC}"
    echo -e "${CYAN}==============${NC}"

    for platform in "${platforms[@]}"; do
        case $platform in
            "windows")
                echo -e "${GREEN}✓${NC} Windows: $DIST_DIR/windows/MetatronAgent.exe"
                ;;
            "linux")
                echo -e "${GREEN}✓${NC} Linux: $DIST_DIR/linux/MetatronAgent"
                ;;
            "macos")
                echo -e "${GREEN}✓${NC} macOS: $DIST_DIR/macos/MetatronAgent"
                ;;
            "android")
                echo -e "${GREEN}✓${NC} Android: $DIST_DIR/android/app-debug.apk"
                ;;
            "ios")
                echo -e "${GREEN}✓${NC} iOS: Built in Xcode"
                ;;
            "server")
                echo -e "${GREEN}✓${NC} Server: $DIST_DIR/server/"
                ;;
        esac
    done
}

# Parse command line arguments
platforms=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            shift
            while [[ $# -gt 0 && ! $1 =~ ^-- ]]; do
                platforms+=("$1")
                shift
            done
            ;;
        --help|-h)
            echo "Usage: $0 [--platform platform1 platform2 ...]"
            echo "Platforms: windows, linux, macos, android, ios, server"
            echo "If no platforms specified, builds all platforms"
            exit 0
            ;;
        *)
            platforms+=("$1")
            shift
            ;;
    esac
done

main "${platforms[@]}"