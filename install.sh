#!/usr/bin/env bash
#
# Установка waybar-player в пользовательский PREFIX (по умолчанию ~/.local).
# Административные права не нужны.

set -euo pipefail

SCRIPT_PATH=$(readlink -f -- "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(dirname -- "$SCRIPT_PATH")
PREFIX="${PREFIX:-$HOME/.local}"

BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/waybar-player"
DOC_DIR="$PREFIX/share/doc/waybar-player"

for needed in \
    "$SCRIPT_DIR/bin/waybar-player-status" \
    "$SCRIPT_DIR/bin/waybar-player-menu" \
    "$SCRIPT_DIR/share/player-menu.py" \
    "$SCRIPT_DIR/share/players.py"; do
    if [[ ! -f $needed ]]; then
        printf 'Не найден файл: %s\n' "$needed" >&2
        exit 1
    fi
done

install -Dm755 "$SCRIPT_DIR/bin/waybar-player-status" "$BIN_DIR/waybar-player-status"
install -Dm755 "$SCRIPT_DIR/bin/waybar-player-menu" "$BIN_DIR/waybar-player-menu"
install -Dm755 "$SCRIPT_DIR/bin/waybar-player-ctl" "$BIN_DIR/waybar-player-ctl"
install -Dm644 "$SCRIPT_DIR/share/player-menu.py" "$SHARE_DIR/player-menu.py"
install -Dm644 "$SCRIPT_DIR/share/players.py" "$SHARE_DIR/players.py"
install -Dm644 "$SCRIPT_DIR/share/i18n.py" "$SHARE_DIR/i18n.py"
for locale in "$SCRIPT_DIR"/locales/*.json; do
    install -Dm644 "$locale" "$SHARE_DIR/locales/$(basename -- "$locale")"
done

install -Dm644 "$SCRIPT_DIR/examples/config.jsonc" "$DOC_DIR/config.jsonc"
install -Dm644 "$SCRIPT_DIR/examples/style.css" "$DOC_DIR/style.css"
install -Dm644 "$SCRIPT_DIR/README.md" "$DOC_DIR/README.md"
install -Dm644 "$SCRIPT_DIR/docs/parity.md" "$DOC_DIR/parity.md"
install -Dm644 "$SCRIPT_DIR/LICENSE" "$PREFIX/share/licenses/waybar-player/LICENSE"

printf 'Установлено в %s\n' "$PREFIX"
printf '  %s\n' "$BIN_DIR/waybar-player-status" "$BIN_DIR/waybar-player-menu" \
    "$BIN_DIR/waybar-player-ctl" "$SHARE_DIR/player-menu.py" "$SHARE_DIR/players.py"
printf 'Документация: %s\n' "$DOC_DIR"
