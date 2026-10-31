# MPRIS: несколько плееров

Дата проверки: 2026-10-31. Контекст: Яндекс Музыка — отдельное Electron-приложение
с собственным MPRIS-именем (`chromium.instance...`), YouTube — Firefox
(`firefox`). Это не один MPRIS на браузер.

## Что было видно в момент проверки

```text
$ playerctl -l
chromium.instance125864

$ playerctl -a metadata --format '{{playerName}} {{status}} | {{title}}'
chromium Playing | In the Field of Blood
```

Проверка каждого имени:

```text
$ playerctl -p chromium.instance125864 status
Playing
$ playerctl -p chromium.instance125864 loop
No player could handle this command
$ playerctl -p chromium.instance125864 shuffle
No player could handle this command
$ playerctl -p chromium.instance125864 volume
1.000000
```

Без `-p`:

```text
$ playerctl metadata --format '{{playerName}} {{status}} | {{title}}'
chromium Playing | In the Field of Blood

$ playerctl loop
No player could handle this command
```

В этот момент Firefox-плеера не было, поэтому проверить маршрутизацию между
двумя живыми плеерами не удалось. При одном плеере playerctl без `-p`
обслуживает его.

## Поведение playerctl без `-p`

`playerctl` без `-p` не знает о «текущем» или «выбранном» плеере. Для каждой
команды он выбирает первый MPRIS-плеер, который **умеет эту команду**; это не
обязательно играющий плеер и не обязательно тот, чей трек показан. Поэтому
`metadata`, `loop`, `shuffle`, `volume` и управляющие команды могут уходить
разным плеерам. Это и давало симптомы:

- пауза в YouTube/Firefox могла перехватывать управление у играющей музыки;
- `loop` без `-p` уходил в Firefox, хотя карточка показывала Яндекс Музыку;
- возврат к музыке происходил только после play в её сессии.

## Политика waybar-player

Выбор общий для `waybar-player-status`, попапа и `waybar-player-ctl`:

1. Если текущий выбранный плеер играет — остаёмся на нём, даже если играет
   второй.
2. Иначе Playing важнее Paused/Stopped.
3. Среди равных кандидатов: `WAYBAR_PLAYER_PRIORITY` (подстроки имён через
   запятую), затем липкий текущий плеер, затем самый недавно активный.
4. Если не играет никто — остаётся липкий текущий плеер.
5. Состояние хранится в `$XDG_RUNTIME_DIR/waybar-player/selection.json`
   под `flock`; запись атомарная.

Все запросы и команды к выбранному плееру выполняются с `-p <выбранный>`.
Исключение — служебный `playerctl -a --follow` в статусном процессе, который
нужен, чтобы видеть события всех плееров.

## Firefox и обложка

На момент проверки Firefox MPRIS-сеанса не публиковал:

```text
$ playerctl -p firefox metadata mpris:artUrl
No players found
```

Поэтому причину заглушки обложки в Firefox сейчас подтвердить нельзя. Когда
Firefox начнёт воспроизведение, проверьте:

```bash
playerctl -l
playerctl -p firefox metadata mpris:artUrl
```

Схема/путь должны попадать в разрешённые `file://`-каталоги; иначе это
ограничение безопасности, а не регрессия выбора плеера.

## Проверка выбора

```bash
playerctl -l
playerctl -a metadata --format '{{playerName}} {{status}} | {{title}}'
playerctl -p <name> status
playerctl -p <name> loop
playerctl -p <name> shuffle
playerctl -p <name> volume
```

Сравните, какой игрок отвечает без `-p`, и какой выбран в
`$XDG_RUNTIME_DIR/waybar-player/selection.json`.
