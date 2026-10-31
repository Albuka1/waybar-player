#!/usr/bin/env bash
#
# Удаляет файлы, установленные install.sh. Пользовательские конфиги и кэш
# не затрагиваются.

set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/waybar-player"
DOC_DIR="$PREFIX/share/doc/waybar-player"

rm -f "$BIN_DIR/waybar-player-status" "$BIN_DIR/waybar-player-menu" "$BIN_DIR/waybar-player-ctl"
rm -f "$SHARE_DIR/player-menu.py" "$SHARE_DIR/i18n.py" "$SHARE_DIR/players.py"
for locale in "$SHARE_DIR"/locales/*.json; do
    if [[ -e $locale ]]; then
        rm -f "$locale"
    fi
done
rm -f "$DOC_DIR/config.jsonc" "$DOC_DIR/style.css" "$DOC_DIR/README.md" "$DOC_DIR/parity.md"
rm -f "$PREFIX/share/licenses/waybar-player/LICENSE"

rmdir --ignore-fail-on-non-empty "$SHARE_DIR/locales" "$SHARE_DIR" "$DOC_DIR" \
    "$PREFIX/share/licenses/waybar-player" 2>/dev/null || true

printf 'Удалены файлы waybar-player из %s\n' "$PREFIX"
