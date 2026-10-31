# waybar-player

Компактный MPRIS-плеер для Waybar: custom-модуль в панели и всплывающая
карточка на GTK3 + gtk-layer-shell.

![Скриншот-заглушка](docs/screenshot.png)

> Это заглушка. Замените `docs/screenshot.png` реальным скриншотом панели и попапа.

## Возможности

- Статус в панели: вращающийся диск `◐ ◓ ◑ ◒`, бегущая строка, pause/idle,
  tooltip с треком, исполнителем, альбомом, плеером и громкостью.
- JSON-вывод для Waybar: `text`, `tooltip`, `class`, `percentage`.
- Компактное меню под зоной плеера: обложка, название, исполнитель, альбом,
  кнопки prev/play/next, слайдер громкости по клику на иконку, перемотка снизу.
- Меню не перемещается (layer-shell), закрывается по клику вне карточки,
  по `✕`, `Esc`, повторному клику по модулю и при смене воркспейса niri.
- Обложки загружаются в фоне; до загрузки показывается заглушка.
- Кэш обложек: `$XDG_CACHE_HOME/waybar-player`; файлы `popup-*.img` старше
  14 дней удаляются при старте меню.

## Зависимости (Arch)

Обязательные:

```text
bash waybar playerctl python python-gobject gtk3 gtk-layer-shell
gdk-pixbuf2 pango util-linux procps-ng coreutils
```

Опциональные:

```text
niri                    # закрытие меню при смене воркспейса
ttf-jetbrains-mono-nerd # шрифт с Nerd Font-глифами
libnotify               # уведомления об ошибках
```

## Установка

### Пакет из репозитория

PKGBUILD рассчитан на архив релиза:

```bash
git archive --prefix=waybar-player-0.1.0/ -o waybar-player-0.1.0.tar.gz HEAD
makepkg -si
```

Пакет ставит:

```text
/usr/bin/waybar-player-status
/usr/bin/waybar-player-menu
/usr/share/waybar-player/player-menu.py
/usr/share/doc/waybar-player/
```

### Вручную, для текущего пользователя

```bash
install -Dm755 bin/waybar-player-status ~/.local/bin/waybar-player-status
install -Dm755 bin/waybar-player-menu   ~/.local/bin/waybar-player-menu
install -Dm644 share/player-menu.py     ~/.local/bin/player-menu.py
```

`waybar-player-menu` ищет `player-menu.py` рядом с собой, затем в
`/usr/share/waybar-player/`. Для системной установки:

```bash
sudo install -Dm755 bin/waybar-player-status /usr/local/bin/waybar-player-status
sudo install -Dm755 bin/waybar-player-menu   /usr/local/bin/waybar-player-menu
sudo install -Dm644 share/player-menu.py     /usr/share/waybar-player/player-menu.py
```

Убедитесь, что каталог с бинарниками есть в `PATH` у Waybar.

## Настройка Waybar

Добавьте `custom/player` в `modules-right` (или `modules-center`). Если у вас
включён встроенный `mpris`, уберите его, иначе трек будет показан дважды.

```jsonc
"custom/player": {
  "exec": "waybar-player-status",
  "return-type": "json",
  "escape": true,
  "tooltip": true,
  "exec-on-event": false,
  "restart-interval": 2,
  "on-click": "waybar-player-menu",
  "on-click-middle": "playerctl previous",
  "on-click-right": "playerctl play-pause",
  "on-scroll-up": "playerctl volume 0.05+",
  "on-scroll-down": "playerctl volume 0.05-"
}
```

Готовый минимальный пример лежит в [`examples/config.jsonc`](examples/config.jsonc).

Стили:

```css
#custom-player {
    color: #ff8c00;
    padding: 0 16px;
    margin: 0 8px;
    background-color: rgba(255, 140, 0, 0.08);
    border-radius: 6px;
}

#custom-player.paused {
    color: #666666;
    background-color: rgba(255, 255, 255, 0.045);
}

#custom-player.stopped {
    color: #555555;
    background-color: transparent;
}

#custom-player:hover {
    background-color: rgba(255, 140, 0, 0.18);
}
```

Готовый пример: [`examples/style.css`](examples/style.css).

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---:|---|
| `WAYBAR_PLAYER_RIGHT_MARGIN` | `215` | Отступ карточки от правого края экрана. Подберите так, чтобы карточка была под зоной плеера. |
| `WAYBAR_PLAYER_WIDTH` | `320` | Ширина карточки в px. |
| `WAYBAR_PLAYER_TITLE_WIDTH` | `30` | Сколько символов названия трека показывать в панели. |

Значения должны быть целыми; некорректное значение заменяется значением по
умолчанию. Переменные задаются в окружении Waybar/niri, например:

```bash
WAYBAR_PLAYER_RIGHT_MARGIN=215 waybar
```

## Управление

- ЛКМ по модулю — открыть/закрыть меню.
- СКМ — предыдущий трек, ПКМ — пауза/плей, колесо — громкость.
- В меню: prev/play/next, иконка динамика открывает слайдер громкости,
  нижний слайдер — перемотка, `✕`/`Esc` — закрыть.
- Меню закрывается при клике вне карточки, при смене воркспейса niri и по
  повторному клику по модулю.

## Безопасность обложек

- Разрешён только `https://`.
- Хост проверяется по DNS: loopback, private, link-local, multicast, reserved
  и прочие непубличные адреса отклоняются. Проверка повторяется после редиректов.
- `file://`, `http://` и локальные файлы не используются.
- Лимит загрузки — 8 МБ, таймаут — 4 с; загрузка идёт в фоновом потоке.

Из-за этого обложки, которые Chromium/YouTube отдают как `file:///tmp/...`,
показываться не будут — это осознанное ограничение безопасности.

## Тесты

```bash
python3 -m py_compile bin/waybar-player-status share/player-menu.py tests/*.py
python3 -m venv --system-site-packages .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
shellcheck bin/waybar-player-menu
```

`--system-site-packages` нужен, чтобы тесты видели системный PyGObject (`gi`).
Тесты не открывают GTK-окна.

## Структура

```text
bin/
  waybar-player-status   # JSON-статус для Waybar (Python)
  waybar-player-menu     # bash-обёртка: single-instance + поиск player-menu.py
share/
  player-menu.py         # GTK3 + gtk-layer-shell попап
examples/
  config.jsonc
  style.css
docs/
  parity.md              # таблица паритета старого и нового статуса
  screenshot.png         # заглушка
tests/
PKGBUILD
LICENSE
```

## English

A compact MPRIS player for Waybar: a JSON status module and a GTK3 +
gtk-layer-shell popup. It includes an animated disc, marquee title, async
cover loading, seek and volume controls, and closes on outside click or niri
workspace change. Only public **https** cover URLs are allowed. Install with
the provided PKGBUILD or copy the files manually; see the Russian sections
above for configuration, environment variables and tests.

## Лицензия

MIT. См. [LICENSE](LICENSE).
