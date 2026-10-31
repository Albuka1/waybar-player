# Maintainer: Albuka1
# shellcheck disable=SC2034,SC2154
pkgname=waybar-player
pkgver=0.2.2
pkgrel=1
pkgdesc="Compact MPRIS player module and layer-shell popup for Waybar"
arch=('any')
url="https://github.com/Albuka1/waybar-player"
license=('MIT')
depends=(
    bash
    waybar
    playerctl
    python
    python-gobject
    gtk3
    gtk-layer-shell
    gdk-pixbuf2
    pango
    util-linux
    procps-ng
    coreutils
)
optdepends=(
    'niri: close the popup when switching workspaces'
    'ttf-jetbrains-mono-nerd: Nerd Font glyphs used by the UI'
    'libnotify: error notifications'
    'wireplumber: system volume fallback via wpctl'
)
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('081385ba05540bb70da5cf4cb668c78be7250c953e11f8ee6687e56957f6b8b8')

package() {
    local src="$srcdir/$pkgname-$pkgver"

    install -Dm755 "$src/bin/waybar-player-status" "$pkgdir/usr/bin/waybar-player-status"
    install -Dm755 "$src/bin/waybar-player-menu" "$pkgdir/usr/bin/waybar-player-menu"
    install -Dm644 "$src/share/player-menu.py" "$pkgdir/usr/share/waybar-player/player-menu.py"
    install -Dm644 "$src/share/i18n.py" "$pkgdir/usr/share/waybar-player/i18n.py"
    for locale in "$src"/locales/*.json; do
        install -Dm644 "$locale" "$pkgdir/usr/share/waybar-player/locales/$(basename -- "$locale")"
    done

    install -Dm644 "$src/examples/config.jsonc" "$pkgdir/usr/share/doc/$pkgname/examples/config.jsonc"
    install -Dm644 "$src/examples/style.css" "$pkgdir/usr/share/doc/$pkgname/examples/style.css"
    install -Dm644 "$src/docs/parity.md" "$pkgdir/usr/share/doc/$pkgname/parity.md"
    install -Dm644 "$src/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm644 "$src/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
