#!/bin/bash
# Elemental Prefix installer. Run again to update.
#   curl -fsSL https://raw.githubusercontent.com/Koutasora/Elemental-Prefix/main/install.sh | bash
set -euo pipefail

REF="${ELEMENTAL_PREFIX_REF:-main}"
URL="https://raw.githubusercontent.com/Koutasora/Elemental-Prefix/$REF/src/elemental-prefix.py"
DIR="$HOME/.local/share/elemental-prefix"
APP="$DIR/elemental-prefix.py"
DESKTOP="$HOME/.local/share/applications/elemental-prefix.desktop"

command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
mkdir -p "$DIR" "$(dirname "$DESKTOP")"

# From a downloaded copy of the repo use its file, otherwise download it.
HERE="$(dirname "${BASH_SOURCE[0]:-/nonexistent}")"
if [ -f "$HERE/src/elemental-prefix.py" ]; then
    cp "$HERE/src/elemental-prefix.py" "$APP.part"
else
    curl -fsSL "$URL" -o "$APP.part"
fi
python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" "$APP.part"
mv -f "$APP.part" "$APP"
chmod +x "$APP"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Elemental Prefix
Comment=One shared Proton prefix for non-Steam games and apps
Exec=python3 $APP
Icon=applications-games
Categories=Game;Utility;
Terminal=false
Actions=uninstall;

[Desktop Action uninstall]
Name=Uninstall Elemental Prefix
Exec=python3 $APP uninstall --gui
EOF

command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true

echo "Elemental Prefix installed."
echo "Open it from the application menu in Desktop Mode (search: Elemental Prefix)."
flatpak info com.github.Matoking.protontricks >/dev/null 2>&1 \
    || echo "Protontricks is missing - install it from Discover first."
