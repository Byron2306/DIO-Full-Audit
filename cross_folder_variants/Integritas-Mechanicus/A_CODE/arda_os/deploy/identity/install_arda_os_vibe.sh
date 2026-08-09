#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
WALLPAPER_SRC="$REPO_ROOT/arda-sovereign-website/assets/media/arda-wallpaper.webp"
FALLBACK_WALLPAPER="$REPO_ROOT/arda_os/deploy/boot/assets/arda-wallpaper.png"
GTK_CSS_SRC="$REPO_ROOT/arda_os/deploy/identity/gtk.css"
WALLPAPER_GENERATOR="$REPO_ROOT/arda_os/deploy/identity/generate_arda_wallpaper.py"
TARGET_DIR="${ARDA_OS_VIBE_TARGET_DIR:-$HOME/.local/share/backgrounds/arda-valinor}"
TARGET_WALLPAPER="$TARGET_DIR/arda-valinor-wallpaper.png"
TARGET_WALLPAPER_DUSK="$TARGET_DIR/arda-valinor-dusk.png"
TARGET_WALLPAPER_EMBER="$TARGET_DIR/arda-valinor-ember.png"
TARGET_WALLPAPER_SILVER="$TARGET_DIR/arda-valinor-silver.png"
TARGET_WALLPAPER_CROWN="$TARGET_DIR/arda-valinor-crown.png"
TARGET_WALLPAPER_DAWN="$TARGET_DIR/arda-valinor-dawn.png"
GTK3_DIR="$HOME/.config/gtk-3.0"
GTK4_DIR="$HOME/.config/gtk-4.0"
XFCE_TERMINAL_DIR="$HOME/.config/xfce4/terminal"
XFCE_TERMINAL_THEME="$XFCE_TERMINAL_DIR/terminalrc"
ICON_DIR="$HOME/.local/share/icons/arda-valinor"
ICON_APPS_DIR="$ICON_DIR/apps/64"
PANEL_DIR="$HOME/.config/xfce4/panel"
AUTOSTART_DIR="$HOME/.config/autostart"
AWAKENING_SCRIPT="$HOME/.local/bin/arda-desktop-awakening"

if ! mkdir -p "$TARGET_DIR" 2>/dev/null; then
  TARGET_DIR="$REPO_ROOT/arda_os/deploy/identity/staged-backgrounds"
  TARGET_WALLPAPER="$TARGET_DIR/arda-valinor-wallpaper.png"
  TARGET_WALLPAPER_DUSK="$TARGET_DIR/arda-valinor-dusk.png"
  TARGET_WALLPAPER_EMBER="$TARGET_DIR/arda-valinor-ember.png"
  TARGET_WALLPAPER_SILVER="$TARGET_DIR/arda-valinor-silver.png"
  TARGET_WALLPAPER_CROWN="$TARGET_DIR/arda-valinor-crown.png"
  TARGET_WALLPAPER_DAWN="$TARGET_DIR/arda-valinor-dawn.png"
  mkdir -p "$TARGET_DIR"
fi
if [ -f "$WALLPAPER_GENERATOR" ]; then
  if python3 "$WALLPAPER_GENERATOR" --output "$TARGET_WALLPAPER_DUSK" --profile dusk --width 1920 --height 1080 >/dev/null 2>&1 && \
     python3 "$WALLPAPER_GENERATOR" --output "$TARGET_WALLPAPER_EMBER" --profile ember --width 1920 --height 1080 >/dev/null 2>&1 && \
     python3 "$WALLPAPER_GENERATOR" --output "$TARGET_WALLPAPER_SILVER" --profile silver --width 1920 --height 1080 >/dev/null 2>&1 && \
     python3 "$WALLPAPER_GENERATOR" --output "$TARGET_WALLPAPER_CROWN" --profile crown --width 1920 --height 1080 >/dev/null 2>&1 && \
     python3 "$WALLPAPER_GENERATOR" --output "$TARGET_WALLPAPER_DAWN" --profile dawn --width 1920 --height 1080 >/dev/null 2>&1; then
    cp "$TARGET_WALLPAPER_DAWN" "$TARGET_WALLPAPER"
    :
  elif [ -f "$WALLPAPER_SRC" ]; then
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DUSK"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_EMBER"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_SILVER"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_CROWN"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DAWN"
  else
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DUSK"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_EMBER"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_SILVER"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_CROWN"
    cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DAWN"
  fi
elif [ -f "$WALLPAPER_SRC" ]; then
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DUSK"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_EMBER"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_SILVER"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_CROWN"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DAWN"
else
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DUSK"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_EMBER"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_SILVER"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_CROWN"
  cp "$FALLBACK_WALLPAPER" "$TARGET_WALLPAPER_DAWN"
fi

mkdir -p "$GTK3_DIR" "$GTK4_DIR" "$XFCE_TERMINAL_DIR" "$ICON_APPS_DIR" "$AUTOSTART_DIR" "$HOME/.local/bin"
cp "$GTK_CSS_SRC" "$GTK3_DIR/gtk.css"
cp "$GTK_CSS_SRC" "$GTK4_DIR/gtk.css"
cp "$REPO_ROOT/arda_os/deploy/identity/arda_desktop_awakening.sh" "$AWAKENING_SCRIPT"
chmod +x "$AWAKENING_SCRIPT"
cp "$REPO_ROOT/arda_os/deploy/identity/arda-awakening.desktop" "$AUTOSTART_DIR/arda-awakening.desktop"

cp "$REPO_ROOT/arda_os/deploy/boot/assets/arda-seal.png" "$ICON_APPS_DIR/arda-command-gate.png"
cp "$REPO_ROOT/arda_os/deploy/boot/assets/arda-silver-crown-bar.png" "$ICON_APPS_DIR/arda-ledger-archive.png"
cp "$REPO_ROOT/arda_os/deploy/boot/assets/arda-mirror-gate.png" "$ICON_APPS_DIR/arda-mirror-gate.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/arda-council-index.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/user-home.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/folder.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/inode-directory.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/folder-documents.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/folder-download.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/system-file-manager.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/user-trash.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/user-trash-full.png"
cp "$REPO_ROOT/arda_os/arda_desktop/static/assets/icon.png" "$ICON_APPS_DIR/drive-harddisk.png"

cat >"$ICON_DIR/index.theme" <<EOF
[Icon Theme]
Name=ARDA Valinor
Comment=ARDA operator identity icons
Inherits=Adwaita
Directories=apps/64

[apps/64]
Size=64
Context=Applications
Type=Fixed
EOF

cat >"$XFCE_TERMINAL_THEME" <<EOF
ColorForeground=#dce8ee
ColorBackground=#02050b
ColorCursor=#63e6ff
ColorSelection=#0d2235
ColorPalette=#02050b;#d84146;#2bd786;#f0a53b;#63e6ff;#b99455;#19bfaf;#dce8ee;#071426;#d84146;#2bd786;#f0a53b;#63e6ff;#b99455;#19bfaf;#e8f0f4
FontName=JetBrains Mono 11
MiscAlwaysShowTabs=FALSE
MiscBell=FALSE
MiscMenubarDefault=FALSE
MiscToolbarDefault=FALSE
MiscBordersDefault=FALSE
MiscDefaultGeometry=118x32
EOF

for launcher in "$PANEL_DIR"/launcher-*/*.desktop; do
  [ -f "$launcher" ] || continue
  if grep -q 'exo-open --launch TerminalEmulator' "$launcher"; then
    cat >"$launcher" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Exec=exo-open --launch TerminalEmulator
Icon=$ICON_APPS_DIR/arda-command-gate.png
StartupNotify=true
Terminal=false
Categories=Utility;X-XFCE;X-Xfce-Toplevel;
OnlyShowIn=XFCE;
Name=Command Gate
Comment=Enter the sovereign shell
EOF
  elif grep -q 'exo-open --launch FileManager' "$launcher"; then
    cat >"$launcher" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Exec=exo-open --launch FileManager %u
Icon=$ICON_APPS_DIR/arda-ledger-archive.png
StartupNotify=true
Terminal=false
Categories=Utility;X-XFCE;X-Xfce-Toplevel;
OnlyShowIn=XFCE;
Name=Ledger Archive
Comment=Traverse the local dominion
EOF
  elif grep -q 'exo-open --launch WebBrowser' "$launcher"; then
    cat >"$launcher" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Exec=exo-open --launch WebBrowser %u
Icon=$ICON_APPS_DIR/arda-mirror-gate.png
StartupNotify=true
Terminal=false
Categories=Network;X-XFCE;X-Xfce-Toplevel;
OnlyShowIn=XFCE;
Name=Mirror Gate
Comment=Cross into the outer web
EOF
  elif grep -q '^Exec=xfce4-appfinder' "$launcher"; then
    cat >"$launcher" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Exec=xfce4-appfinder
Icon=$ICON_APPS_DIR/arda-council-index.png
StartupNotify=true
Terminal=false
Categories=Utility;X-XFCE;
Name=Council Index
Comment=Summon applications and instruments
EOF
  fi
done

if command -v xfconf-query >/dev/null 2>&1; then
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/last-image$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s "$TARGET_WALLPAPER" || true
  done
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/last-single-image$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s "$TARGET_WALLPAPER" || true
  done
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/image-path$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s "$TARGET_WALLPAPER" || true
  done

  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/image-style$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s 5 || true
  done
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/image-show$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s true || true
  done
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/color-style$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s 0 || true
  done

  if xfconf-query -c xsettings -l >/dev/null 2>&1; then
    xfconf-query -c xsettings -p /Net/ThemeName -n -t string -s "Adwaita-dark" 2>/dev/null || \
      xfconf-query -c xsettings -p /Net/ThemeName -t string -s "Adwaita-dark" || true
    xfconf-query -c xsettings -p /Net/IconThemeName -n -t string -s "ARDA Valinor" 2>/dev/null || \
      xfconf-query -c xsettings -p /Net/IconThemeName -t string -s "ARDA Valinor" || true
    xfconf-query -c xsettings -p /Net/SoundThemeName -n -t string -s "freedesktop" 2>/dev/null || \
      xfconf-query -c xsettings -p /Net/SoundThemeName -t string -s "freedesktop" || true
    xfconf-query -c xsettings -p /Gtk/CursorThemeName -n -t string -s "Adwaita" 2>/dev/null || \
      xfconf-query -c xsettings -p /Gtk/CursorThemeName -t string -s "Adwaita" || true
    xfconf-query -c xsettings -p /Net/PreferDarkTheme -n -t bool -s true 2>/dev/null || \
      xfconf-query -c xsettings -p /Net/PreferDarkTheme -t bool -s true || true
    xfconf-query -c xsettings -p /Gtk/FontName -n -t string -s "Sans 10" 2>/dev/null || \
      xfconf-query -c xsettings -p /Gtk/FontName -t string -s "Sans 10" || true
    xfconf-query -c xsettings -p /Gtk/MonospaceFontName -n -t string -s "JetBrains Mono 11" 2>/dev/null || \
      xfconf-query -c xsettings -p /Gtk/MonospaceFontName -t string -s "JetBrains Mono 11" || true
  fi

  if xfconf-query -c xfwm4 -l >/dev/null 2>&1; then
    xfconf-query -c xfwm4 -p /general/title_font -n -t string -s "Sans Bold 10" 2>/dev/null || \
      xfconf-query -c xfwm4 -p /general/title_font -t string -s "Sans Bold 10" || true
    xfconf-query -c xfwm4 -p /general/theme -n -t string -s "Default" 2>/dev/null || \
      xfconf-query -c xfwm4 -p /general/theme -t string -s "Default" || true
  fi

  if xfconf-query -c xfce4-panel -l >/dev/null 2>&1; then
    for panel_path in $(xfconf-query -c xfce4-panel -l 2>/dev/null | grep '^/panels/panel-[0-9]\+$' || true); do
      xfconf-query -c xfce4-panel -p "$panel_path/background-style" -n -t int -s 1 2>/dev/null || \
        xfconf-query -c xfce4-panel -p "$panel_path/background-style" -t int -s 1 || true
      xfconf-query -c xfce4-panel -p "$panel_path/background-rgba" -n -t double -t double -t double -t double -s 0.027 -s 0.078 -s 0.149 -s 0.92 2>/dev/null || \
        xfconf-query -c xfce4-panel -p "$panel_path/background-rgba" -t double -t double -t double -t double -s 0.027 -s 0.078 -s 0.149 -s 0.92 || true
      xfconf-query -c xfce4-panel -p "$panel_path/size" -n -t int -s 34 2>/dev/null || \
        xfconf-query -c xfce4-panel -p "$panel_path/size" -t int -s 34 || true
      xfconf-query -c xfce4-panel -p "$panel_path/length-adjust" -n -t bool -s true 2>/dev/null || \
        xfconf-query -c xfce4-panel -p "$panel_path/length-adjust" -t bool -s true || true
    done
  fi

  xfconf-query -c xfce4-desktop -p /desktop-icons/style -n -t int -s 2 2>/dev/null || \
    xfconf-query -c xfce4-desktop -p /desktop-icons/style -t int -s 2 || true
fi

cat <<EOF
ARDA OS vibe installed
wallpaper: $TARGET_WALLPAPER
dusk_wallpaper: $TARGET_WALLPAPER_DUSK
dawn_stage_1: $TARGET_WALLPAPER_EMBER
dawn_stage_2: $TARGET_WALLPAPER_SILVER
dawn_stage_3: $TARGET_WALLPAPER_CROWN
dawn_wallpaper: $TARGET_WALLPAPER_DAWN
palette: void/navy/silver/cyan/teal/gold
gtk_css: $GTK3_DIR/gtk.css
terminal_theme: $XFCE_TERMINAL_THEME
awakening_script: $AWAKENING_SCRIPT
session: XFCE dark preference, wallpaper, panel tint, terminal palette, awakening autostart
EOF
