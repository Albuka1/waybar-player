# Maintainer: <user> <email>
pkgname=waybar-player
pkgver=0.1.0
pkgrel=1
pkgdesc="Compact MPRIS player module and layer-shell popup for Waybar"
arch=('any')
url="https://github.com/<user>/waybar-player"
license=('MIT')
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
    install -Dm755 bin/waybar-player-status "$pkgdir/usr/bin/waybar-player-status"
    install -Dm755 bin/waybar-player-menu "$pkgdir/usr/bin/waybar-player-menu"
    install -Dm644 share/player-menu.py "$pkgdir/usr/share/waybar-player/player-menu.py"
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
